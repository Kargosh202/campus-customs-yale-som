"""Pydantic models for the API and Pydantic AI structured types for the chat agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, model_validator


class SizeStock(BaseModel):
    size: str
    quantity: int


class ProductSummary(BaseModel):
    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    image_url: str


class Product(ProductSummary):
    colors: list[str]
    search_tags: list[str]
    inventory: list[SizeStock]
    total_stock: int


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str = Field(max_length=128)


class User(BaseModel):
    """A user as returned by the API. Never includes password_hash."""

    id: int
    first_name: str
    last_name: str
    name: str
    email: str


# --- Chat API ---------------------------------------------------------------


class ChatTurn(BaseModel):
    """One earlier message, sent by the website when the shopper isn't logged in."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class PageContext(BaseModel):
    """Where the shopper is on the website when they send a message."""

    path: str = Field(default="/", max_length=300, description='The page URL path, e.g. "/products/basic-hoodie-big-yale".')
    product_id: str | None = Field(
        default=None, max_length=200, description="The product_id when the shopper is on a product page."
    )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    # The page the shopper is on, so "do you have this in pink?" can be resolved.
    page: PageContext = Field(default_factory=PageContext)
    # Only used for logged-out shoppers; logged-in history comes from chat_messages.
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)


SHORT_DESCRIPTION_CHARS = 110


