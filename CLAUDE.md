# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

Solution to the "Desafio MBA Engenharia de Software com IA" (Full Cycle): a RAG pipeline that
ingests `document.pdf` into PostgreSQL + pgvector and answers CLI questions **grounded strictly
in the ingested content**.

`document.pdf` is not prose — it is a 34-page spreadsheet with 1,001 fictional companies
(`Nome da empresa | Faturamento | Ano de fundação`). That shapes everything: chunking cuts table
rows in half, and the 150-char overlap is what makes the split row reappear intact in the next
chunk. Never "optimize" the overlap down.

`docs/plan.md` is the living design document — milestones, 18 recorded decisions with rationale,
risks, and validation results. **Read it before proposing changes**; most "obvious improvements"
were already evaluated and rejected there, with reasons.

## Setup and commands

No test suite, linter, or build step. Everything runs as plain scripts.

```bash
docker compose up -d                    # Postgres 17 + pgvector on host port 55432
docker exec postgres_rag psql -U postgres -d rag -c "\dx"   # must list `vector`

python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # then fill OPENAI_API_KEY

python src/ingest.py                    # one-off: 34 pages -> 67 chunks
python src/chat.py                      # interactive Q&A
```

Run from the **repo root**, not from `src/`. The scripts use flat imports
(`from search import search_prompt`), which work because Python puts the script's own directory
on `sys.path`. `python -m src.chat` breaks — there is no `__init__.py`, by design.

System `python3` is 3.9.6 and too old (`numpy 2.3.2` needs ≥3.11); use `python3.12` from homebrew.

Host port is **55432**, not 5432, because 5432 is already taken locally. Inside the compose
network the port is still 5432 — the `bootstrap_vector_ext` service must always use 5432.

## Architecture

Two phases sharing one pgvector collection, wired only through `PG_VECTOR_COLLECTION_NAME`:

- **Ingestion** (`src/ingest.py`) — `PyPDFLoader` → `RecursiveCharacterTextSplitter` (1000/150) →
  drop empty metadata → deterministic `doc-{i}` ids → `PGVector.add_documents`. Standalone;
  nothing imports it.
- **Retrieval + generation** (`src/search.py`) — `search_prompt()` builds an LCEL chain:
  `similarity_search_with_score(k=10)` feeds `{contexto}`, the question feeds `{pergunta}`, then
  prompt → LLM → `StrOutputParser`.
- **CLI** (`src/chat.py`) — calls `search_prompt()` once, exits early if it returns falsy, then
  loops over questions.

Supporting modules: `config.py` (the only module reading env vars), `providers.py` (the only
module importing `langchain_openai`), `store.py` (the pgvector collection).

That `providers.py` boundary is the one piece of architecture worth protecting: `ingest.py` and
`search.py` must never instantiate `OpenAIEmbeddings`/`ChatOpenAI` directly. Ingestion and search
must use the same embedding model — a mismatch silently produces garbage retrieval, and the
shared factory is what enforces it.

## Conventions that matter

- **`PROMPT_TEMPLATE` in `src/search.py` is the graded artifact.** Its rules, the exact refusal
  sentence "Não tenho informações necessárias para responder sua pergunta.", and the three
  few-shot examples define required behavior. Do not reword, soften, or extend it — including to
  fix the known aggregate-question limitation (see below).
- **Code is 100% English; only data is Portuguese.** Identifiers, functions, and type hints in
  English. Portuguese stays in the `PROMPT_TEMPLATE`, the `contexto`/`pergunta` keys that bind to
  it, and user-facing output (the `PERGUNTA:`/`RESPOSTA:` format comes from the challenge spec).
- **No explanatory comments or docstrings.** If a function needs a comment to explain its return
  value or mechanics, rename or extract until the code says it by itself. The codebase currently
  has zero comments outside the prompt template — keep it that way.
- **Do not add pytest, pydantic-settings, repository classes, or layered architecture.** All
  explicitly rejected in `docs/plan.md` §4.1 as overengineering for ~200 lines.

## Known limitation

Aggregate questions ("quantas empresas existem?") return a wrong number instead of refusing: the
model counts the rows in the retrieved context (162 of 1,001). It is being faithful to
`{contexto}` — the context is just one sixth of the document. Not fixable without editing the
prompt template, so it stays documented in the README rather than patched.
