from app.database import obter_conexao
from app.models.leitura import DadosSensores

COLUNAS = """
    estacao_id, temperatura, umidade, pressao,
    qualidade_ar, luminosidade, chuva, data_hora
"""


def inserir(dados: DadosSensores) -> None:
    with obter_conexao() as conexao:
        conexao.execute(
            """
            INSERT INTO leituras
                (estacao_id, temperatura, umidade, pressao, qualidade_ar, luminosidade, chuva)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
            """,
            (
                dados.estacao_id,
                dados.temperatura,
                dados.umidade,
                dados.pressao,
                dados.qualidade_ar,
                dados.luminosidade,
                int(dados.chuva),
            ),
        )


def buscar_ultima(estacao_id: str) -> dict | None:
    with obter_conexao() as conexao:
        return conexao.execute(
            f"""
            SELECT {COLUNAS} FROM leituras
            WHERE estacao_id = %s
            ORDER BY data_hora DESC
            LIMIT 1;
            """,
            (estacao_id,),
        ).fetchone()


def buscar_historico(estacao_id: str, limite: int) -> list[dict]:
    with obter_conexao() as conexao:
        return conexao.execute(
            f"""
            SELECT {COLUNAS} FROM leituras
            WHERE estacao_id = %s
            ORDER BY data_hora DESC
            LIMIT %s;
            """,
            (estacao_id, limite),
        ).fetchall()
