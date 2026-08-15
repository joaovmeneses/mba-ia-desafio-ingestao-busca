from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import resolve_pdf_path
from store import get_vector_store

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def load_pages(pdf_path) -> list[Document]:
    return PyPDFLoader(str(pdf_path)).load()


def split_into_chunks(pages: list[Document]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=False,
    )
    return splitter.split_documents(pages)


def drop_empty_metadata(documents: list[Document]) -> list[Document]:
    return [
        Document(
            page_content=document.page_content,
            metadata={
                key: value
                for key, value in document.metadata.items()
                if value not in ("", None)
            },
        )
        for document in documents
    ]


def build_deterministic_ids(chunks: list[Document]) -> list[str]:
    return [f"doc-{index}" for index in range(len(chunks))]


def ingest_pdf():
    pdf_path = resolve_pdf_path()
    print(f"Lendo {pdf_path.name}...")

    pages = load_pages(pdf_path)
    print(f"  {len(pages)} páginas carregadas.")

    chunks = drop_empty_metadata(split_into_chunks(pages))
    if not chunks:
        raise RuntimeError("Nenhum texto extraído do PDF — nada a ingerir.")

    print(f"  {len(chunks)} chunks de {CHUNK_SIZE} caracteres (overlap {CHUNK_OVERLAP}).")

    print("Gerando embeddings e gravando na coleção...")
    get_vector_store().add_documents(
        documents=chunks,
        ids=build_deterministic_ids(chunks),
    )
    print(f"Pronto: {len(chunks)} chunks gravados.")


if __name__ == "__main__":
    ingest_pdf()
