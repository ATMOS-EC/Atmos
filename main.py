from fastapi import FastAPI
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import psycopg

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = FastAPI()

class DadosSensores(BaseModel):
    estacao_id: str
    temperatura: float
    umidade: float
    pressao: float
    qualidade_ar: float
    luminosidade: int
    chuva: bool

@app.get("/")
def inicio():
    return {"mensagem": "API da estação meteorológica funcionando"}

@app.post("/dados")
def receber_dados(dados: DadosSensores):

    conexao = psycopg.connect(DATABASE_URL)
    cursor = conexao.cursor()

    cursor.execute("""
    INSERT INTO leituras
    (estacao_id, temperatura, umidade, pressao, qualidade_ar, luminosidade, chuva)
    VALUES (%s, %s, %s, %s, %s, %s, %s);
    """, (
        dados.estacao_id,
        dados.temperatura,
        dados.umidade,
        dados.pressao,
        dados.qualidade_ar,
        dados.luminosidade,
        int(dados.chuva)
    ))

    conexao.commit()

    cursor.close()
    conexao.close()

    return {
        "mensagem": "Dados salvos no banco com sucesso!",
        "dados": dados
    }
conexao = psycopg.connect(DATABASE_URL)
cursor = conexao.cursor()

cursor.execute("""
SELECT
    column_name,
    data_type,
    numeric_precision,
    numeric_scale
FROM information_schema.columns
WHERE table_name = 'leituras'
ORDER BY ordinal_position;
""")

for coluna in cursor.fetchall():
    print(coluna)

cursor.close()
conexao.close()
