
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from psycopg.rows import dict_row
import os
import psycopg

# configurações
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()

# configurações de acesso ao dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500"
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DadosSensores(BaseModel):
    estacao_id: str
    temperatura: float
    umidade: float
    pressao: float
    qualidade_ar: float
    luminosidade: int
    chuva: bool


# conexão com o banco
def conectar_banco():
    if not DATABASE_URL:
        raise HTTPException(
            status_code=500,
            detail="DATABASE_URL não configurada."
        )

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row
    )


# formata os dados para o dashboard
def formatar_dados(linha):
    if not linha:
        return None

    dados = dict(linha)

    dados["temperatura"] = float(dados["temperatura"])
    dados["umidade"] = float(dados["umidade"])
    dados["pressao"] = float(dados["pressao"])
    dados["qualidadeAr"] = float(dados["qualidade_ar"])
    dados["luminosidade"] = int(dados["luminosidade"])

    # O banco armazena chuva como inteiro: 0 ou 1.
    dados["chuva"] = int(dados["chuva"])

    dados["data"] = (
        dados["data_hora"].isoformat()
        if dados.get("data_hora")
        else None
    )

    dados.pop("qualidade_ar", None)
    dados.pop("data_hora", None)

    return dados


# rota inicial
@app.get("/")
def inicio():
    return {
        "mensagem": "API da estação meteorológica funcionando"
    }


# recebe e salva os dados dos sensores
@app.post("/dados")
def receber_dados(dados: DadosSensores):
    try:
        with conectar_banco() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO leituras
                    (
                        estacao_id,
                        temperatura,
                        umidade,
                        pressao,
                        qualidade_ar,
                        luminosidade,
                        chuva
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id_leitura, data_hora;
                    """,
                    (
                        dados.estacao_id,
                        dados.temperatura,
                        dados.umidade,
                        dados.pressao,
                        dados.qualidade_ar,
                        dados.luminosidade,
                        int(dados.chuva)
                    )
                )

                registro = cursor.fetchone()

        return {
            "mensagem": "Dados salvos no banco com sucesso!",
            "id_leitura": registro["id_leitura"],
            "data": registro["data_hora"].isoformat(),
            "dados": dados.model_dump()
        }

    except psycopg.Error as erro:
        print("Erro ao salvar leitura:", erro)

        raise HTTPException(
            status_code=500,
            detail="Não foi possível salvar os dados no banco."
        )


# consulta a leitura mais recente
@app.get("/dados")
def buscar_dados_atuais():
    try:
        with conectar_banco() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM leituras
                    ORDER BY data_hora DESC, id_leitura DESC
                    LIMIT 1;
                    """
                )

                linha = cursor.fetchone()

        if not linha:
            raise HTTPException(
                status_code=404,
                detail="Ainda não existem leituras cadastradas."
            )

        return formatar_dados(linha)

    except psycopg.Error as erro:
        print("Erro ao consultar os dados atuais:", erro)

        raise HTTPException(
            status_code=500,
            detail="Não foi possível consultar os dados atuais."
        )


# consulta o histórico para os gráficos
@app.get("/historico")
def buscar_historico():
    try:
        with conectar_banco() as conexao:
            with conexao.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT *
                    FROM (
                        SELECT *
                        FROM leituras
                        ORDER BY data_hora DESC, id_leitura DESC
                        LIMIT 100
                    ) AS ultimas
                    ORDER BY data_hora ASC, id_leitura ASC;
                    """
                )

                linhas = cursor.fetchall()

        return [
            formatar_dados(linha)
            for linha in linhas
        ]

    except psycopg.Error as erro:
        print("Erro ao consultar o histórico:", erro)

        raise HTTPException(
            status_code=500,
            detail="Não foi possível consultar o histórico."
        )
