"""Campus Customs chat agent: Pydantic AI on OpenAI's Responses API, routed through Portkey.

The system prompt is prompts/prompt.md, the tools are in tools.py, and the structured types are in
models.py. main.py calls run_chat() for each message from the website's chat widget. run_chat() also
reports progress ("Checking stock…") through ChatDeps.status and returns a TurnTrace of the tool
calls, fact-check retries, tokens, and timing, which main.py writes to the audit trail.

Model and reasoning effort default to gpt-5.6-luna / high and can be changed with the
OPENAI_MODEL and OPENAI_REASONING_EFFORT environment variables.
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import AsyncIterable
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, ModelRetry, RunContext, capture_run_messages
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import (
    AgentStreamEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_core import to_jsonable_python
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

import audit
import db
from models import (
    MAX_PRODUCT_MATCHES,
    AuditContext,
    AuditEntry,
    AuditToolCall,
    AgentReply,
    AgentResult,
    CatalogueOverview,
    ChatDeps,
    ChatMessage,
    Product,
    ProductDetails,
    ProductSearchResult,
    ShopperProfile,
    ToolCallRecord,
    ToolError,
    TurnTrace,
)
from tools import AGENT_TOOLS, SIZES

BACKEND_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BACKEND_DIR / "prompts" / "prompt.md"

DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "high"
MAX_HISTORY_MESSAGES = 20  # earlier messages sent to the model with each new one
MAX_MODEL_REQUESTS = 12  # agent-loop limit: model calls allowed for one shopper message

# Sent when the model provider's own content filter blocks a message (for example a jailbreak
# attempt). Keeps the assistant in character instead of showing an error.
CONTENT_FILTER_REPLY = (
    "Ruff, sorry, I can't help with that one. I'm Handsome Dan, here to help you find Campus Customs "
    "gear, though. Looking for a hoodie, a tee, or a gift for someone?"
)


def _is_content_filter(error: ModelHTTPError) -> bool:
    body = error.body if isinstance(error.body, dict) else {}
    return error.status_code == 400 and body.get("code") == "content_filter"


# --- Fact check -------------------------------------------------------------
# Before a reply goes out, every dollar amount and stock count in it must match a number that a
# tool returned during this run (or that the shopper typed, like "under $50"). If not, the model
# is told to look it up and try again, so it can't quote a price or quantity from memory.

PRICE_RE = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)")
QUANTITY_RES = [
    re.compile(r"\b(\d+)\s+(?:left|remaining|available|in stock|units?|in total|total)\b", re.I),
    re.compile(r"\b(?:total of|only)\s+(\d+)\b", re.I),
    re.compile(r"\b(?:" + "|".join(sorted(SIZES, key=len, reverse=True)) + r")\b\s*(?:[:\u2013\u2014-]|has|with)?\s*\(?(\d+)\b"),
]
PRICE_KEYS = {"price", "min_price", "max_price"}
QUANTITY_KEYS = {"quantity", "total_stock", "match_count", "product_count", "total_products"}


def _walk(value: Any, found: dict[str, set[float]], names: set[str]) -> None:
    if isinstance(value, dict):
        for key, v in value.items():
            if key in PRICE_KEYS and isinstance(v, (int, float)):
                found["prices"].add(round(float(v), 2))
            elif key in QUANTITY_KEYS and isinstance(v, int):
                found["quantities"].add(v)
            elif key == "name" and isinstance(v, str):
                names.add(v)
            elif key == "results" and isinstance(v, list):
                found["quantities"].add(len(v))
            _walk(v, found, names)
    elif isinstance(value, list):
        for v in value:
            _walk(v, found, names)


def _numbers(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}


def check_facts(ctx: RunContext[ChatDeps], output: AgentReply) -> AgentReply:
    """Reject replies whose prices or stock counts didn't come from this run's tool results."""
    found: dict[str, set[float]] = {"prices": set(), "quantities": set()}
    names: set[str] = set()
    allowed = _numbers(ctx.prompt if isinstance(ctx.prompt, str) else "")  # numbers the shopper typed
    for message in ctx.messages:
        for part in message.parts:
            if isinstance(part, ToolReturnPart):
                _walk(to_jsonable_python(part.content), found, names)
            elif isinstance(part, ToolCallPart):
                allowed |= _numbers(str(part.args_as_dict().get("max_price", "")))
                allowed |= _numbers(str(part.args_as_dict().get("min_price", "")))

    text = output.reply
    for name in sorted(names, key=len, reverse=True):  # names like "Ua Mens Tech L S 2 0" aren't stock counts
        text = text.replace(name, " ")

    bad_prices = sorted({m for m in (float(x.replace(",", "")) for x in PRICE_RE.findall(text))
                         if round(m, 2) not in found["prices"] and m not in allowed})
    bad_counts = sorted({int(x) for rx in QUANTITY_RES for x in rx.findall(text)
                         if int(x) not in found["quantities"] and int(x) not in allowed})
    if bad_prices or bad_counts:
        problems = []
        if bad_prices:
            problems.append("prices " + ", ".join(f"${p:,.2f}" for p in bad_prices))
        if bad_counts:
            problems.append("stock counts " + ", ".join(map(str, bad_counts)))
        ctx.deps.status("Double-checking prices and stock…")
        raise ModelRetry(
            f"Your reply mentions {' and '.join(problems)}, which did not come from a tool result in this turn. "
            "Call get_product_details (or search_products) now and quote only the price_text and stock numbers it "
            "returns. If a size's status is out_of_stock, say it is out of stock."
        )
    return output


def model_name() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def default_reasoning_effort() -> str:
    return os.getenv("OPENAI_REASONING_EFFORT", DEFAULT_REASONING_EFFORT)


@lru_cache(maxsize=4)
def build_agent(reasoning_effort: str | None = None) -> Agent[ChatDeps, AgentReply]:
    """The agent, built once per reasoning effort (None means the default) and then reused."""
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    for env_file in db.ENV_FILES:
        load_dotenv(env_file)
    api_key = os.environ.get("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not set. Copy .env.example to .env and fill it in.")

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={
            "x-portkey-api-key": api_key,
            "x-portkey-provider": "openai",
            # Always get a fresh answer: stock changes, and a cached response for a repeated
            # question came back with an item id the model API rejected on the next tool round.
            "x-portkey-cache-force-refresh": "true",
        },
        max_retries=3,
    )
    model = OpenAIResponsesModel(model_name(), provider=OpenAIProvider(openai_client=client))
    agent = Agent(
        model,
        deps_type=ChatDeps,
        output_type=AgentReply,
        instructions=PROMPT_PATH.read_text(encoding="utf-8"),
        tools=AGENT_TOOLS,
        retries=2,
        model_settings=OpenAIResponsesModelSettings(
            openai_reasoning_effort=reasoning_effort or default_reasoning_effort(),
        ),
    )

    agent.output_validator(check_facts)

    @agent.instructions
    def chat_context(ctx: RunContext[ChatDeps]) -> str:
        return describe_context(ctx.deps)

    return agent


PAGE_NAMES = {
    "/": "the Home page",
    "/products": "the Products page (the full catalogue grid)",
    "/about": "the About Us page",
    "/login": "the Log In page",
    "/create-account": "the Create Account page",
}


def describe_context(deps: ChatDeps) -> str:
    """The per-message context added to the agent's instructions: who is chatting and where they are."""
    lines = ["## Current context"]
    if deps.shopper:
        lines.append(
            f"- Shopper: logged in as {deps.shopper.first_name} {deps.shopper.last_name}. "
            "Call get_shopper_profile if you need their email. Their conversation is saved and earlier "
            "messages above are from previous visits too."
        )
    else:
        lines.append("- Shopper: not logged in. You don't know their name, and this conversation isn't saved.")

    product = deps.viewed_product
    if product:
        lines.append(
            f"- Page: the product page for **{product.name}** (product_id: {product.product_id}). "
            "\"this\", \"it\", \"this one\", or \"this {kind}\" means this product.".format(kind=product.garment_type)
        )
        lines.append(f"  - Garment type: {product.garment_type}")
        lines.append(f"  - Colors it comes in: {', '.join(product.colors)}")
        lines.append(f"  - Description: {product.description}")
        lines.append("  - For its price, sizes, or stock, call get_product_details with this product_id.")
    else:
        lines.append(f"- Page: {PAGE_NAMES.get(deps.page_path, 'page ' + deps.page_path)}. No specific product is open.")
    return "\n".join(lines)


