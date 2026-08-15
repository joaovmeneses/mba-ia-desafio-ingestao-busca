# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Starter skeleton for the "Desafio MBA Engenharia de Software com IA" (Full Cycle): a RAG pipeline that
ingests `document.pdf` into a PostgreSQL + pgvector store and answers CLI questions **grounded strictly
in the ingested content**.

The three files in `src/` are intentionally unimplemented stubs (`pass` bodies) — the challenge is to
fill them in. Treat the existing signatures, the prompt template, and `.env.example` as the contract:
they define the expected shape of the solution, so extend rather than rewrite them.

## Setup and commands

The repo has no test suite, linter, or build step. Everything runs as plain scripts.

```bash
# 1. Vector database (pgvector/pg17 on :5432; a bootstrap container runs CREATE EXTENSION vector)
docker compose up -d

# 2. Virtualenv — system python3 is 3.9.6, which is too old for the pinned deps
#    (numpy 2.3.2 requires >= 3.11). Use the homebrew interpreter:
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Credentials
cp .env.example .env   # then fill in the keys / DATABASE_URL / PG_VECTOR_COLLECTION_NAME / PDF_PATH

# 4. Run — from inside src/, see the import note below
cd src
python ingest.py       # one-off: chunk + embed document.pdf into pgvector
python chat.py         # interactive Q&A loop
```

`DATABASE_URL` for the compose stack is `postgresql+psycopg://postgres:postgres@localhost:5432/rag`
(the `+psycopg` driver suffix matters — `langchain-postgres` uses SQLAlchemy with psycopg 3).

## Architecture

Two phases sharing one pgvector collection, wired only through `PG_VECTOR_COLLECTION_NAME`:

- **Ingestion** (`src/ingest.py`) — load `PDF_PATH` with `PyPDFLoader`, split with
  `RecursiveCharacterTextSplitter` (challenge spec: 1000 chars / 150 overlap), embed, and write to
  `PGVector`. Runs standalone; nothing else imports it.
- **Retrieval + generation** (`src/search.py`) — `search_prompt()` builds and returns a LangChain
  chain: similarity search over the same `PGVector` collection (challenge spec: `k=10`), the retrieved
  chunks joined into `PROMPT_TEMPLATE`'s `{contexto}`, the user question into `{pergunta}`, then the LLM.
- **CLI** (`src/chat.py`) — calls `search_prompt()` once at startup, exits early if it returns falsy,
  then loops reading questions and invoking the chain.

Provider choice is deliberately open: `.env.example` carries **both** `OPENAI_*` and `GOOGLE_*` keys and
embedding models. Whatever embedding model ingestion uses must be the one search uses — a mismatch
silently produces garbage retrieval against an existing collection, so re-ingest into a fresh collection
name when switching providers.

## Conventions that matter

- **Flat imports.** `chat.py` does `from search import search_prompt`, not `from src.search import ...`.
  Scripts must be run with `src/` as the working directory (or on `PYTHONPATH`). Keep new modules in
  `src/` and import them the same flat way; adding a package prefix breaks the entrypoints.
- **`PROMPT_TEMPLATE` in `src/search.py` is the graded artifact.** Its rules (answer only from context,
  the exact fallback sentence "Não tenho informações necessárias para responder sua pergunta.", no
  outside knowledge, no opinions) plus the three few-shot examples define the required behavior. Do not
  reword or soften it while implementing the chain around it.
- User-facing strings and the prompt are in Portuguese; keep new ones consistent.
- `README.md` is a stub asking the author to document how to run the solution — fill it in as the
  solution lands.
