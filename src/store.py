"""Acesso ao banco vetorial.

A coleção é o único ponto de acoplamento entre ingestão e busca: as duas fases
precisam apontar para o mesmo `PG_VECTOR_COLLECTION_NAME`.
"""

from langchain_postgres import PGVector

from config import DATABASE_URL, PG_VECTOR_COLLECTION_NAME, require_env
from providers import get_embeddings


def get_vector_store() -> PGVector:
    """Devolve a coleção pgvector, criando-a se ainda não existir."""
    require_env("DATABASE_URL", "PG_VECTOR_COLLECTION_NAME")
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=PG_VECTOR_COLLECTION_NAME,
        connection=DATABASE_URL,
        use_jsonb=True,
    )
