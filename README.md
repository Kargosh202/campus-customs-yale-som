# Campus Customs

A shopping website for Campus Customs (officially licensed Yale merchandise, 57 Broadway, New Haven) with **Handsome Dan**, an AI shopping assistant that answers questions about products, prices, sizes, and live stock.

- **Frontend:** React + Vite + TypeScript (`frontend/`)
- **Backend:** FastAPI (`backend/main.py`), with SQLite for products, accounts, and saved chats
- **Agent:** Pydantic AI on OpenAI's Responses API through Portkey, in four files under `backend/`: `prompts/prompt.md`, `agent.py`, `tools.py`, `models.py`

How it all works is documented in [`output/harness.md`](output/harness.md). The design and usability write-ups are in [`output/design.md`](output/design.md) and [`output/usability.md`](output/usability.md), and screenshots are in [`output/app_check.html`](output/app_check.html).

## Requirements

- Python 3.12+ (developed on 3.14)
- Node.js 20+ and npm
- A Portkey API key with access to `gpt-5.6-luna`

## 1. Place the data pack (not in git)

The database and product photos aren't in this repository. Put the data pack in a `data/` folder at the top level:

```
data/
├── campus_customs.db
└── products/          # images referenced by the catalogue
```

If you have `data.zip`, run `unzip data.zip` from this folder.

## 2. Configure secrets

```bash
cp .env.example .env
```

Edit `.env` and set `PORTKEY_API_KEY` and `SESSION_SECRET` (the file explains how to generate one). `.env` is git-ignored.

## 3. Run the backend (terminal 1)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

The API runs at http://localhost:8000. It must be started from inside `backend/`.

## 4. Run the frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server forwards `/api` and `/media` to the backend on port 8000.

## Try it

- Browse **Products**, sort by price, and open any product for sizes and stock.
- Click **Ask Handsome Dan** and try "what hoodies do you have?" (matching cards appear on the page), or open a product and ask "do you have this in pink?"
- Create an account or log in. Logged-in chats are saved and reload when you come back. The provided data pack includes a test account: `test@campuscustoms.yale.edu` / `password`.

## Useful scripts (from `backend/`, with the venv active)

| Command | What it does |
|---|---|
| `python smoke_test.py` | Checks the model connection through Portkey |
| `python audit_report.py --last 3` | Summarizes the agent-loop audit trail in `output/audit_trail.json` |
| `python benchmark.py` | Measures reply speed and correctness at each reasoning effort |

## Project layout

```
├── AI_prompts.md          # log of the prompts used to build this
├── requirements.txt
├── .env.example
├── frontend/              # Vite React TypeScript app
├── backend/
│   ├── main.py            # FastAPI app (uvicorn main:app --reload --port 8000)
│   ├── agent.py           # agent wiring, fact-check, audit trail
│   ├── tools.py           # tools the agent can call
│   ├── models.py          # Pydantic / Pydantic AI types
│   ├── prompts/prompt.md  # Handsome Dan's system prompt
│   └── db.py, passwords.py, audit.py, …
└── output/                # harness, design, usability, app check, audit trail
```
