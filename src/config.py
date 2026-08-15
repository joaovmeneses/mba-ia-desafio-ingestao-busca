import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL")
PG_VECTOR_COLLECTION_NAME = os.getenv("PG_VECTOR_COLLECTION_NAME")
PDF_PATH = os.getenv("PDF_PATH")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-nano")
AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))


def require_env(*names: str) -> None:
    for name in names:
        if not os.getenv(name):
            raise RuntimeError(
                f"Variável de ambiente {name} não definida. "
                f"Copie o .env.example para .env e preencha os valores."
            )


def resolve_pdf_path() -> Path:
    require_env("PDF_PATH")

    path = Path(PDF_PATH).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    if not path.is_file():
        raise RuntimeError(f"PDF não encontrado em {path} (PDF_PATH={PDF_PATH}).")

    return path
