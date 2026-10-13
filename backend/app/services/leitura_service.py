from app.models.leitura import DadosSensores
from app.repositories import leitura_repository


def _formatar(linha: dict) -> dict:
    """Converte a linha do banco para o formato que o frontend usa."""
    data = linha.get("data_hora")
    return {
        **linha,
        "chuva": float(linha["chuva"]) if linha.get("chuva") is not None else None,
        "qualidadeAr": linha.get("qualidade_ar"),
        "data_hora": data.isoformat() if data else None,
        "data": data.isoformat() if data else None,
    }


def registrar_leitura(dados: DadosSensores) -> None:
    leitura_repository.inserir(dados)


def leitura_atual(estacao_id: str) -> dict | None:
    linha = leitura_repository.buscar_ultima(estacao_id)
    return _formatar(linha) if linha else None


def historico(estacao_id: str, limite: int) -> list[dict]:
    linhas = leitura_repository.buscar_historico(estacao_id, limite)
    # Repositório retorna do mais recente ao mais antigo; gráficos querem ordem cronológica.
    return [_formatar(linha) for linha in reversed(linhas)]
