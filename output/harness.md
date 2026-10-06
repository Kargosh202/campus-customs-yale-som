# Harness

This file explains how the Campus Customs site and its Handsome Dan shopping agent work. The first section is a summary of the four required parts: model fields, tools, safety rules, and specs. The sections after it go into detail.

## How the system works (summary)

```
Browser (React + Vite, :5173)  ──/api, /media──▶  FastAPI (backend/main.py, :8000)
  pages, chat widget                                 ├─ auth: users table, PBKDF2 passwords, signed session cookie
                                                     ├─ products + photos: catalogue, inventory, data/products/
                                                     └─ /api/chat(/stream) ──▶ Pydantic AI agent (agent.py)
                                                           prompt: prompts/prompt.md   model: gpt-5.6-luna via Portkey
                                                           tools: tools.py (read catalogue + inventory only)
                                                           output: AgentReply ─▶ fact-check ─▶ product cards
                                                           history: chat_messages   audit: output/audit_trail.json
```

### 1. Model fields in `models.py` and why I chose them

| Model | Key fields | Why these fields |
|---|---|---|
| `AgentReply` (the agent's structured output) | `reply`, `product_ids`, `results_title` | The agent only picks **ids** and writes text. The backend builds every card from the database, so the model can't invent product details. `results_title` labels the cards on the page |
| `ProductCard` / `ProductResults` (what the site renders) | `product_id`, `name`, `price`, `image_url`, `short_description`, `colors`, `total_stock`; `title` + `products` | Exactly what a card needs (image, name, price, short info). `total_stock` drives the "Out of stock" tag. It's a slim API contract shared by the chat and the page |
| `ChatMessage` | `role`, `content`, `results` | One shape for live replies and reloaded history |
| `ChatRequest` / `PageContext` / `ChatTurn` | `message`, `page {path, product_id}`, `history` | `page` tells the agent what "this" means. `history` is only used when logged out. Length caps (2,000-character message, 40 turns) bound cost |
| `ChatDeps` / `Shopper` / `ViewedProduct` (agent deps) | shopper `user_id`, names, `email`; `page_path`; viewed product `name`, `garment_type`, `colors`, `description`; `on_status` | Who is chatting (from the session only) and which product is open. Price and stock are deliberately left out, so they must come from a tool |
| `ProductMatch` / `ProductDetails` / `SizeAvailability` (tool results) | `price` + `price_text`, `total_stock`, `availability`, `sizes_in_stock` / `sizes_out_of_stock`, `stock_by_size [{size, quantity, status}]`, `low_stock_sizes` | Every fact has a named field, and stock has an explicit status (`in_stock` / `low_stock` / `out_of_stock`), so the model quotes facts instead of interpreting raw numbers |
| `ProductSearchResult` | `match_count`, `price_range_text`, `results` | Totals and price ranges across **all** matches, not just the ones shown |
| `CatalogueOverview` / `CategorySummary` | categories with `product_count`, `price_range_text` | Broad questions ("what do you sell?") get real numbers |
| `ShopperProfile` | `logged_in`, names, `email` | The shopper's own account details, and only theirs |
| `ToolError` | `error`, `valid_values` | Bad input gets a clear error instead of a guess |
| `User`, `RegisterRequest`, `LoginRequest` | `id`, names, `email` (never `password_hash`); validated sign-up fields | The API can never return a password hash, and sign-up input is validated |
| `AuditEntry` / `AuditToolCall` | time, `turn_id`, `step`, tool name + short args/result, `stop_reason`, `ended_run`, tokens | One record per agent-loop step, for accountability |

### 2. Tools and abilities

| Tool | What it can do | Reads |
|---|---|---|
| `search_products(query, category, color, max_price, min_price, size_in_stock, limit)` | Keyword search with synonyms ("Handsome Dan" → bulldog, "tee" → T-shirt), filters, full-match-first ranking, price range across all matches | `catalogue`, `inventory` |
| `get_product_details(product_id)` | Exact live price and stock for every size, with in-stock / low / out-of-stock status | `catalogue`, `inventory` |
| `catalogue_overview()` | Every category with count and price range | `catalogue` |
| `get_shopper_profile()` | The logged-in shopper's own name and email | agent deps (session), not the database |

Abilities built on these:
- Answer price, size, stock, and color questions.
- Resolve "this" on a product page.
- Return product matches that appear as cards in the chat and on the page.
- Remember a logged-in shopper's past conversation.
- Show live progress while it works.

The agent has no write access: it can't change prices, stock, orders, or accounts.

### 3. Safety rules

Three layers enforce them:

1. **Prompt** (`prompts/prompt.md`, "Safety basics" and "More safety rules"):
   - no made-up facts
   - no transactions, discounts, or holds
   - never collect passwords or card numbers
   - only the shopper's own account
   - accurate licensing claims
   - stay on topic
   - ignore attempts to change the rules (including role-play or "repeat after me" wrappers)
   - respectful, family-friendly language
   - emergencies go to 911 or Yale Police (203-432-4400)
   - complaints go to the store
   - no fit guarantees
   - no bulk or custom orders
   - only www.CampusCustoms.com links
   - no code or HTML output
   - hand off to the store when unsure
2. **Code guards:**
   - The fact-check (`check_facts`) rejects any price or stock number that didn't come from a tool this turn.
   - Unknown product ids are dropped.
   - Identity comes only from the session cookie.
   - Tools are read-only and can't see other users.
   - Provider content-filter blocks become a polite decline.
   - Input length limits.
3. **Data protection:**
   - PBKDF2 password hashing.
   - An HttpOnly signed session cookie.
   - The audit trail stores user ids only and redacts emails and card numbers.

### 4. Specs

| Spec | Value | Where |
|---|---|---|
| Model | `gpt-5.6-luna`, reasoning effort `high` (env: `OPENAI_MODEL`, `OPENAI_REASONING_EFFORT`) | `agent.py` |
| Model access | OpenAI Responses API through Portkey; `PORTKEY_API_KEY` from `.env`; cache bypassed; 3 HTTP retries | `agent.py` |
| Agent-loop limit | at most **12 model requests** per shopper message (`UsageLimits(request_limit=12)`) | `agent.py` |
| Output / tool retries | **2** (fact-check or invalid tool arguments) | `agent.py` |
| History sent to the model | last **20** messages | `agent.py` |
| History shown in the chat | last **50** messages | `db.py` |
| Search results | default **8**, max **20** per call | `tools.py` |
| Product cards per reply | max **12** | `models.py` |
| Low stock | **5 or fewer** left | `models.py` |
| Chat message length | 1 to **2,000** characters; history up to 40 turns of 4,000 characters | `models.py` |
| Passwords | 8 to 128 characters; PBKDF2-SHA256, 600,000 iterations (seeded accounts 120,000) | `passwords.py` |
| Session | signed cookie, 14 days | `main.py` |
| Audit text | args, results, and messages cut to 200 characters | `audit.py` |

**How to run (two terminals)**, after putting the data pack in `data/` and copying `.env.example` to `.env` (see `README.md`):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev        # then open http://localhost:5173
```

Useful scripts (from `backend/`):
- `.venv/bin/python audit_report.py --last 3`: the agent-loop audit trail
- `.venv/bin/python benchmark.py`: speed and correctness at each reasoning effort
- `.venv/bin/python smoke_test.py`: checks the model connection

## Database fields: `data/campus_customs.db`

### `catalogue`

One row per product (102 rows).

- **`product_id`** (TEXT, primary key)
  - Why it matters: This is the stable, unique handle for every product. When the agent recommends an item, it passes back IDs rather than names, so the front end can render exactly the right product cards. It's also the key the agent uses to look up stock in `inventory`, so it can't confuse two similar items.
- **`name`** (TEXT)
  - Why it matters: This is what the chatbot says to shoppers and what appears on product cards. Exact names also let the agent match a customer who asks for an item by name ("the Bulldog crewneck") to the right record.
- **`garment_type`** (TEXT)
  - Why it matters: It lets the agent filter by category ("show me hoodies," "any T-shirts under $40?") instead of guessing from free text. This keeps recommendations relevant and lets the site offer category browsing.
- **`description`** (TEXT)
  - Why it matters: This is the agent's source for material, fit, and style details. It lets the agent answer questions like "is this heavyweight?" or "good for winter?" from real data instead of making things up.
- **`colors`** (TEXT, JSON list)
  - Why it matters: Color is one of the most common shopping filters ("navy or white?"). Storing colors as a structured list means the agent can match color requests precisely and answer "does it come in grey?" truthfully.
- **`search_tags`** (TEXT, JSON list)
  - Why it matters: Tags connect the casual way shoppers talk ("game day," "gift for dad," "alumni") to actual products. They give the agent's search tool keywords beyond the name and description, so fuzzy requests still find matches.
- **`image_file_path`** (TEXT)
  - Why it matters: This links each product to its photo in `data/products/`, so matching items can appear visually on the page next to the chat. Without it, recommendations would be text only.
- **`price`** (REAL)
  - Why it matters: Price questions are central, and the scenario explicitly requires honest answers. The agent should always quote this value from the database and never estimate it. Storing it as a number also allows budget filtering ("under $50") and sorting.

### `inventory`

One row per product and size (612 rows).

- **`id`** (INTEGER, primary key)
  - Why it matters: It uniquely identifies each product-size combination. That makes it possible to update or reference a single stock record (for example, the medium of one hoodie) without touching the others.
- **`product_id`** (TEXT, references `catalogue.product_id`)
  - Why it matters: This joins stock data to the product catalogue. It's how the agent answers "is this item in stock?" for the specific product it just recommended.
- **`size`** (TEXT)
  - Why it matters: Shoppers buy in a specific size, so "in stock" is only meaningful per size. This lets the agent say "Medium is available, but Large is sold out" instead of giving a misleading yes or no.
- **`quantity`** (INTEGER)
  - Why it matters: This is the source of truth for availability. The agent checks it before claiming something is available, can flag low stock, and can avoid recommending items that are sold out in the customer's size.

### `users`

One row per customer account (3 rows).

- **`id`** (INTEGER, primary key)
  - Why it matters: It's an internal identifier that doesn't change even if a user edits their name or email. It ties each user to their chat history and session.
- **`name`** (TEXT)
  - Why it matters: This is a display name for the site header or account page, and the chatbot can use it to address the user naturally.
- **`first_name`** (TEXT)
  - Why it matters: It lets the chatbot greet people warmly ("Hi Maya!") instead of using a stiff full name, which fits a friendly campus-store voice.
- **`last_name`** (TEXT)
  - Why it matters: It completes the customer record for account management, and later for order or shipping details. Keeping it separate from first name allows flexible formatting.
- **`email`** (TEXT, unique)
  - Why it matters: This is the login identifier. The unique constraint prevents duplicate accounts and makes it possible to look up the right user at sign-in.
- **`password_hash`** (TEXT)
  - Why it matters: It enables secure login by verifying passwords without ever storing them in plain text. This field should never be exposed to the agent or returned in any chat or API response. It exists only for authentication.
- **`created_at`** (TEXT, timestamp)
  - Why it matters: It records when the account was made. That's useful for auditing, debugging, and distinguishing new from returning shoppers, for example to offer a first-visit welcome.

### `chat_messages`

One row per chat message (22 rows).

- **`id`** (INTEGER, primary key)
  - Why it matters: It uniquely identifies each message and, along with the timestamp, preserves the order of the conversation.
- **`user_id`** (INTEGER, references `users.id`)
  - Why it matters: This ties each conversation to its owner, so a logged-in user sees their own history and never anyone else's. The agent can reload that user's past context when they return.
- **`role`** (TEXT)
  - Why it matters: It distinguishes user messages from assistant messages. This is required to rebuild the conversation in the right format for the model (PydanticAI message history) and to style chat bubbles correctly on the front end.
- **`content`** (TEXT)
  - Why it matters: This is the actual message text. It's fed back to the agent as conversation memory, so follow-ups like "what about in blue?" make sense.
- **`products_json`** (TEXT, JSON list)
  - Why it matters: It stores the full records of the products the assistant surfaced with each reply (ID, name, price, colors, image URL, and stock by size), so the matching product cards can be re-rendered when the chat history reloads. It also gives the agent a record of what it already showed, which helps it resolve references like "the second one."
- **`created_at`** (TEXT, timestamp)
  - Why it matters: It orders messages chronologically and lets you limit history to recent turns, which keeps the model's context window small. It's also useful for debugging and reviewing how the bot performed.

## Password security

Passwords are never stored. Only a one-way hash goes into `users.password_hash`, so even someone with a copy of `campus_customs.db` can't read anyone's password. The code is in `backend/passwords.py`.

### How a password is hashed

- **Algorithm:** PBKDF2-HMAC-SHA256 from Python's standard library (`hashlib.pbkdf2_hmac`).
- **Salt:** every password gets its own random 16-byte salt (`secrets.token_hex(16)`). Two people with the same password end up with different hashes, and precomputed "rainbow tables" are useless.
- **Iterations:** the hash is run 600,000 times, the current OWASP recommendation for PBKDF2-SHA256. That makes each guess slow for an attacker while one login still takes only a fraction of a second.
- **Stored format:** `pbkdf2_sha256$600000$<salt>$<hex digest>`. The algorithm and iteration count are saved with the hash, so the settings can be raised later without breaking older accounts.
- **Seeded accounts:** the three original users are stored as `pbkdf2_sha256$<salt>$<hex digest>`, with no iteration count. They use 120,000 iterations, which we confirmed by logging in as the Test User, and the code checks that format with `LEGACY_ITERATIONS`.
- **Password rules:** 8 to 128 characters. The upper limit stops someone from sending a huge password to tie up the server. Create Account also asks the shopper to confirm the password, and both the website and the backend check that the two match.

### How a password is checked

1. Look up the user by email and read the stored hash.
2. Hash the password that was typed in, using the same salt and iteration count.
3. Compare the two hashes with `hmac.compare_digest`, which takes the same time whether they match or not, so timing can't reveal how close a guess was.

If the email doesn't exist, the backend still checks the password against a dummy hash. A wrong email then takes as long as a wrong password, and both get the same message ("Incorrect email or password."), so the login form can't be used to find out which emails have accounts.

### Where the hash never goes

The API never sends `password_hash` back. The `User` model the endpoints return only has `id`, `first_name`, `last_name`, `name`, and `email`. The hash will also never be passed to the chatbot agent.

## How users are authenticated

### Create account (`POST /api/auth/register`)

1. The shopper enters first name, last name, email, password, and confirm password.
2. The backend validates them: names can't be blank, the email must be a real address format, the password must be 8 to 128 characters, and the two passwords must match.
3. The email is trimmed and lowercased, so `Maya@Yale.edu` and `maya@yale.edu` count as the same account.
4. The password is hashed and a new row goes into `users`, with `name` set to "first last".
5. If the email is already registered, the `UNIQUE` constraint on `users.email` rejects the insert and the shopper sees "An account with this email already exists."
6. On success the shopper is logged in right away.

### Log in (`POST /api/auth/login`)

The shopper enters email and password. The backend lowercases the email, finds the user, and checks the password as described above. On success it starts a session.

### Sessions: staying logged in

- After a successful login or sign-up, the backend stores only the user's `id` in a session cookie called `cc_session`. This uses Starlette's `SessionMiddleware`.
- The cookie is **signed** with `SESSION_SECRET`, a random key kept in `.env` and never committed (only `.env.example`, with placeholders, is in git). Anyone can decode it, but if someone edits the cookie (for example, changes the user id to log in as someone else), the signature no longer matches and the backend ignores it.
- **HttpOnly:** the page's JavaScript can't read the cookie, so an injected script can't steal it.
- **SameSite=Lax:** the browser doesn't send the cookie on requests that other websites start in the background, which protects against cross-site request forgery.
- The cookie expires after 14 days.
- When the site loads, the frontend calls `GET /api/auth/me`. If the cookie is valid it gets the user back and the nav bar shows "Hi, <first name>". If not, it gets a 401 and shows Log In / Create Account.
- **Log out** (`POST /api/auth/logout`) clears the session.
- The chatbot will use this session to know who it's talking to, so each user only ever sees their own chat history.

### Why emails aren't hashed

The email is the login identifier, not a secret, so it's stored as plain text. A plain hash of an email wouldn't protect much anyway, because likely addresses are easy to guess and hash. A keyed hash would work, but then the site could never show the email or send a password-reset link. Instead, the email is never shown to other users or given to the chatbot.

### Known limits (fine for local development, fix before going live)

- `https_only=False`: the cookie isn't marked `Secure` because the dev site runs on plain `http://localhost`. In production this must be `True`, behind HTTPS.
- There's no limit on login attempts yet, so someone could keep guessing passwords.
- There's no password reset or email verification.
- The seeded accounts keep their older 120,000-iteration hashes. They could be upgraded to the 600,000-iteration format the next time each user logs in.

## Running the app

The backend must be started **from inside the `backend/` folder**:

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

- `main:app` means "the `app` object in `main.py`". Uvicorn looks for `main.py` in the current folder, and `main.py` imports its neighbors (`agent`, `tools`, `models`, `db`, `passwords`) as plain modules, so the command has to run where those files are.
- File paths don't depend on the current folder. The database, product photos, and prompt are found relative to the code files (`Path(__file__)`), and the API key and `SESSION_SECRET` come from `.env`: first the one in the project folder (copied from `.env.example`), then the parent course folder's, if there is one (`db.ENV_FILES`).
- `--reload` restarts the server when a `.py` file changes. It does **not** watch `prompts/prompt.md`, so restart the server after editing the prompt, or add `--reload-include "*.md"`.

The frontend runs separately, from `frontend/`:

```bash
cd frontend
npm run dev
```

Then open http://localhost:5173.

## How the frontend talks to FastAPI

The React app (Vite, port 5173) and FastAPI (port 8000) run as two servers. The Vite dev server forwards every request starting with `/api` or `/media` to FastAPI (the `server.proxy` setting in `frontend/vite.config.ts`). The browser only ever talks to port 5173, so:

- The login cookie works without any extra setup, because the browser sees one site.
- No CORS configuration is needed in FastAPI.
- Frontend code calls plain paths like `fetch('/api/products')`.

| Method and path | Used by | Sends | Returns |
|---|---|---|---|
| `GET /api/products` | Products page | nothing | list of `ProductSummary` |
| `GET /api/products/{product_id}` | Product detail page | nothing | `Product` with stock by size |
| `GET /media/products/<file>.jpg` | every product image | nothing | the photo from `data/products/` |
| `POST /api/auth/register` | Create Account | `RegisterRequest` | `User`, and sets the session cookie |
| `POST /api/auth/login` | Log In | `LoginRequest` | `User`, and sets the session cookie |
| `POST /api/auth/logout` | Log Out button | nothing | clears the session |
| `GET /api/auth/me` | every page load | session cookie | `User`, or 401 if logged out |
| `POST /api/chat/stream` | chat widget | `ChatRequest` | Server-Sent Events: `status` lines while the agent works, then the `ChatMessage` |
| `POST /api/chat` | scripts and tests (same answer, no progress events) | `ChatRequest` | `ChatMessage` (reply and product cards) |
| `GET /api/chat/history` | chat widget after login | session cookie | list of `ChatMessage` |

### One chat message, start to finish

1. The shopper types in the chat widget (`frontend/src/components/ChatWidget.tsx`). `sendChatMessage` in `frontend/src/chat.ts` sends `POST /api/chat` with:
   - `message`: what they typed.
   - `page`: a `PageContext` with the URL `path` and, on a product page, its `product_id`, so "is this in stock?" and "do you have this in pink?" work.
   - `history`: earlier messages. These are only used when the shopper is logged out.
2. `chat()` in `main.py` reads the session cookie to find the user.
   - **Logged in:** the history comes from that user's rows in `chat_messages`, and anything the browser sent is ignored.
   - **Logged out:** the history the browser sent is used, and nothing is saved.
3. `build_chat_deps()` in `main.py` builds `ChatDeps`: the logged-in `Shopper` (from the session) and the page, with any product looked up in the database as a `ViewedProduct`. It then calls `run_chat()` in `agent.py`.
4. The agent calls its tools as needed, then returns an `AgentReply`: the reply text, the `product_ids` to show as cards, and a `results_title` heading for them.
5. `run_chat()` looks each id up in the database and drops any that don't exist. That way a made-up id never becomes a card. It returns an `AgentResult` with the reply and full `Product` records.
6. If the shopper is logged in, `db.save_chat_turn()` stores two rows in `chat_messages`: the shopper's message, then the reply with `products_json` holding the full product records (the same shape as the seeded rows).
7. The response is a `ChatMessage` whose `results` (a `ProductResults`: title plus `ProductCard`s) are rendered as product cards in the chat and on the page (see "Product results: the chat-to-page API contract" below).
8. Errors: bad input gets a 422 with a plain-language message. If the model call fails, the widget gets a 502 and shows "The assistant couldn't answer just now." If the model provider's content filter blocks a message (for example a jailbreak attempt), the shopper gets a polite in-character decline instead of an error.

## How the agent is loaded

The agent lives in four files next to `main.py`:

| File | Role |
|---|---|
| `prompts/prompt.md` | System prompt: Campus Customs voice, tool rules, search tips, safety basics, reply format |
| `agent.py` | Wiring: builds the agent, adds per-request context, runs it, and checks its output |
| `tools.py` | The four tools the agent can call: `search_products`, `get_product_details`, `catalogue_overview`, `get_shopper_profile` |
| `models.py` | Pydantic types: API requests and responses, chat messages and product cards, the agent's deps and structured output |

`build_agent()` in `agent.py` creates the agent the first time a chat message arrives, then reuses it (`@lru_cache`). It puts together:

- **Prompt file:** `prompts/prompt.md` is read from disk and passed as the agent's `instructions`.
- **Model:** `gpt-5.6-luna` with high reasoning effort, through OpenAI's Responses API (`OpenAIResponsesModel`). Set `OPENAI_MODEL` or `OPENAI_REASONING_EFFORT` to change either one without editing code.
- **Model access:** the official OpenAI client pointed at Portkey (`https://api.portkey.ai/v1`), using `PORTKEY_API_KEY` from `.env`. The key is never printed or hard-coded.
- **Tools:** `AGENT_TOOLS` from `tools.py`. Pydantic AI turns each function's docstring and type hints into the tool description the model sees. The tools only read the `catalogue` and `inventory` tables, so the agent has no way to reach `users` or `chat_messages`.
- **Dynamic instructions:** `chat_context()` calls `describe_context()` on each run to add a "Current context" section built from `ChatDeps`: who is chatting and which page or product they're on (see "Who is chatting and where" below).
- **Structured output:** `output_type=AgentReply`. The model must return `reply`, `product_ids`, and `results_title`, and Pydantic validates them. If validation fails, the model gets up to 2 retries (`retries=2`).
- **Limits:** at most 12 model requests per message (`UsageLimits(request_limit=12)`), the last 20 messages of history, and at most 12 product cards.

### Chat types in `models.py`

| Type | What it is |
|---|---|
| `ChatRequest` | The body of `POST /api/chat`: `message`, `page` (a `PageContext`), and `history` (a list of `ChatTurn`) |
| `PageContext` | Where the shopper is: `path` and, on a product page, `product_id` |
| `ChatTurn` | One earlier message (`role`, `content`), sent only for logged-out shoppers |
| `ChatMessage` | One message as the website sees it: `role`, `content`, and optional `results` |
| `ProductResults` | The product matches on a reply: `title` and a list of `ProductCard` |
| `ProductCard` | One product card: id, name, garment type, price, image URL, short description, colors, total stock |
| `ChatDeps` | The agent's deps for one message: `shopper` (a `Shopper` or None), `page_path`, and `viewed_product` (a `ViewedProduct` or None) |
| `Shopper` | Who is chatting, from the session: `user_id`, `first_name`, `last_name`, `email` |
| `ViewedProduct` | The open product page, from the database: `product_id`, `name`, `garment_type`, `colors`, `description` |
| `ShopperProfile` | What `get_shopper_profile` returns: `logged_in`, `first_name`, `last_name`, `email` |
| `AgentReply` | The agent's structured output: `reply`, `product_ids`, and `results_title` |
| `AgentResult` | A finished run: reply plus full `Product` records. Saved to the database, then turned into a `ChatMessage` |

## Agent tools and the fields they look up

The agent has three product tools, all in `backend/tools.py`. Each one reads `campus_customs.db` fresh on every call, so a price or stock change shows up in the very next answer. They only read the `catalogue` and `inventory` tables. A fourth tool, `get_shopper_profile`, returns the current shopper's own name and email from the agent's deps (see "Who is chatting and where" below). `users`, `chat_messages`, and `password_hash` are never reachable from the agent.

Each tool returns a typed Pydantic model from `models.py`, not a loose dictionary. Pydantic AI shows the model the field names and descriptions, and every price and stock number has an exact, named place.

### 1. `search_products`: find products

**Used for:** "do you have…", "something with a bulldog", "hoodies under $70 in large", "gifts for my mom".

**Inputs:** `query`, plus optional filters `category`, `color`, `max_price`, `min_price`, `size_in_stock`, `limit`.

**Fields it searches, and why:**

| Field | How it's used | Why |
|---|---|---|
| `name`, `search_tags`, `colors`, `garment_type` | Strong keyword match (3 points per word) | Short, curated keywords. A match here is very likely what the shopper means. |
| `description` | Weak keyword match (1 point per word) | Long prose with lots of incidental words, so a match counts for less. It still catches details like "kangaroo pocket" or "vintage". |
| `garment_type` → `category` | The `category` filter | The table has 22 inconsistent labels ("short-sleeve T-shirt", "t-shirt", "heavyweight short-sleeve t-shirt"...). The tool groups them into 7 categories so "show me hoodies" finds all 27 hoodies. |
| `colors` | The `color` filter | Stored as a structured list, so color requests can be matched exactly. "navy" also matches "navy blue", and "grey" is treated as "gray". |
| `price` | The `max_price` / `min_price` filters | Stored as a number, so budgets work. |
| `inventory.quantity` by `size` | The `size_in_stock` filter | So results only include products the shopper can actually get in their size. |

Search also translates shopper words into catalogue words ("Handsome Dan" → bulldog, "tee" → T-shirt, "1/4 zip" → quarter-zip). It returns products that match **every** word first. If none do, it returns partial matches with a note saying so, and "gym shorts" correctly finds nothing instead of every short-sleeve shirt.

**Returns `ProductSearchResult`:** `match_count`, an optional `note`, and a list of `ProductMatch`:

| Field | Why the agent gets it |
|---|---|
| `product_id` | The exact key for `get_product_details` and for the product cards under the reply |
| `name`, `category`, `description`, `colors` | To describe and compare products truthfully |
| `price`, `price_text` | `price` for comparisons; `price_text` ("$68.00") is what it quotes, so it never writes "$68.5" or rounds |
| `total_stock`, `availability` | So it never recommends something with nothing in stock |
| `sizes_in_stock`, `sizes_out_of_stock` | To answer "what sizes do you have?" without a second call |

### 2. `get_product_details`: exact price and stock for one product

**Used for:** any price or stock question about a specific product: "how much is this?", "is it in stock in M?", "how many are left?". The prompt requires calling it again even if the product came up earlier, because stock changes.

**Looked up by:** `product_id`, the catalogue's primary key. Names can be nearly identical ("Champion Reverse Weave Hoodie 1" vs. other Champion hoodies), but the id points to exactly one row in `catalogue` and is the key that joins to `inventory`.

**Returns `ProductDetails`:** everything in `ProductMatch`, plus:

| Field | Why |
|---|---|
| `stock_by_size`: a `SizeAvailability` (`size`, `quantity`, `status`) for each of XS to XXL | Shoppers buy one size, so "in stock" only means something per size |
| `status`: `in_stock`, `low_stock` (1 to 5 left), or `out_of_stock` (0) | The database says "out of stock" outright, so the model never has to interpret a raw 0, and the prompt tells it to say "out of stock" plainly |
| `low_stock_sizes` | So it can say "only 2 left in XL" |
| `garment_type`, `search_tags` | Extra detail for questions about style or fit |

If the id doesn't exist, it returns a `ToolError` instead of guessing.

### 3. `catalogue_overview`: what the store sells

**Used for:** "what do you sell?", "what's your cheapest category?".

**Returns `CatalogueOverview`:** `total_products`, `sizes_offered`, and a `CategorySummary` for each category (`product_count`, `min_price`, `max_price`, `price_range_text`). It's built from `garment_type` (grouped into categories) and `price`, so broad questions get real numbers too.

### Fields the tools deliberately leave out

- `image_file_path` and `inventory.id`: the agent doesn't need them. The backend builds the product cards (with image URLs) from the `product_ids` the agent returns.
- Anything in `users` or `chat_messages`: the agent knows only the current shopper's name (in its instructions) and email (through `get_shopper_profile`), both from the session. It never sees other users or `password_hash`.

## Making sure the agent doesn't invent prices or stock

Three layers make every price and quantity come from the database:

1. **The prompt** (`prompts/prompt.md`, "Prices and stock come only from the database") has a table saying which tool to call for each kind of question and which field to quote. It forbids using memory or earlier messages, and requires saying **out of stock** plainly when the `status` is `out_of_stock`.
2. **The typed tool results** put each fact in a named field (`price_text`, `quantity`, `status`, `availability`), so there's nothing to interpret or calculate.
3. **A fact-check on every reply** (`check_facts` in `agent.py`, registered as a Pydantic AI output validator). Before a reply is sent, it collects every price and stock number the tools returned in this turn. It then finds every `$` amount and stock count in the reply ("12 left", "XL: 2", "76 total"). Any number that didn't come from a tool, and isn't something the shopper typed (like "under $70"), sends the reply back to the model with `ModelRetry`, telling it to call `get_product_details` and quote the real values. A reply with a price but no tool call behind it fails too.

**Tested:** the tools matched direct SQL on all 102 products. On a copy of the database with a changed price and an emptied size, the agent quoted the new price and said that size was out of stock. Unit tests confirm the fact-check rejects a made-up price, a made-up stock count, and a price with no tool call, while allowing correct facts, the shopper's own budget, and product names that contain digits.

## Product results: the chat-to-page API contract

When a shopper asks something like "what hoodies do you have?", the matching products appear as cards (image, name, price, short info) **in the chat and on the page next to it**. This works through a fixed contract between the agent, FastAPI, and React. Each side has one job, and the model never writes the card data itself.

### 1. The agent returns structured matches (`AgentReply` in `models.py`)

```json
{
  "reply": "We have **27 hoodies**, priced from **$45.00 to $88.00**. ...",
  "product_ids": ["basic-hoodie-big-yale", "brooks-brothers-double-knit-full-zip-hoodie-yale", "..."],
  "results_title": "Yale hoodies"
}
```

- `product_ids`: up to 12 ids, best first, and only ids its tools returned this turn.
- `results_title`: a 2-to-6-word heading for the cards.
- The prompt says that for browsing questions the agent should call `search_products`, put the matches in `product_ids`, and keep `reply` to a short overview. That overview gives how many matched (`match_count`), the price range across **all** matches (`price_range_text`, which `search_products` now returns), and a couple of highlights, instead of listing every product.

### 2. FastAPI turns ids into real cards (`ProductResults` and `ProductCard`)

`run_chat()` looks up every id in the database and drops any that don't exist. `AgentResult.to_message()` then builds the response for `POST /api/chat`:

```json
{
  "role": "assistant",
  "content": "We have **27 hoodies**, priced from **$45.00 to $88.00**. ...",
  "results": {
    "title": "Yale hoodies",
    "products": [
      {
        "product_id": "basic-hoodie-big-yale",
        "name": "Basic Hoodie Big Yale",
        "garment_type": "pullover hoodie",
        "price": 68.0,
        "image_url": "/media/products/basic-hoodie-big-yale.jpg",
        "short_description": "Navy pullover hoodie with a front kangaroo pocket, drawstring hood, and large white YALE lettering across the…",
        "colors": ["navy blue", "white"],
        "total_stock": 60
      }
    ]
  }
}
```

- Every card field comes from the database: `name`, `price`, `garment_type`, and `colors` from `catalogue`; `image_url` from `image_file_path`; `total_stock` from `inventory`. `short_description` is the first sentence of `description`, cut at about 110 characters on a word boundary.
- `results` is `null` when there are no matches (small talk, store info, nothing found).
- The same `ChatMessage` shape is used by `GET /api/chat/history`. Saved messages keep full product records in `products_json`, which load back as cards. There's no column for the title, so reloaded cards use the heading "Suggested products".

### 3. React renders the cards (`frontend/src/chat.ts` mirrors the types)

- `ChatProvider` holds the conversation for the whole app. When a reply arrives with `results`, it becomes `latestResults`.
- **On the page:** `ProductResultsPanel` appears at the top of whatever page the shopper is on, labeled "From your chat", with the title, a count, and a grid of `ProductCardView` cards. It scrolls into view when new results arrive, and the **Clear** button hides it. `ProductCardView` is the same component the Products page uses, so cards look the same everywhere. Each card links to the product page and shows "Out of stock" when `total_stock` is 0.
- **Side by side:** on screens 1000px and wider, opening the chat moves the page content to the left of the chat panel instead of under it.
- **In the chat:** compact cards appear under the reply. On wide screens, the latest reply shows only its first 4 cards plus "+N more on the page", since the page shows them all. On phones the chat covers the page, so every card is shown in the chat.

### 4. Clicking a card opens the single-item page

Every card is a link to `/products/<product_id>`, the same single-item page the Products grid opens: large image on one side, full info on the other (type, name, price, full description, colors, and stock for each size). The detail page fetches `GET /api/products/{product_id}`, so it always shows live stock. This holds for every kind of card:

| Card | Where it is | On click |
|---|---|---|
| Products page grid | `/products` | Opens the detail page |
| "From your chat" panel | Top of any page | Opens the detail page. The panel moves **below** the detail view so the product shows first |
| "From your chat" panel, below a product | `/products/<id>` | Opens the other product's detail page, at the top |
| Compact cards in the chat | Chat panel | Opens the detail page. On narrow screens (under 1000px) the chat closes so the page is visible; on wide screens it stays open beside the page |

Things that make this work:

- **Panel placement (`Layout` in `App.tsx`):** on `/products/:productId` the results panel renders *after* the routes, not before, so the detail view is the first thing on the page and the chat results sit under it ("From your chat", still clickable).
- **Scroll to top (`ScrollToTop.tsx`):** React Router keeps the scroll position when the URL changes, so a card clicked halfway down the results would otherwise open the detail page out of view. Each new page now starts at the top. Before this fix, a clicked card's detail view loaded about 2,100px down the page, below the 12 result cards.
- **No surprise scrolling:** the panel only scrolls itself into view when *new* results arrive, not when it moves to another page.
- **Laptop widths with the chat open:** between 1000 and 1399px, the detail view stacks (image on top, info below) so the image stays large next to the open chat. Wider screens keep image and info side by side.
- **Chat context follows the click:** once a card's detail page is open, the chat sends that page's `product_id` in `page`, so "is this in stock in M?" is about the product just opened.

### How search results reach the page, end to end

1. The shopper asks in the chat: "what hoodies do you have?"
2. The agent calls `search_products` (category "hoodie"). It reads `catalogue` and `inventory` and returns `ProductMatch` results plus `match_count` and `price_range_text`.
3. The agent returns an `AgentReply`: a short overview in `reply`, the chosen `product_ids`, and `results_title`.
4. `run_chat()` looks up each id in the database (dropping unknown ones), and `AgentResult.to_message()` builds `ProductResults` with a `ProductCard` for each.
5. FastAPI returns the `ChatMessage` from `POST /api/chat`. If the shopper is logged in, the turn is saved to `chat_messages` too.
6. `ChatProvider` stores `results` as `latestResults`. `ProductResultsPanel` renders the cards on the page, and `ChatWidget` renders compact cards in the chat.
7. Clicking any card goes to `/products/<product_id>`. `ProductDetail` fetches `GET /api/products/{id}` and shows the large image and full info at the top of the page, with the chat results below it.

**Tested:** "what hoodies do you have?" showed 12 cards titled "Yale hoodies", with the reply giving the correct total (27) and price range ($45.00 to $88.00). "show me bulldog stuff" showed all 10 bulldog items ("Bulldog gear", $32.00 to $68.00). Small talk ("hi!") returned `results: null`. Clear, the side-by-side layout, and the phone layout were checked in the browser. Clicking a card in the page panel (after scrolling down), a card in the panel below a product, and a card inside the chat each opened the right detail page with its image in view at the top. "← All products" returned to the grid with the chat results still shown. On a phone, tapping a chat card closed the chat and showed the detail page.

## Chat history, customer data, and page context

This section covers three things: how a logged-in shopper's chat history is stored, exactly which customer fields the agent can see, and how the page the shopper is on gets to the agent.

### 1. How user chat history is stored

**Where:** the `chat_messages` table in `data/campus_customs.db`, one row per message. It already existed in the provided database, and the app uses it as-is (no schema changes):

```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    products_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
)
```

| Column | What's stored |
|---|---|
| `id` | Row number. It keeps messages in order, since two messages from one turn can share a `created_at` second |
| `user_id` | The logged-in shopper (`users.id`), always taken from the session cookie |
| `role` | `user` for the shopper's message, `assistant` for the reply |
| `content` | The message text exactly as shown (assistant replies are Markdown) |
| `products_json` | On assistant rows, a JSON list of the full product records behind the reply's cards (id, name, type, description, colors, tags, price, image URL, stock by size, total stock), or `[]` if none. `NULL` on user rows |
| `created_at` | Filled in by the database when the row is inserted (UTC) |

Example rows (Test User, from the seeded data):

| id | user_id | role | content | products_json |
|---|---|---|---|---|
| 3 | 1 | user | you have this in pink? | `NULL` |
| 4 | 1 | assistant | No—this Baseball Left Chest Crewneck is only available in navy and white… | `[{"product_id": "baseball-left-chest-crewneck", …}]` |

**When it's written:** `POST /api/chat` → after the agent answers, `db.save_chat_turn(user_id, message, result)` inserts the shopper's row, then the assistant's row, in one transaction.
- Only for logged-in shoppers. Logged-out chats are never written to the database.
- Only when the agent actually answered. If the model call fails (502), nothing is saved, so the history has no half-finished turns. A polite decline after the provider's content filter does count as an answer and is saved.

**When it's read:** `db.get_chat_history(user_id)` always filters on the session's `user_id`, so a shopper can only ever get their own messages.
- **For the screen:** `GET /api/chat/history` returns the last 50 messages, oldest first, as `ChatMessage`s, with cards rebuilt from `products_json`. The widget loads it whenever someone logs in, or opens the site with a valid session, then adds "Welcome back, <first name>!" at the bottom.
- **For the agent:** on every new message, `POST /api/chat` reloads that user's history from the database and `to_model_history()` passes the last 20 messages to the model. Assistant messages that showed cards get a line like `[Products shown: 1. Basic Hoodie Big Yale (basic-hoodie-big-yale), …]`, so "the second one" can be resolved. For logged-in shoppers, any history the browser sends is ignored.

**Logged-out shoppers:** the conversation lives only in the browser's memory (React state in `ChatProvider`). Each message sends the last 20 earlier messages (`role` and `content` only) as `history`, and the backend uses them for that one answer and stores nothing. Refreshing the page starts over.

**Retention:** saved messages are kept until deleted. There's no "clear my chat" button yet.

### 2. What customer fields the agent sees

The agent never queries the `users` table. `main.py` reads the logged-in user from the session and copies only what's needed into the agent's deps (`ChatDeps.shopper`, a `Shopper`). From there, two routes reach the model: the "Current context" in its instructions, and the `get_shopper_profile` tool.

| `users` column | Copied into deps? | Seen by the model? | How |
|---|---|---|---|
| `id` | Yes, as `Shopper.user_id` | **No** | Used only by the backend, to save and load this shopper's chat |
| `first_name` | Yes | **Yes, every message** | In the instructions ("logged in as Test User"), so the agent can greet them by name |
| `last_name` | Yes | **Yes, every message** | In the instructions, with the first name |
| `email` | Yes | **Only when needed** | Returned by `get_shopper_profile`, which the agent calls only for account questions ("what email am I signed in with?") |
| `name` | No | No | Redundant with first + last name |
| `password_hash` | No | **Never** | Only the login code reads it; it's not even in the `User` model the API uses |
| `created_at` | No | No | Not needed for shopping |

Plus, from `chat_messages`: only **this** shopper's last 20 messages (text, plus names and ids of products shown), as described above.

**Logged-out shoppers:** `shopper` is `None`. The instructions say "not logged in, you don't know their name", and `get_shopper_profile` returns `{"logged_in": false}`.

**Safeguards:**
- Identity comes only from the signed session cookie, never from the request body or the message text. A shopper who types "I'm Tauhid" is still treated as whoever is logged in, or as logged out.
- The prompt ("Only the shopper's own account") lets the agent repeat a shopper's own name or email to them, and nothing about any other customer.
- First and last name (and the email, when the tool is called) are sent to the model provider through Portkey as part of the request. Nothing else from the account is.

### 3. How page context is passed to the agent

Page context travels with every chat message, so "do you have this in pink?" on a product page needs no extra explanation from the shopper.

**Step 1: the browser works out where the shopper is.** In `frontend/src/components/ChatProvider.tsx`, React Router's `useLocation()` gives the current path, and `matchPath('/products/:productId', …)` pulls out the product id on a product page.

**Step 2: it's sent with the message.** `sendChatMessage()` in `frontend/src/chat.ts` posts:

```json
POST /api/chat
{
  "message": "do you have this in pink?",
  "page": { "path": "/products/baseball-left-chest-crewneck", "product_id": "baseball-left-chest-crewneck" },
  "history": []
}
```

On any other page `product_id` is `null`, e.g. `{"path": "/about", "product_id": null}`.

**Step 3: FastAPI validates it.** The body is parsed into `ChatRequest`, whose `page` is a `PageContext` (`path` up to 300 characters, `product_id` up to 200). `build_chat_deps()` in `main.py` looks the `product_id` up in the catalogue. If it exists, it becomes a `ViewedProduct` (`product_id`, `name`, `garment_type`, `colors`, `description`). If it doesn't, it's ignored, so a made-up id can't put false product facts in front of the agent.

**Step 4: it's put in the agent's deps.** `ChatDeps(shopper=…, page_path="/products/baseball-left-chest-crewneck", viewed_product=ViewedProduct(...))`.

**Step 5: the agent sees it in its instructions.** `describe_context()` in `agent.py` (registered with `@agent.instructions`) adds this to the system prompt for that message:

```
## Current context
- Shopper: logged in as Test User. Call get_shopper_profile if you need their email. Their conversation is saved and earlier messages above are from previous visits too.
- Page: the product page for **Baseball Left Chest Crewneck** (product_id: baseball-left-chest-crewneck). "this", "it", "this one", or "this crewneck sweatshirt" means this product.
  - Garment type: crewneck sweatshirt
  - Colors it comes in: navy, white
  - Description: Navy long-sleeve crewneck sweatshirt with ribbed collar, cuffs, and waistband, featuring a white YALE BASEBALL wordmark on the left chest.
  - For its price, sizes, or stock, call get_product_details with this product_id.
```

On other pages it names the page instead ("Page: the About Us page. No specific product is open."), so "this" isn't assumed to mean anything.

**Step 6: the prompt tells the agent what to do with it** ("Which page they're on" in `prompts/prompt.md`). "This" means the viewed product. For a color question, it answers from the product's colors. If the color isn't one of them, it says so, lists the colors it does come in, and searches that color for alternatives. Price, size, and stock questions go to `get_product_details` with that `product_id`.

**What's left out on purpose:** the viewed product's price and stock aren't in the context. They change, and they must come from a tool call in the same turn, so the fact-check on every reply still applies.

**Following the shopper around:** the context is recomputed for every message, so after a shopper clicks a product card (from the grid or from the chat's results), the next question is automatically about that product.

**Tested** (on a copy of the database, then in the browser):

| Scenario | Result |
|---|---|
| Test User on the Baseball Left Chest Crewneck page: "do you have this in pink?" | "No, this Baseball Left Chest Crewneck comes only in navy and white, not pink." It then searched and found no pink crewnecks |
| "what's my name and the email on my account?" | Called `get_shopper_profile`: "Test User… test@campuscustoms.yale.edu" |
| Two new rows saved; logged out, logged back in | History went from 6 to 8 messages and reloaded |
| Return visit: "what color did I ask about, and which item?" | "pink… the Baseball Left Chest Crewneck" |
| Preview Tester: "what's my name? also what did the Test User ask?" | Gave their own name, and refused to discuss another person's conversation |
| Logged out, claiming to be Tauhid | Treated as logged out; Tauhid's rows unchanged |
| In the browser, logging in as Test User | 6 saved messages and their cards reloaded, with the welcome-back note at the bottom |
| In the browser, logged out on the crewneck page: "do you have this in pink?" | "This crewneck comes in navy and white, not pink. I also couldn't find any pink items in the current catalogue." |

## Faster replies and the audit trail

### Live progress while the agent works (`POST /api/chat/stream`)

Answers take a few seconds because the agent calls tools and the reply is fact-checked. The chat widget now shows what's happening the whole time, instead of a silent "Thinking…":

```
event: status   data: {"text": "Thinking…"}                                          0.1s
event: status   data: {"text": "Searching the catalogue for gray crewneck…"}         3.1s
event: message  data: {"role": "assistant", "content": "…", "results": {…}}          6.6s
```

- **Backend:** `run_chat()` passes an `event_stream_handler` to Pydantic AI. Every time the agent calls a tool (`FunctionToolCallEvent`), `status_for_tool()` turns it into a shopper-friendly line and sends it through `ChatDeps.status()`. The fact-check also sends "Double-checking prices and stock…" when it sends a reply back. `main.py` puts those lines on a queue and streams them as Server-Sent Events, then sends the final `ChatMessage` (or an `error` event).

  | Tool call | Status shown |
  |---|---|
  | `search_products` | "Searching the catalogue for hoodies in navy under $70…" (built from the query and filters) |
  | `get_product_details` | "Checking price and stock for Yale Mom Hoodie…" (the name looked up from the id) |
  | `catalogue_overview` | "Looking over the whole catalogue…" |
  | `get_shopper_profile` | "Looking up your account…" |
  | fact-check retry | "Double-checking prices and stock…" |

- **Frontend:** `streamChatMessage()` in `chat.ts` reads the stream with `fetch` (EventSource can't send a POST body) and passes each status to `ChatProvider`, which shows it in the typing bubble with animated dots.
- **Why the reply text isn't streamed word by word:** the fact-check has to approve the whole reply before the shopper sees it. Streaming the text first could flash a wrong price that then gets corrected. Progress lines make the wait feel shorter without weakening that guarantee.
- `POST /api/chat` still returns the same answer as plain JSON, for scripts and tests. Both go through the same `answer_chat()`.

### Reasoning effort: measured, not guessed (`backend/benchmark.py`)

`benchmark.py` runs six real shopper questions through the agent at each reasoning effort and checks every reply against the database (e.g. "27 hoodies, $45.00 to $88.00", "L is out of stock", "$68.00, 2 left in XXL"). Results on 2026-10-06:

| Effort | Correct | Median | Mean | Slowest | Output tokens (mean) | Fact-check retries |
|---|---|---|---|---|---|---|
| high (default) | 6/6 | 5.6s | 6.2s | 9.6s | 277 | 0 |
| medium | 6/6 | 4.4s | 6.2s | 13.4s | 209 | 0 |
| low | 6/6 | 4.2s | 4.3s | 6.0s | 184 | 0 |

All three got everything right. Lower effort was about 1 to 2 seconds faster per reply, but six questions is a small sample and single runs vary (medium's 13.4s was one slow call). The default stays **high**, the project's standard setting. To trade a little reasoning for speed, set `OPENAI_REASONING_EFFORT=low` (or `medium`) before starting the backend, and re-run `benchmark.py` to confirm.

**Portkey cache fix:** while testing, a repeated identical question came back from Portkey's response cache with an item id the model API then rejected on the next tool round (a 400 error). The agent's client now sends `x-portkey-cache-force-refresh: true`, so every answer is fresh. That's also correct for a store, since stock changes.

### Audit trail of agent-loop activity (`output/audit_trail.json`)

Every agent loop is recorded in `output/audit_trail.json`: a JSON array, **append-only**, never wiped between runs or server restarts. There is one entry (`AuditEntry` in `models.py`) per loop iteration, that is, per model response. This follows the same pattern as HW 3.

| Field | What it records |
|---|---|
| `timestamp` | When the model responded (UTC) |
| `turn_id`, `step` | Which chat message the step belongs to, and its position in that message's loop (1, 2, …) |
| `endpoint`, `user_id`, `page_path` | Where the message came from. User id only, never name or email |
| `message` | The shopper's message, shortened |
| `model`, `reasoning_effort` | Which model and setting answered |
| `tool_calls` | Each call in this step: `tool_name`, short `args`, short `result` (e.g. `baseball-left-chest-crewneck: $58.00, in_stock, XS:0 S:15 M:5 L:25 XL:0 XXL:25`). `final_result` is the agent's structured answer, recorded as `answer: … \| product_ids: […]`. A result starting with `retry:` means the fact-check or argument validation sent it back |
| `stop_reason` | The model's finish reason (`stop`, `tool_call`, `length`, `content_filter`), or `error: …` if the run failed |
| `ended_run` | `true` on the step that finished the message |
| `input_tokens`, `output_tokens` | Tokens for this step |
| `turn_latency_ms` | Total time for the message, on the last step |

Example (one chat message, two steps):

```json
[
  {"timestamp": "2026-10-06T21:04:56+00:00", "turn_id": "f7eeaae6cac9", "step": 1, "endpoint": "/api/chat",
   "user_id": null, "page_path": "/products/baseball-left-chest-crewneck", "message": "is this in stock in XS?",
   "model": "gpt-5.6-luna", "reasoning_effort": "high", "stop_reason": "stop", "ended_run": false,
   "tool_calls": [{"tool_name": "get_product_details", "args": {"product_id": "baseball-left-chest-crewneck"},
                   "result": "baseball-left-chest-crewneck: $58.00, in_stock, XS:0 S:15 M:5 L:25 XL:0 XXL:25"}]},
  {"timestamp": "2026-10-06T21:04:59+00:00", "turn_id": "f7eeaae6cac9", "step": 2, "stop_reason": "stop", "ended_run": true,
   "tool_calls": [{"tool_name": "final_result", "args": {…},
                   "result": "answer: The **Baseball Left Chest Crewneck** is **out of stock in XS**… | product_ids: [...]"}],
   "turn_latency_ms": 7512}
]
```

**How it's written:**
- `run_chat()` in `agent.py` wraps the run in Pydantic AI's `capture_run_messages()`, so the loop's messages are available even if the run fails.
- `loop_entries()` turns each model response into an entry, matching tool calls to their results by `tool_call_id`.
- `audit.append()` adds the entries to the end of the file: it reads the array, appends, writes a temp file, and swaps it in atomically, under a lock, so a crash mid-write never loses earlier entries.
- Every chat message from both endpoints is recorded, including failed runs (`stop_reason: "error: …"`) and filtered ones (`content_filter`).
- If writing the audit fails, the shopper still gets their answer.

**Privacy:**
- Only the user id is logged, never name or password.
- Email addresses and card-like numbers in any text are replaced with `[email]` and `[redacted number]`.
- `get_shopper_profile` results are logged only as `logged_in=True`.
- Arguments and results are cut to 200 characters.

**Reading it:** `.venv/bin/python audit_report.py` (from `backend/`) summarizes it: steps, how runs ended, steps per message, time per message, tool use, retries, and tokens. `--last N` prints the last N messages step by step.

**What it has caught so far:**
- A coding mistake in reading token usage.
- A Portkey cache error on repeated questions.
- A jailbreak attempt where the provider filtered the model's response mid-loop (`stop_reason: content_filter`) and the agent carried on, giving a confused reply. Any filtered response now ends in Handsome Dan's polite decline.

## The assistant's persona: Handsome Dan

The agent now speaks as **Handsome Dan**, Yale's bulldog mascot.

- **Prompt (`prompts/prompt.md`):**
  - The title and first line make it Handsome Dan.
  - A "Who you are: Handsome Dan" section sets the personality: friendly, loyal, a little playful, Yale-proud, with light bulldog touches, at most one "Woof!" per reply and not in every reply.
  - It tells him the chat window has already greeted the shopper, so he shouldn't reintroduce himself. In testing he did reintroduce himself before this rule was added.
  - He must say he's an AI shopping assistant playing Handsome Dan when asked, must not claim to have tried products, and must not speak for Yale or its real live mascot.
  - All earlier rules (prices and stock only from tools, the fact-check, safety basics) are unchanged and still come first.
- **Code:**
  - The greeting and "welcome back" lines are in `frontend/src/components/ChatProvider.tsx`.
  - His avatar (the 1889 photo cropped to his face, `.dan-avatar`) is in the chat header, on the "Ask Handsome Dan" button, and next to each of his messages.
  - The progress lines in `status_for_tool()` and the content-filter decline in `agent.py` are in his voice.
