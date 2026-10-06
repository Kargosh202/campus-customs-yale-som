"""Tools the Campus Customs agent can call.

The product tools only read the catalogue and inventory tables. get_shopper_profile reads the
current shopper from the agent's deps (built from the login session), so the agent can only ever
see the account of the person it's talking to, never the users or chat_messages tables.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic_ai import RunContext

import db
from models import (
    LOW_STOCK_THRESHOLD,
    CatalogueOverview,
    ChatDeps,
    ShopperProfile,
    CategorySummary,
    ProductDetails,
    ProductMatch,
    ProductSearchResult,
    SizeAvailability,
    StockStatus,
    ToolError,
)

SIZES = db.SIZE_ORDER

# The catalogue's garment_type values are inconsistent ("short-sleeve T-shirt", "t-shirt", ...),
# so each product is put in one category. Checked in order: "crew-neck t-shirt" is a T-shirt.
CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("t-shirt", ("t-shirt",)),
    ("quarter-zip", ("quarter-zip",)),
    ("jacket", ("jacket",)),
    ("hoodie", ("hood",)),
    ("mockneck", ("mockneck",)),
    ("long-sleeve shirt", ("long-sleeve",)),
    ("crewneck", ("crewneck",)),
]
CATEGORIES = [name for name, _ in CATEGORY_RULES]

# Words shoppers use -> words that appear in the catalogue.
SYNONYMS: dict[str, list[str]] = {
    "handsome dan": ["bulldog"],
    "dan": ["bulldog"],
    "mascot": ["bulldog"],
    "dog": ["bulldog"],
    "tee": ["t-shirt", "t shirt"],
    "tshirt": ["t-shirt", "t shirt"],
    "shirt": ["t-shirt", "t shirt", "long-sleeve", "long sleeve"],
    "hoody": ["hoodie", "hood"],
    "hoodie": ["hoodie", "hood"],
    "sweatshirt": ["sweatshirt", "crewneck", "hoodie"],
    "crew": ["crewneck"],
    "quarter zip": ["quarter-zip", "1 4 zip", "1/4 zip"],
    "1/4 zip": ["quarter-zip", "1 4 zip"],
    "quarterzip": ["quarter-zip", "1 4 zip"],
    "zip": ["zip"],
    "fleece": ["fleece"],
    "sweater": ["sweater", "fleece"],
    "jacket": ["jacket"],
    "grey": ["gray"],
    "gray": ["gray"],
    "navy": ["navy"],
    "yale": ["yale"],
    "harvard": ["harvard", "the game"],
    "game": ["the game", "harvard"],
    "mom": ["mom"],
    "dad": ["dad"],
    "parent": ["mom", "dad"],
    "grandparent": ["grandma", "grandpa"],
    "college": ["college"],
    "law": ["law school"],
    "som": ["school of management"],
    # Kept as-is so they don't turn into "short" (short-sleeve) or "pant".
    "shorts": ["shorts"],
    "pants": ["pants", "sweatpants", "joggers"],
    "management": ["school of management"],
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "with", "in", "on", "to", "any", "some", "do", "you",
    "have", "has", "i", "im", "me", "my", "show", "want", "looking", "something", "anything", "item",
    "items", "stuff", "merch", "that", "this", "is", "are", "it", "got", "u", "what", "which",
}


def categorize(garment_type: str) -> str:
    text = garment_type.lower()
    for name, needles in CATEGORY_RULES:
        if any(n in text for n in needles):
            return name
    return "other"


def _load_catalogue() -> list[dict[str, Any]]:
    """All products with their per-size stock, read fresh so stock is always current."""
    with db.connect() as conn:
        rows = conn.execute("SELECT * FROM catalogue").fetchall()
        stock_rows = conn.execute("SELECT product_id, size, quantity FROM inventory").fetchall()
    stock: dict[str, dict[str, int]] = {}
    for r in stock_rows:
        stock.setdefault(r["product_id"], {})[r["size"]] = r["quantity"]
    products = []
    for r in rows:
        sizes = stock.get(r["product_id"], {})
        products.append(
            {
                "product_id": r["product_id"],
                "name": r["name"],
                "category": categorize(r["garment_type"]),
                "garment_type": r["garment_type"],
                "description": r["description"],
                "colors": json.loads(r["colors"]),
                "search_tags": json.loads(r["search_tags"]),
                "price": r["price"],
                "stock": {size: sizes.get(size, 0) for size in SIZES},
            }
        )
    return products


def _query_terms(query: str) -> list[list[str]]:
    """Split a query into terms; each term is a list of alternatives that count as a match."""
    text = re.sub(r"[^a-z0-9/\- ]", " ", query.lower())
    terms: list[list[str]] = []
    for phrase in ("handsome dan", "quarter zip", "1/4 zip", "t shirt"):
        if phrase in text:
            terms.append(SYNONYMS.get(phrase, [phrase.replace(" ", "-")]) + [phrase])
            text = text.replace(phrase, " ")
    for word in text.split():
        if word in STOPWORDS or len(word) < 2:
            continue
        alternatives = {word, *SYNONYMS.get(word, [])}
        if len(word) > 3 and word.endswith("s") and word not in SYNONYMS:  # "hoodies" -> "hoodie"
            singular = word[:-1]
            alternatives |= {singular, *SYNONYMS.get(singular, [])}
        terms.append(sorted(alternatives))
    return terms


def _status(quantity: int) -> StockStatus:
    if quantity <= 0:
        return "out_of_stock"
    return "low_stock" if quantity <= LOW_STOCK_THRESHOLD else "in_stock"


def _match_fields(p: dict[str, Any]) -> dict[str, Any]:
    total = sum(p["stock"].values())
    return {
        "product_id": p["product_id"],
        "name": p["name"],
        "category": p["category"],
        "description": p["description"],
        "colors": p["colors"],
        "price": p["price"],
        "price_text": f"${p['price']:,.2f}",
        "total_stock": total,
        "availability": "in_stock" if total > 0 else "out_of_stock",
        "sizes_in_stock": [size for size, qty in p["stock"].items() if qty > 0],
        "sizes_out_of_stock": [size for size, qty in p["stock"].items() if qty <= 0],
    }


def search_products(
    query: str = "",
    category: str | None = None,
    color: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    size_in_stock: str | None = None,
    limit: int = 8,
) -> ProductSearchResult | ToolError:
    """Search the Campus Customs catalogue. Use this before naming, pricing, or recommending any product.

    Matching is by keyword over product names, descriptions, search tags, colors, and garment types,
    with common synonyms (e.g. "Handsome Dan" -> bulldog, "tee" -> T-shirt, "grey" -> gray).
    Products matching more of the query's words rank higher. If nothing matches, try fewer or
    different words, or a broader category, before telling the shopper we don't carry it.

    Args:
        query: What the shopper is looking for, e.g. "bulldog hoodie" or "gift for dad". Leave empty to list by filters only.
        category: Optional exact category: t-shirt, crewneck, hoodie, quarter-zip, jacket, long-sleeve shirt, mockneck.
        color: Optional color the product must come in, e.g. "navy" or "gray".
        max_price: Optional highest price in US dollars.
        min_price: Optional lowest price in US dollars.
        size_in_stock: Optional size that must currently be in stock: XS, S, M, L, XL, or XXL.
        limit: Maximum number of results (1-20).
    """
    products = _load_catalogue()
    limit = max(1, min(limit, 20))

    if category:
        cat = category.strip().lower()
        if cat not in CATEGORIES:
            return ToolError(error=f"Unknown category {category!r}.", valid_values=CATEGORIES)
        products = [p for p in products if p["category"] == cat]
    if color:
        wanted = color.strip().lower().replace("grey", "gray")
        products = [p for p in products if any(wanted in c.lower() for c in p["colors"])]
    if max_price is not None:
        products = [p for p in products if p["price"] <= max_price]
    if min_price is not None:
        products = [p for p in products if p["price"] >= min_price]
    if size_in_stock:
        size = size_in_stock.strip().upper()
        if size not in SIZES:
            return ToolError(error=f"Unknown size {size_in_stock!r}.", valid_values=SIZES)
        products = [p for p in products if p["stock"].get(size, 0) > 0]

    terms = _query_terms(query)
    partial = False
    if terms:
        scored = []
        for p in products:
            strong = " ".join([p["name"], p["garment_type"], *p["search_tags"], *p["colors"]]).lower()
            weak = p["description"].lower()
            matched, score = 0, 0
            for alternatives in terms:
                if any(a in strong for a in alternatives):
                    matched, score = matched + 1, score + 3
                elif any(a in weak for a in alternatives):
                    matched, score = matched + 1, score + 1
            if matched:
                scored.append((matched, score, p))
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]["name"]))
        # Prefer products that match every word; fall back to partial matches only if there are none.
        full = [p for matched, _, p in scored if matched == len(terms)]
        partial = not full and bool(scored)
        products = full or [p for _, _, p in scored]
    else:
        products.sort(key=lambda p: p["name"])

    prices = [p["price"] for p in products]
    lo, hi = (min(prices), max(prices)) if prices else (None, None)
    return ProductSearchResult(
        match_count=len(products),
        min_price=lo,
        max_price=hi,
        price_range_text=None if lo is None else (f"${lo:,.2f}" if lo == hi else f"${lo:,.2f} to ${hi:,.2f}"),
        note="No product matches every word of the query; these match only some of them." if partial else None,
        results=[ProductMatch(**_match_fields(p)) for p in products[:limit]],
    )


def get_product_details(product_id: str) -> ProductDetails | ToolError:
    """Exact, live details for one product: description, price, colors, and stock for every size.

    Call this for any question about a specific product's price, stock, sizes, or availability,
    even if the product came up earlier in the conversation, because stock changes.
    Each size has a quantity and a status: in_stock, low_stock (5 or fewer left), or out_of_stock.

    Args:
        product_id: The product's product_id, as returned by search_products.
    """
    for p in _load_catalogue():
        if p["product_id"] == product_id:
            stock_by_size = [
                SizeAvailability(size=size, quantity=qty, status=_status(qty)) for size, qty in p["stock"].items()
            ]
            return ProductDetails(
                **_match_fields(p),
                garment_type=p["garment_type"],
                search_tags=p["search_tags"],
                stock_by_size=stock_by_size,
                low_stock_sizes=[s.size for s in stock_by_size if s.status == "low_stock"],
            )
    return ToolError(error=f"No product with id {product_id!r}. Use search_products to find the right id.")


def catalogue_overview() -> CatalogueOverview:
    """A summary of everything the store sells: each category with its product count and price range.

    Use this for broad questions like "what do you sell?" or "what's your cheapest item?".
    """
    products = _load_catalogue()
    categories: dict[str, list[float]] = {}
    for p in products:
        categories.setdefault(p["category"], []).append(p["price"])
    summaries = []
    for name in CATEGORIES:
        prices = categories.get(name)
        if not prices:
            continue
        lo, hi = min(prices), max(prices)
        summaries.append(
            CategorySummary(
                category=name,
                product_count=len(prices),
                min_price=lo,
                max_price=hi,
                price_range_text=f"${lo:,.2f}" if lo == hi else f"${lo:,.2f} to ${hi:,.2f}",
            )
        )
    return CatalogueOverview(total_products=len(products), sizes_offered=SIZES, categories=summaries)


def get_shopper_profile(ctx: RunContext[ChatDeps]) -> ShopperProfile:
    """The logged-in shopper's own account details: first name, last name, and email.

    Call this only when the shopper asks about their own account (e.g. "what email am I logged in
    with?"). It always describes the person you're talking to, never anyone else.
    """
    shopper = ctx.deps.shopper
    if shopper is None:
        return ShopperProfile(logged_in=False)
    return ShopperProfile(
        logged_in=True, first_name=shopper.first_name, last_name=shopper.last_name, email=shopper.email
    )


AGENT_TOOLS = [search_products, get_product_details, catalogue_overview, get_shopper_profile]
