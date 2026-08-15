# Desafio MBA Engenharia de Software com IA - Full Cycle

Solução de RAG que ingere um PDF em PostgreSQL + pgVector e responde perguntas via CLI,
usando **exclusivamente** o conteúdo do documento.

O `document.pdf` incluído é uma planilha com 1.001 empresas fictícias (nome, faturamento e
ano de fundação) distribuídas em 34 páginas.

## Stack

| Camada | Escolha |
|---|---|
| Linguagem | Python 3.12 |
| Framework | LangChain (LCEL) |
| Banco vetorial | PostgreSQL 17 + pgvector, via Docker Compose |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dimensões) |
| LLM | OpenAI `gpt-5-nano` |

## Pré-requisitos

- Docker e Docker Compose
- Python **3.11 ou superior** (`numpy 2.3.2` não suporta versões anteriores)
- Uma `OPENAI_API_KEY`

## Como executar

### 1. Suba o banco

```bash
docker compose up -d
```

Confirme que a extensão foi criada antes de seguir:

```bash
docker exec postgres_rag psql -U postgres -d rag -c "\dx"
```

A lista precisa incluir `vector`. O Postgres é exposto na porta **55432** do host para não
conflitar com uma instalação local na 5432.

### 2. Crie o ambiente virtual

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure as variáveis

```bash
cp .env.example .env
```

Preencha a `OPENAI_API_KEY`. Os demais valores já vêm prontos para o `docker-compose.yml`
deste repositório:

| Variável | Valor |
|---|---|
| `OPENAI_API_KEY` | sua chave |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` |
| `OPENAI_CHAT_MODEL` | `gpt-5-nano` |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:55432/rag` |
| `PG_VECTOR_COLLECTION_NAME` | `desafio_rag` |
| `PDF_PATH` | `./document.pdf` |

O sufixo `+psycopg` na `DATABASE_URL` é obrigatório: o `langchain-postgres` usa SQLAlchemy
com psycopg 3, e uma URL `postgresql://` pura seleciona o psycopg2.

### 4. Ingira o PDF

```bash
python src/ingest.py
```

```
Lendo document.pdf...
  34 páginas carregadas.
  67 chunks de 1000 caracteres (overlap 150).
Gerando embeddings e gravando na coleção...
Pronto: 67 chunks gravados.
```

Rodar de novo é seguro: os identificadores dos chunks são determinísticos, então a gravação
é um upsert e não duplica nada.

### 5. Converse com o documento

```bash
python src/chat.py
```

```
Faça sua pergunta (digite 'sair' para encerrar).

PERGUNTA: Qual o faturamento da Empresa SuperTechIABrazil?
RESPOSTA: R$ 10.000.000,00

PERGUNTA: Quantos clientes temos em 2024?
RESPOSTA: Não tenho informações necessárias para responder sua pergunta.

PERGUNTA: sair
Até mais!
```

Encerre com `sair`, `exit`, `quit`, `Ctrl+C` ou `Ctrl+D`.

> Os scripts usam imports diretos (`from search import search_prompt`), então rode-os como
> `python src/ingest.py` a partir da raiz do projeto. `python -m src.chat` não funciona.

## Como funciona

**Ingestão** — `PyPDFLoader` lê o PDF, o `RecursiveCharacterTextSplitter` divide em chunks de
1000 caracteres com overlap de 150, cada chunk vira um embedding e é gravado na coleção
pgvector.

O overlap não é decorativo: como o documento é uma tabela, um corte a cada 1000 caracteres
parte linhas no meio. O overlap de 150 garante que a linha partida reapareça inteira no
chunk seguinte.

**Busca** — a pergunta é vetorizada, `similarity_search_with_score(k=10)` traz os 10 chunks
mais próximos, o texto deles preenche o `{contexto}` do prompt e o LLM redige a resposta.
Se a informação não estiver no contexto, o prompt obriga a recusa.

```
src/
  config.py      variáveis de ambiente e caminhos
  providers.py   fábricas de embeddings e LLM
  store.py       acesso à coleção pgvector
  ingest.py      entrypoint da ingestão
  search.py      prompt e chain de pergunta/resposta
  chat.py        entrypoint do CLI
```

`providers.py` é o único módulo que conhece o provider concreto — `ingest.py` e `search.py`
pedem os modelos a ele e não importam nada de OpenAI. Trocar de provider é mexer em um
arquivo só.

## Limitações conhecidas

**Perguntas agregadas não são confiáveis.** "Quantas empresas existem no documento?" responde
um número errado em vez de recusar, porque o modelo conta as linhas do contexto que recebeu —
162 linhas nos 10 chunks recuperados, de 1.001 no documento inteiro. Ele está sendo fiel ao
contexto; o contexto é que é uma fatia. Perguntas sobre empresas específicas, que é o caso de
uso do desafio, funcionam corretamente.

**Não há histórico de conversa.** Cada pergunta é independente, então perguntas de
acompanhamento ("e o ano de fundação dela?") não funcionam.

## Manutenção

Ao mudar `chunk_size`, `chunk_overlap` ou o modelo de embeddings, limpe a coleção antes de
reingerir. Os identificadores são posicionais: se a nova execução gerar menos chunks, os
antigos excedentes ficam órfãos no banco e continuam aparecendo nas buscas.

```bash
docker exec postgres_rag psql -U postgres -d rag -c "DELETE FROM langchain_pg_embedding;"
python src/ingest.py
```

Para recomeçar do zero, apagando o volume do Postgres:

```bash
docker compose down -v && docker compose up -d
```
