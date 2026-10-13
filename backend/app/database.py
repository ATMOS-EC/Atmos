from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_URL


class BancoNaoConfigurado(RuntimeError):
    """DATABASE_URL não foi definida no .env."""


@contextmanager
def obter_conexao():
    if not DATABASE_URL:
        raise BancoNaoConfigurado("DATABASE_URL não configurada no arquivo .env")

    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conexao:
        yield conexao
