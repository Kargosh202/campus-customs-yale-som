"""Read access to data/campus_customs.db."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from models import (
    DEFAULT_RESULTS_TITLE,
    AgentResult,
    ChatMessage,
    Product,
    ProductCard,
    ProductResults,
    ProductSummary,
    SizeStock,
    User,
)

HW_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = HW_DIR / "data"
ENV_FILES = [HW_DIR / ".env", HW_DIR.parent / ".env"]  # repo .env first, then the course folder's
DB_PATH = DATA_DIR / "campus_customs.db"

SIZE_ORDER = ["XS", "S", "M", "L", "XL", "XXL"]


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def image_url(image_file_path: str) -> str:
    # image_file_path is relative to data/, e.g. "products/x.jpg"; /media serves data/
    return f"/media/{image_file_path}"


def _summary_fields(row: sqlite3.Row) -> dict:
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "garment_type": row["garment_type"],
        "description": row["description"],
        "price": row["price"],
        "image_url": image_url(row["image_file_path"]),
    }


def list_products() -> list[ProductSummary]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM catalogue ORDER BY name").fetchall()
    return [ProductSummary(**_summary_fields(row)) for row in rows]


def get_product(product_id: str) -> Product | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM catalogue WHERE product_id = ?", (product_id,)).fetchone()
        if row is None:
            return None
        stock_rows = conn.execute(
            "SELECT size, quantity FROM inventory WHERE product_id = ?", (product_id,)
        ).fetchall()

    def size_rank(size: str) -> int:
        return SIZE_ORDER.index(size) if size in SIZE_ORDER else len(SIZE_ORDER)

    inventory = sorted(
        (SizeStock(size=r["size"], quantity=r["quantity"]) for r in stock_rows),
        key=lambda s: size_rank(s.size),
    )
    return Product(
        **_summary_fields(row),
        colors=json.loads(row["colors"]),
        search_tags=json.loads(row["search_tags"]),
        inventory=inventory,
        total_stock=sum(s.quantity for s in inventory),
    )


USER_COLUMNS = "id, first_name, last_name, name, email"


def _user(row: sqlite3.Row) -> User:
    # Older rows may only have `name`; fall back to splitting it.
    first, _, last = row["name"].partition(" ")
    return User(
        id=row["id"],
        first_name=row["first_name"] or first,
        last_name=row["last_name"] or last,
        name=row["name"],
        email=row["email"],
    )


def get_user(user_id: int) -> User | None:
    with connect() as conn:
        row = conn.execute(f"SELECT {USER_COLUMNS} FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user(row) if row else None


def get_login(email: str) -> tuple[User, str] | None:
    """The user with this email and their password hash, for checking a login."""
    with connect() as conn:
        row = conn.execute(
            f"SELECT {USER_COLUMNS}, password_hash FROM users WHERE email = ?", (email,)
        ).fetchone()
    return (_user(row), row["password_hash"]) if row else None


def create_user(first_name: str, last_name: str, email: str, password_hash: str) -> User | None:
    """Insert a new user. Returns None if the email is already registered."""
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (name, first_name, last_name, email, password_hash) VALUES (?, ?, ?, ?, ?)",
                (f"{first_name} {last_name}", first_name, last_name, email, password_hash),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    return get_user(user_id)


def get_chat_history(user_id: int, limit: int = 50) -> list[ChatMessage]:
    """The user's most recent chat messages, oldest first, with the product cards that were shown."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, products_json FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    messages = []
    for row in reversed(rows):
        products = []
        for item in json.loads(row["products_json"] or "[]"):
            try:
                products.append(ProductCard.model_validate(item))
            except ValidationError:
                continue  # skip a card saved in an older format rather than failing the whole history
        # The table has no column for the results title, so reloaded cards get the default heading.
        results = ProductResults(title=DEFAULT_RESULTS_TITLE, products=products) if products else None
        messages.append(ChatMessage(role=row["role"], content=row["content"], results=results))
    return messages


def save_chat_turn(user_id: int, user_message: str, result: AgentResult) -> None:
    """Store one exchange: the shopper's message, then the assistant's reply with the full
    records of the products it showed (the same shape as the seeded chat_messages rows)."""
    products_json = json.dumps([p.model_dump() for p in result.products])
    with connect() as conn:
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content) VALUES (?, 'user', ?)",
            (user_id, user_message),
        )
        conn.execute(
            "INSERT INTO chat_messages (user_id, role, content, products_json) VALUES (?, 'assistant', ?, ?)",
            (user_id, result.reply, products_json),
        )
