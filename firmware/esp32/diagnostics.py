"""Ensaios explicitos no REPL. Importar este modulo nao envia dados."""
import json
import config
from main import validate_config
from payload import build_payload
from sensors import PhysicalSensors, SimulatedSensors

_physical = None


def sample():
    """Gera e valida uma amostra simulada, sem acessar rede/hardware."""
    validate_config(config)
    result = build_payload(config.SIMULATION_STATION_ID, SimulatedSensors().read())
    print("[SIMULACAO / SEM ENVIO]", json.dumps(result))
    return result


def read_sensor(name):
    """Nomes: dht, bmp, mq, ldr, rain. Requer HARDWARE_CONFIRMED."""
    global _physical
    validate_config(config)
    if _physical is None:
        _physical = PhysicalSensors(config)
    result = _physical.read_one(name)
    print("[FISICO / SEM ENVIO]", name, result)
    return result


def connect_wifi():
    """Somente Wi-Fi: nao envia JSON para a API."""
    from secrets import WIFI_SSID, WIFI_PASSWORD
    from wifi_manager import WiFiManager
    wifi = WiFiManager(config, WIFI_SSID, WIFI_PASSWORD)
    return wifi.connect()


def send_once():
    """Uma amostra, um POST, sem repeticao. Respeita todas as travas de config."""
    validate_config(config)
    if not config.SEND_ENABLED:
        raise ValueError("Habilite SEND_ENABLED conscientemente antes do ensaio")
    from api_client import APIClient
    from wifi_manager import sync_clock
    global _physical
    if config.SIMULATION:
        sensors = SimulatedSensors()
    else:
        if _physical is None:
            _physical = PhysicalSensors(config)
        sensors = _physical
    station = config.SIMULATION_STATION_ID if config.SIMULATION else config.STATION_ID
    payload = build_payload(station, sensors.read())
    client = APIClient(config)
    if not connect_wifi():
        print("[WIFI] Sem conexao; nenhum POST realizado")
        return None
    if client.target[0] == "https" and not sync_clock():
        return None
    print("[ENVIO UNICO]", "SIMULACAO" if config.SIMULATION else "FISICO / ADC BRUTO")
    status = client.post(payload)
    print("[HTTP]", status)
    return status
