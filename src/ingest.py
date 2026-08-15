"""Ingestão do PDF no banco vetorial.

Roda uma vez, de forma independente do restante: `python src/ingest.py`.

Reexecutar é seguro — os ids são determinísticos, então a gravação é um upsert.
A ressalva é mudar os parâmetros de split: se a nova execução gerar menos chunks,
os ids antigos excedentes continuam no banco e poluem a busca. Nesse caso, limpe
a coleção antes:

    docker exec postgres_rag psql -U postgres -d rag -c "DELETE FROM langchain_pg_embedding;"
"""

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import resolve_pdf_path
from store import get_vector_store

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def ingest_pdf():
    pdf_path = resolve_pdf_path()
    print(f"Lendo {pdf_path.name}...")

    docs = PyPDFLoader(str(pdf_path)).load()
    print(f"  {len(docs)} páginas carregadas.")

    splits = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=False,
    ).split_documents(docs)

    if not splits:
        raise RuntimeError("Nenhum texto extraído do PDF — nada a ingerir.")

    print(f"  {len(splits)} chunks de {CHUNK_SIZE} caracteres (overlap {CHUNK_OVERLAP}).")

    # Metadados vazios sujariam o jsonb sem agregar nada à busca.
    enriched = [
        Document(
            page_content=d.page_content,
            metadata={k: v for k, v in d.metadata.items() if v not in ("", None)},
        )
        for d in splits
    ]
    ids = [f"doc-{i}" for i in range(len(enriched))]

    print("Gerando embeddings e gravando na coleção...")
    get_vector_store().add_documents(documents=enriched, ids=ids)
    print(f"Pronto: {len(enriched)} chunks gravados.")


if __name__ == "__main__":
    ingest_pdf()
