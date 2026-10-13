from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
from app.controllers.leitura_controller import router as leitura_router

app = FastAPI(
    title="ATMOS — Estação Meteorológica API",
    description="Backend em FastAPI para recepção e consulta de dados meteorológicos.",
    version="1.0.0",
)

# Habilita CORS para permitir conexões do Vercel, localhost ou qualquer origem configurada
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if "*" not in CORS_ORIGINS else ["*"],
    allow_credentials=True if "*" not in CORS_ORIGINS else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rota raiz informativa (útil para verificação de status no Render)
@app.get("/")
def raiz():
    return {
        "status": "online",
        "servico": "ATMOS Weather API",
        "documentacao": "/docs",
        "rotas": {
            "status": "/api/status",
            "dados_atuais": "/api/dados",
            "historico": "/api/historico",
        },
    }

# Rotas sob /api (consumidas pelo frontend na Vercel)
app.include_router(leitura_router, prefix="/api")

# Compatibilidade: ESP32 continua podendo enviar POST /dados direto na raiz
app.include_router(leitura_router, include_in_schema=False)
