"""Campus Customs API.

    .venv/bin/uvicorn main:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from collections.abc import AsyncIterator, Callable

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import db
from agent import run_chat
from models import (
    AuditContext,
    ChatDeps,
    ChatMessage,
    ChatRequest,
    LoginRequest,
    Product,
    ProductSummary,
    RegisterRequest,
    Shopper,
    User,
    ViewedProduct,
)
from passwords import DUMMY_HASH, hash_password, verify_password

for env_file in db.ENV_FILES:  # earlier files win; existing environment variables win over both
    load_dotenv(env_file)
session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    sys.exit("SESSION_SECRET is not set. Copy .env.example to .env and fill it in.")

logger = logging.getLogger("campus_customs")

app = FastAPI(title="Campus Customs API")

# Login state lives in a signed, HttpOnly cookie that holds only the user id.
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="cc_session",
    max_age=14 * 24 * 3600,
    same_site="lax",
    https_only=False,  # local dev runs over http; set True when served over https
)

FIELD_ERRORS = {
    "email": "Please enter a valid email address.",
    "password": "Password must be between 8 and 128 characters.",
    "first_name": "Please enter your first name.",
    "last_name": "Please enter your last name.",
    "message": "Messages must be between 1 and 2,000 characters.",
}


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Turn Pydantic's validation errors into one message a shopper can act on."""
    field = next((e["loc"][-1] for e in exc.errors() if e.get("loc")), None)
    return JSONResponse(
        status_code=422,
        content={"detail": FIELD_ERRORS.get(field, "Please check the form and try again.")},
    )


# Product photos: /media/products/<file>.jpg -> data/products/<file>.jpg
app.mount("/media/products", StaticFiles(directory=db.DATA_DIR / "products"), name="media")


@app.get("/api/products")
def list_products() -> list[ProductSummary]:
    return db.list_products()


@app.get("/api/products/{product_id}")
def get_product(product_id: str) -> Product:
    product = db.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def normalize_email(email: str) -> str:
    return email.strip().lower()


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterRequest, request: Request) -> User:
    first_name, last_name = body.first_name.strip(), body.last_name.strip()
    if not first_name or not last_name:
        raise HTTPException(status_code=422, detail="First and last name are required.")
    if body.password != body.confirm_password:
        raise HTTPException(status_code=422, detail="Passwords do not match.")
    user = db.create_user(first_name, last_name, normalize_email(body.email), hash_password(body.password))
    if user is None:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    request.session.clear()
    request.session["user_id"] = user.id
    return user


@app.post("/api/auth/login")
def login(body: LoginRequest, request: Request) -> User:
    found = db.get_login(normalize_email(body.email))
    stored_hash = found[1] if found else DUMMY_HASH
    if not verify_password(body.password, stored_hash) or found is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password.")
    request.session.clear()
    request.session["user_id"] = found[0].id
    return found[0]


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request) -> None:
    request.session.clear()


def current_user(request: Request) -> User | None:
    user_id = request.session.get("user_id")
    user = db.get_user(user_id) if user_id is not None else None
    if user is None:
        request.session.clear()
    return user


@app.get("/api/auth/me")
def me(request: Request) -> User:
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in.")
    return user


def build_chat_deps(user: User | None, body: ChatRequest) -> ChatDeps:
    """The agent's context for one message.

    Who is chatting comes only from the session (a shopper can't claim to be someone else in the
    request), and the product page is checked against the database.
    """
    shopper = None
    if user:
        shopper = Shopper(user_id=user.id, first_name=user.first_name, last_name=user.last_name, email=user.email)

    viewed = None
    product = db.get_product(body.page.product_id) if body.page.product_id else None
    if product:
        viewed = ViewedProduct(
            product_id=product.product_id,
            name=product.name,
            garment_type=product.garment_type,
            colors=product.colors,
            description=product.description,
        )
    return ChatDeps(shopper=shopper, page_path=body.page.path, viewed_product=viewed)


class ChatError(Exception):
    """A chat request that failed; `detail` is safe to show the shopper."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail


async def answer_chat(
    body: ChatRequest, request: Request, endpoint: str, on_status: Callable[[str], None] | None = None
) -> ChatMessage:
    """Answer one chat message: build context, run the agent, save the turn.

    Logged-in shoppers' conversations are saved in chat_messages and reloaded from there.
    Logged-out shoppers' history comes from the request and isn't saved. The agent appends every
    loop step to output/audit_trail.json (see audit.py).
    """
    user = current_user(request)
    message = body.message.strip()
    if not message:
        raise ChatError(422, FIELD_ERRORS["message"])
    if user:
        history = db.get_chat_history(user.id)
    else:
        history = [ChatMessage(role=t.role, content=t.content) for t in body.history]

    deps = build_chat_deps(user, body)
    deps.on_status = on_status
    audit_context = AuditContext(
        turn_id=uuid.uuid4().hex[:12],
        endpoint=endpoint,
        user_id=user.id if user else None,
        page_path=body.page.path,
    )
    try:
        result = await run_chat(message, history, deps, audit_context=audit_context)
    except Exception as exc:
        logger.exception("Chat agent failed")
        raise ChatError(502, "The assistant couldn't answer just now. Please try again.") from exc

    if user:
        db.save_chat_turn(user.id, message, result)
    return result.to_message()


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request) -> ChatMessage:
    """Send one message to the shopping assistant and get its reply (with product cards)."""
    try:
        return await answer_chat(body, request, endpoint="/api/chat")
    except ChatError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest, request: Request) -> StreamingResponse:
    """The same as POST /api/chat, but as Server-Sent Events so the widget can show progress.

    Events, in order:
      status   {"text": "Searching the catalogue for hoodies…"}   (zero or more)
      message  the ChatMessage reply                               (on success)
      error    {"detail": "..."}                                   (on failure)
    The reply text is sent whole at the end, after the fact-check has approved it.
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def work() -> None:
        try:
            reply = await answer_chat(
                body,
                request,
                endpoint="/api/chat/stream",
                on_status=lambda text: queue.put_nowait(sse("status", {"text": text})),
            )
            queue.put_nowait(sse("message", reply.model_dump(mode="json")))
        except ChatError as exc:
            queue.put_nowait(sse("error", {"detail": exc.detail}))
        except Exception:
            logger.exception("Chat stream failed")
            queue.put_nowait(sse("error", {"detail": "The assistant couldn't answer just now. Please try again."}))
        finally:
            queue.put_nowait(None)

    async def events() -> AsyncIterator[str]:
        task = asyncio.create_task(work())
        try:
            while (item := await queue.get()) is not None:
                yield item
        finally:
            await task

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/chat/history")
def chat_history(request: Request) -> list[ChatMessage]:
    """The logged-in shopper's saved conversation (empty when logged out)."""
    user = current_user(request)
    return db.get_chat_history(user.id) if user else []