def to_model_history(messages: list[ChatMessage]) -> list[ModelMessage]:
    """Turn stored chat messages into Pydantic AI message history."""
    history: list[ModelMessage] = []
    for m in messages[-MAX_HISTORY_MESSAGES:]:
        if m.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=m.content)]))
        else:
            text = m.content
            if m.results:
                shown = ", ".join(f"{i}. {p.name} ({p.product_id})" for i, p in enumerate(m.results.products, 1))
                text += f"\n\n[Products shown: {shown}]"
            history.append(ModelResponse(parts=[TextPart(content=text)]))
    return history


# --- Progress updates and the trace ----------------------------------------


def status_for_tool(tool: str, args: dict[str, Any]) -> str:
    """A short, shopper-friendly line for the chat widget while a tool runs."""
    if tool == "search_products":
        what = args.get("query") or args.get("category") or "products"
        text = f"Sniffing through the catalogue for {what}"
        if args.get("color") and str(args["color"]).lower() not in str(what).lower():
            text += f" in {args['color']}"
        if args.get("max_price") is not None:
            text += f" under ${float(args['max_price']):g}"
        if args.get("size_in_stock"):
            text += f" in size {args['size_in_stock']}"
        return text + "…"
    if tool == "get_product_details":
        product = db.get_product(str(args.get("product_id", "")))
        return f"Checking price and stock for {product.name}…" if product else "Checking price and stock…"
    if tool == "catalogue_overview":
        return "Trotting through the whole catalogue…"
    if tool == "get_shopper_profile":
        return "Looking up your account…"
    return "Working on it…"


