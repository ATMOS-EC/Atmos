from pydantic import BaseModel


class DadosSensores(BaseModel):
    """Payload enviado pela estação (ESP32)."""

    estacao_id: str
    temperatura: float
    umidade: float
    pressao: float
    qualidade_ar: float
    luminosidade: int
    chuva: bool