def short_description(description: str) -> str:
    """The first sentence of a description, cut at a word boundary if it's long."""
    first = description.split(". ")[0].rstrip(".")
    if len(first) <= SHORT_DESCRIPTION_CHARS:
        return first + "."
    return first[:SHORT_DESCRIPTION_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "…"


class ProductCard(BaseModel):
    """One product card the website renders: image, name, price, and short info.

    Always built by the backend from the database (never written by the model), so every field is
    real. chat_messages.products_json keeps full Product records, which also load as cards.
    """

    product_id: str
    name: str
    garment_type: str
    price: float
    image_url: str
    short_description: str
    colors: list[str]
    total_stock: int  # 0 means out of stock in every size

    @model_validator(mode="before")
    @classmethod
    def _derive_short_description(cls, data: Any) -> Any:
        if isinstance(data, dict) and "short_description" not in data and "description" in data:
            data = {**data, "short_description": short_description(data["description"])}
        return data

    @classmethod
    def from_product(cls, product: Product) -> ProductCard:
        return cls.model_validate(product.model_dump())


DEFAULT_RESULTS_TITLE = "Suggested products"


class ProductResults(BaseModel):
    """The structured product matches attached to an assistant reply.

    The chat widget shows them under the reply, and the page shows them as a grid of cards.
    """

    title: str = Field(description='Short heading for the cards, e.g. "Hoodies" or "Navy hoodies under $70".')
    products: list[ProductCard]


class ChatMessage(BaseModel):
    """One message in the chat: what POST /api/chat returns and GET /api/chat/history lists."""

    role: Literal["user", "assistant"]
    content: str
    results: ProductResults | None = None  # only on assistant messages that matched products


# --- Tool results (what the agent's tools return) ---------------------------
# Every price and stock number the agent may quote comes from one of these, read live from
# campus_customs.db. Explicit statuses ("out_of_stock") mean the model never has to infer
# availability from a raw number.

LOW_STOCK_THRESHOLD = 5  # 1-5 left counts as low stock

StockStatus = Literal["in_stock", "low_stock", "out_of_stock"]


class SizeAvailability(BaseModel):
    size: str
    quantity: int
    status: StockStatus


class ProductMatch(BaseModel):
    """One product as returned by search_products."""

    product_id: str
    name: str
    category: str
    description: str
    colors: list[str]
    price: float
    price_text: str = Field(description='The price formatted for quoting, e.g. "$68.00".')
    total_stock: int = Field(description="Units in stock across all sizes. 0 means out of stock in every size.")
    availability: Literal["in_stock", "out_of_stock"]
    sizes_in_stock: list[str]
    sizes_out_of_stock: list[str]


class ProductDetails(ProductMatch):
    """One product as returned by get_product_details, with exact stock for every size."""

    garment_type: str
    search_tags: list[str]
    stock_by_size: list[SizeAvailability]
    low_stock_sizes: list[str]


class ProductSearchResult(BaseModel):
    match_count: int = Field(description="How many products matched in total (results may show fewer).")
    price_range_text: str | None = Field(
        default=None, description='Lowest to highest price across ALL matches, e.g. "$45.00 to $88.00".'
    )
    min_price: float | None = None
    max_price: float | None = None
    note: str | None = None
    results: list[ProductMatch]


class CategorySummary(BaseModel):
    category: str
    product_count: int
    min_price: float
    max_price: float
    price_range_text: str


class CatalogueOverview(BaseModel):
    total_products: int
    sizes_offered: list[str]
    categories: list[CategorySummary]


class ToolError(BaseModel):
    """Returned instead of a result when a tool's input is invalid (unknown id, size, or category)."""

    error: str
    valid_values: list[str] = Field(default_factory=list)


# --- Agent (Pydantic AI) ----------------------------------------------------


@dataclass
class Shopper:
    """Who is chatting. Built by the backend from the login session, never from the request body."""

    user_id: int
    first_name: str
    last_name: str
    email: str


@dataclass
class ViewedProduct:
    """The product page the shopper has open, looked up in the database."""

    product_id: str
    name: str
    garment_type: str
    colors: list[str]
    description: str


@dataclass
class ChatDeps:
    """Per-request context handed to the agent's instructions and tools (Pydantic AI deps).

    main.py builds one for every chat message:
    - shopper: from the session cookie (None when logged out)
    - page_path / viewed_product: from the request's PageContext, with the product checked
      against the database
    """

    shopper: Shopper | None = None
    page_path: str = "/"
    viewed_product: ViewedProduct | None = None
    # Progress updates for the chat widget ("Checking stock…"). Not shown to the model.
    on_status: Callable[[str], None] | None = field(default=None, repr=False)

    def status(self, text: str) -> None:
        if self.on_status:
            self.on_status(text)


class ShopperProfile(BaseModel):
    """What get_shopper_profile returns: the logged-in shopper's own account details."""

    logged_in: bool
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None


MAX_PRODUCT_MATCHES = 12


class AgentReply(BaseModel):
    """The agent's structured output for every message: the reply text plus its product matches."""

    reply: str = Field(description="The message shown to the shopper. Light Markdown (bold, bullet lists) is fine.")
    product_ids: list[str] = Field(
        default_factory=list,
        description=(
            f"product_id values of the products that match the shopper's request, best first, at most "
            f"{MAX_PRODUCT_MATCHES}. The website shows each one as a product card (image, name, price, short info). "
            "Only use ids returned by your tools in this turn. Leave empty when no specific product is relevant."
        ),
    )
    results_title: str | None = Field(
        default=None,
        description=(
            'A short heading (2 to 6 words) for those product cards, e.g. "Hoodies", "Bulldog gear", '
            '"Navy hoodies under $70". Leave empty when product_ids is empty.'
        ),
    )


# --- Audit trail -------------------------------------------------------------


class ToolCallRecord(BaseModel):
    """One tool call the agent made while answering a message."""

    tool: str
    args: dict[str, Any]
    duration_ms: int | None = None
    result: str | None = None  # a short summary, not the full tool output


class TurnTrace(BaseModel):
    """How the agent produced one reply: which tools it used, retries, tokens, and timing."""

    model: str
    reasoning_effort: str
    outcome: Literal["answered", "content_filter"] = "answered"
    duration_ms: int = 0
    model_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    fact_check_retries: list[str] = Field(default_factory=list)  # why each reply was sent back


class AuditToolCall(BaseModel):
    """One tool call inside an agent-loop step (final_result is the agent's structured answer)."""

    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None  # shortened; "retry: …" if the call or the answer was sent back


class AuditEntry(BaseModel):
    """One agent-loop iteration (one model response) in output/audit_trail.json."""

    timestamp: str
    turn_id: str  # groups the steps of one chat message
    step: int
    endpoint: str
    user_id: int | None  # never the name or email
    page_path: str
    message: str  # the shopper's message, shortened
    model: str | None = None
    reasoning_effort: str | None = None
    tool_calls: list[AuditToolCall] = Field(default_factory=list)
    stop_reason: str | None = None  # the model's finish reason, or "content_filter" / "error: …"
    ended_run: bool = False  # True on the step that produced the final answer (or ended in error)
    input_tokens: int = 0
    output_tokens: int = 0
    turn_latency_ms: int | None = None  # on the last step of the turn


@dataclass
class AuditContext:
    """Where a chat message came from, attached to every audit entry for that message."""

    turn_id: str
    endpoint: str
    user_id: int | None
    page_path: str


@dataclass
class AgentResult:
    """A finished agent run: the reply text and the full records of the products it recommended."""

    reply: str
    products: list[Product]
    results_title: str | None = None
    trace: TurnTrace | None = None

    def to_message(self) -> ChatMessage:
        results = None
        if self.products:
            results = ProductResults(
                title=self.results_title or DEFAULT_RESULTS_TITLE,
                products=[ProductCard.from_product(p) for p in self.products],
            )
        return ChatMessage(role="assistant", content=self.reply, results=results)
