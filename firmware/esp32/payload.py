"""Contrato puro, testavel sem placa e sem importar configuracao do backend."""
import math


def _number(value, low, high, name, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Tipo invalido: " + name)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Fora da faixa: " + name)
    if integer and not isinstance(value, int):
        raise ValueError("Esperado inteiro: " + name)
    return value


def build_payload(station_id, reading):
    if not isinstance(station_id, str) or not station_id.strip():
        raise ValueError("Identificacao da estacao vazia")
    if type(reading.get("chuva")) is not bool:
        raise ValueError("Chuva deve ser booleana")
    return {
        "estacao_id": station_id,
        "temperatura": _number(reading.get("temperatura"), -40, 80, "temperatura"),
        "umidade": _number(reading.get("umidade"), 0, 100, "umidade"),
        "pressao": _number(reading.get("pressao"), 300, 1100, "pressao"),
        "qualidade_ar": _number(reading.get("qualidade_ar"), 0, 4095, "qualidade_ar"),
        "luminosidade": _number(reading.get("luminosidade"), 0, 4095, "luminosidade", True),
        "chuva": reading["chuva"],
    }


class PendingBuffer:
    """RAM limitada; guarda apenas leituras ainda nao tentadas via POST."""

    def __init__(self, capacity, max_age_ms, ticks_diff):
        if capacity < 1 or max_age_ms < 1:
            raise ValueError("Buffer invalido")
        self.capacity = capacity
        self.max_age_ms = max_age_ms
        self.ticks_diff = ticks_diff
        self.items = []

    def add(self, payload, now):
        dropped = len(self.items) >= self.capacity
        if dropped:
            self.items.pop(0)
        self.items.append((now, payload))
        return dropped

    def expire(self, now):
        count = 0
        while self.items and self.ticks_diff(now, self.items[0][0]) >= self.max_age_ms:
            self.items.pop(0)
            count += 1
        return count

    def take(self):
        return self.items.pop(0)[1] if self.items else None


def retry_delay(failures, base, maximum):
    return min(maximum, base * (2 ** min(max(failures - 1, 0), 8)))
