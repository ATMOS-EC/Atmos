import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
ESTACAO_PADRAO = os.getenv("ESTACAO_PADRAO", "ATMOS-01")
PORT = int(os.getenv("PORT", "8000"))

# Lista de origens permitidas pelo CORS
cors_env = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = [origem.strip() for origem in cors_env.split(",") if origem.strip()]
