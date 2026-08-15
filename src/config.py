"""Carrega e valida a configuração vinda do .env.

Único módulo que lê variáveis de ambiente. Os demais importam daqui.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Raiz do projeto (src/ está um nível abaixo). Serve para resolver caminhos
# relativos independentemente do diretório de onde o script foi chamado.
BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL")
PG_VECTOR_COLLECTION_NAME = os.getenv("PG_VECTOR_COLLECTION_NAME")
PDF_PATH = os.getenv("PDF_PATH")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-nano")


def require_env(*keys: str) -> None:
    """Falha cedo, com mensagem clara, se alguma variável obrigatória faltar."""
    for key in keys:
        if not os.getenv(key):
            raise RuntimeError(
                f"Variável de ambiente {key} não definida. "
                f"Copie o .env.example para .env e preencha os valores."
            )


def resolve_pdf_path() -> Path:
    """Resolve PDF_PATH contra a raiz do projeto quando o caminho é relativo."""
    require_env("PDF_PATH")
    path = Path(PDF_PATH).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.is_file():
        raise RuntimeError(f"PDF não encontrado em {path} (PDF_PATH={PDF_PATH}).")
    return path