def summarize_tool_result(part: ToolReturnPart | RetryPromptPart) -> str:
    """A one-line summary of a tool result for the audit trail (never the shopper's email)."""
    if isinstance(part, RetryPromptPart):
        return f"invalid call, asked to retry: {str(part.content)[:200]}"
    content = part.content
    if isinstance(content, ProductSearchResult):
        ids = ", ".join(r.product_id for r in content.results[:5])
        more = "…" if len(content.results) > 5 else ""
        return f"{content.match_count} matches, returned {len(content.results)} ({ids}{more}), {content.price_range_text}"
    if isinstance(content, ProductDetails):
        stock = " ".join(f"{s.size}:{s.quantity}" for s in content.stock_by_size)
        return f"{content.product_id}: {content.price_text}, {content.availability}, {stock}"
    if isinstance(content, CatalogueOverview):
        return f"{content.total_products} products in {len(content.categories)} categories"
    if isinstance(content, ShopperProfile):
        return f"logged_in={content.logged_in}"
    if isinstance(content, ToolError):
        return f"error: {content.error}"
    return str(content)[:200]


def build_trace(
    result_messages: list[ModelMessage], calls: list[ToolCallRecord], effort: str, started: float, usage: Any
) -> TurnTrace:
    retries = [
        str(p.content)[:300]
        for m in result_messages
        if isinstance(m, ModelRequest)
        for p in m.parts
        if isinstance(p, RetryPromptPart) and p.tool_name not in {c.tool for c in calls}
    ]
    return TurnTrace(
        model=model_name(),
        reasoning_effort=effort,
        duration_ms=round((time.perf_counter() - started) * 1000),
        model_requests=getattr(usage, "requests", 0),
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
        tool_calls=calls,
        fact_check_retries=retries,
    )


def loop_entries(
    messages: list[ModelMessage],
    ctx: AuditContext,
    message: str,
    effort: str,
    *,
    final_output: AgentReply | None = None,
    stop: str | None = None,
    latency_ms: int,
) -> list[AuditEntry]:
    """One AuditEntry per model response in this run, with each tool call's short args and result.

    `final_output` is set when the run succeeded; `stop` ("content_filter" or "error: …") when it
    didn't. The last entry carries the end of the run and the total time for the message.
    """
    results: dict[str, str] = {}
    for m in messages:
        if isinstance(m, ModelRequest):
            for part in m.parts:
                if isinstance(part, ToolReturnPart):
                    results[part.tool_call_id] = summarize_tool_result(part)
                elif isinstance(part, RetryPromptPart) and part.tool_call_id:
                    results[part.tool_call_id] = "retry: " + str(part.content)

    base = dict(
        turn_id=ctx.turn_id, endpoint=ctx.endpoint, user_id=ctx.user_id, page_path=ctx.page_path,
        message=audit.shorten(message, 160), reasoning_effort=effort,
    )
    entries: list[AuditEntry] = []
    for m in messages:
        if not isinstance(m, ModelResponse):
            continue
        calls = [
            AuditToolCall(
                tool_name=p.tool_name,
                args=audit.short_args(p.args_as_dict()),
                result=audit.shorten(results[p.tool_call_id]) if p.tool_call_id in results else None,
            )
            for p in m.parts
            if isinstance(p, ToolCallPart)
        ]
        entries.append(AuditEntry(
            **base,
            timestamp=m.timestamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
            step=len(entries) + 1,
            model=m.model_name,
            tool_calls=calls,
            stop_reason=m.finish_reason,
            input_tokens=m.usage.input_tokens,
            output_tokens=m.usage.output_tokens,
        ))

    if final_output is not None and entries:
        last = entries[-1]
        for call in last.tool_calls:
            if call.tool_name == "final_result" and not (call.result or "").startswith("retry:"):
                call.result = audit.shorten(
                    f"answer: {final_output.reply} | product_ids: {final_output.product_ids}"
                )
        last.ended_run = True
        last.turn_latency_ms = latency_ms
    else:
        entries.append(AuditEntry(
            **base,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            step=len(entries) + 1,
            model=model_name(),
            stop_reason=audit.shorten(stop, 300) if stop else None,
            ended_run=True,
            turn_latency_ms=latency_ms,
        ))
    return entries


