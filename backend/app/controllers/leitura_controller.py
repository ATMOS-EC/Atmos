from fastapi import APIRouter, HTTPException, Query

from app.config import ESTACAO_PADRAO
from app.database import BancoNaoConfigurado
from app.models.leitura import DadosSensores
from app.services import leitura_service

router = APIRouter(tags=["leituras"])


def _erro_banco(erro: Exception) -> HTTPException:
    if isinstance(erro, BancoNaoConfigurado):
        return HTTPException(status_code=503, detail=str(erro))
    return HTTPException(status_code=503, detail=f"Erro no banco de dados: {erro}")


@router.get("/status")
def status():
    return {"mensagem": "API da estação meteorológica funcionando"}


@router.post("/dados")
def receber_dados(dados: DadosSensores):
    try:
        leitura_service.registrar_leitura(dados)
    except Exception as erro:
        raise _erro_banco(erro)

    return {"mensagem": "Dados salvos no banco com sucesso!", "dados": dados}


@router.get("/dados")
def dados_atuais(estacao_id: str = ESTACAO_PADRAO):
    try:
        leitura = leitura_service.leitura_atual(estacao_id)
    except Exception as erro:
        raise _erro_banco(erro)

    if leitura is None:
        raise HTTPException(status_code=404, detail="Nenhuma leitura encontrada")
    return leitura


@router.get("/historico")
def historico(
    estacao_id: str = ESTACAO_PADRAO,
    limite: int = Query(100, ge=1, le=1000),
):
    try:
        return leitura_service.historico(estacao_id, limite)
    except Exception as erro:
        raise _erro_banco(erro)