async def run_chat(
    message: str,
    history: list[ChatMessage],
    deps: ChatDeps,
    reasoning_effort: str | None = None,
    audit_context: AuditContext | None = None,
) -> AgentResult:
    """Answer one shopper message.

    Returns the reply, the full records of the products it recommends, and a TurnTrace (used by
    benchmark.py). Progress lines are sent through deps.status as the agent calls its tools.
    With an audit_context, every agent-loop step is appended to output/audit_trail.json, even
    when the run fails.
    """
    effort = reasoning_effort or default_reasoning_effort()
    started = time.perf_counter()
    calls: list[ToolCallRecord] = []
    in_flight: dict[str, tuple[ToolCallRecord, float]] = {}

    async def on_events(ctx: RunContext[ChatDeps], events: AsyncIterable[AgentStreamEvent]) -> None:
        async for event in events:
            if isinstance(event, FunctionToolCallEvent):
                args = event.part.args_as_dict()
                record = ToolCallRecord(tool=event.part.tool_name, args=args)
                calls.append(record)
                in_flight[event.part.tool_call_id] = (record, time.perf_counter())
                deps.status(status_for_tool(event.part.tool_name, args))
            elif isinstance(event, FunctionToolResultEvent):
                record, t0 = in_flight.pop(event.part.tool_call_id, (None, 0.0))
                if record:
                    record.duration_ms = round((time.perf_counter() - t0) * 1000)
                    record.result = summarize_tool_result(event.part)

    def write_audit(run_messages: list[ModelMessage], **kwargs: Any) -> None:
        if audit_context is None:
            return
        new = run_messages[len(model_history):]  # skip the earlier conversation sent as history
        latency = round((time.perf_counter() - started) * 1000)
        try:
            audit.append(loop_entries(new, audit_context, message, effort, latency_ms=latency, **kwargs))
        except Exception:  # the audit trail must never break a reply
            pass

    model_history = to_model_history(history)
    deps.status("Thinking…")
    with capture_run_messages() as run_messages:
        try:
            result = await build_agent(reasoning_effort).run(
                message,
                deps=deps,
                message_history=model_history,
                usage_limits=UsageLimits(request_limit=MAX_MODEL_REQUESTS),
                event_stream_handler=on_events,
            )
        except ModelHTTPError as error:
            if not _is_content_filter(error):
                write_audit(run_messages, stop=f"error: {type(error).__name__}: {error}")
                raise
            # The provider's content filter blocked the message: answer politely, in character.
            write_audit(run_messages, stop="content_filter")
            trace = TurnTrace(
                model=model_name(),
                reasoning_effort=effort,
                outcome="content_filter",
                duration_ms=round((time.perf_counter() - started) * 1000),
                tool_calls=calls,
            )
            return AgentResult(reply=CONTENT_FILTER_REPLY, products=[], trace=trace)
        except Exception as error:
            write_audit(run_messages, stop=f"error: {type(error).__name__}: {error}")
            raise
    output = result.output

    # A response the provider's content filter cut off mid-loop makes the rest of the run
    # unreliable (the model ends up answering an error message), so decline politely instead.
    if any(isinstance(m, ModelResponse) and m.finish_reason == "content_filter" for m in result.new_messages()):
        decline = AgentReply(reply=CONTENT_FILTER_REPLY)
        write_audit(run_messages, final_output=decline)
        trace = build_trace(result.new_messages(), calls, effort, started, result.usage)
        trace.outcome = "content_filter"
        return AgentResult(reply=CONTENT_FILTER_REPLY, products=[], trace=trace)

    products: list[Product] = []
    for product_id in dict.fromkeys(output.product_ids):  # drop duplicates, keep order
        product = db.get_product(product_id)
        if product:  # ignore any id the model made up
            products.append(product)
        if len(products) == MAX_PRODUCT_MATCHES:
            break
    trace = build_trace(result.new_messages(), calls, effort, started, result.usage)
    write_audit(run_messages, final_output=output)
    return AgentResult(reply=output.reply, products=products, results_title=output.results_title, trace=trace)
