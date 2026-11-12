"""Copie o conteudo de firmware/esp32 para a raiz do ESP32 (exceto tests)."""
import time
import config
from payload import PendingBuffer, build_payload, retry_delay
from sensors import PhysicalSensors, SensorError, SimulatedSensors


def validate_config(cfg):
    if cfg.INTERVAL_SECONDS < 2 or cfg.HTTP_TIMEOUT_SECONDS <= 0:
        raise ValueError("Intervalo minimo 2s; timeout positivo")
    if cfg.WIFI_ATTEMPTS < 1 or cfg.WIFI_TIMEOUT_SECONDS <= 0:
        raise ValueError("Configure ao menos uma tentativa Wi-Fi e timeout positivo")
    if cfg.ADC_SAMPLES < 1 or cfg.RAIN_ACTIVE_LEVEL not in (0, 1):
        raise ValueError("Amostras ADC/nivel de chuva invalidos")
    if cfg.BACKOFF_MAX_SECONDS < cfg.INTERVAL_SECONDS:
        raise ValueError("Backoff maximo deve ser maior ou igual ao intervalo")
    if cfg.SIMULATION and (not cfg.SIMULATION_STATION_ID.strip()
                           or cfg.SIMULATION_STATION_ID == cfg.STATION_ID):
        raise ValueError("Simulacao precisa de identificador proprio")
    if not cfg.SIMULATION and cfg.SEND_ENABLED and not cfg.ALLOW_RAW_ADC_UPLOAD:
        raise ValueError("Envio fisico bloqueado: reveja ADC bruto versus IQA/lux")

def run():
    validate_config(config)
    mode = "SIMULACAO" if config.SIMULATION else "FISICO / ADC BRUTO"
    print("[ATMOS] Modo:", mode)
    print("[ATMOS] Envio habilitado:", config.SEND_ENABLED)
    station = config.SIMULATION_STATION_ID if config.SIMULATION else config.STATION_ID
    wifi = client = None
    if config.SEND_ENABLED:
        from wifi_manager import WiFiManager
        from api_client import APIClient
        try:
            from secrets import WIFI_SSID, WIFI_PASSWORD
        except ImportError:
            raise ValueError("Crie secrets.py a partir de secrets.example.py na placa")
        wifi = WiFiManager(config, WIFI_SSID, WIFI_PASSWORD)
        client = APIClient(config)
    buffer = PendingBuffer(config.BUFFER_SIZE, config.BUFFER_MAX_AGE_SECONDS * 1000,
                           time.ticks_diff)
    sensors = None
    failures = 0
    while True:
        try:
            if sensors is None:
                sensors = SimulatedSensors() if config.SIMULATION else PhysicalSensors(config)
            payload = build_payload(station, sensors.read())
        except (SensorError, OSError, ValueError):
            print("[SENSOR] Leitura incompleta/invalida; nenhum dado enviado. Consulte diagnostico.")
            time.sleep(config.INTERVAL_SECONDS)
            continue
        if not config.SEND_ENABLED:
            print("[SEM ENVIO]", payload)
            time.sleep(config.INTERVAL_SECONDS)
            continue
        if buffer.add(payload, time.ticks_ms()):
            print("[BUFFER] Descartada leitura mais antiga (capacidade)")
        try:
            if not wifi.connect():
                raise OSError()
            from wifi_manager import sync_clock
            if client.target[0] == "https" and not sync_clock():
                raise OSError()
            expired = buffer.expire(time.ticks_ms())
            if expired:
                print("[BUFFER] Leituras expiradas:", expired)
            # Retira ANTES de iniciar POST. Uma tentativa por leitura, mesmo com
            # resposta perdida: API nao tem chave idempotente para deduplicar.
            pending = buffer.take()
            if pending is not None:
                status = client.post(pending)
                if status != 200:
                    print("[HTTP] Falha", status, "- leitura descartada; consulte README")
                    raise OSError()
                print("[HTTP] Leitura aceita (200)")
            failures = 0
        except (OSError, ValueError, ImportError, AttributeError) as error:
            # Nao imprime error: bibliotecas podem incluir URL, resposta ou segredo.
            print("[REDE/TLS] Falha; leituras ja tentadas nao serao reenviadas")
            failures += 1
        except Exception as error:
            from api_client import APIError
            if not isinstance(error, APIError):
                raise
            print("[HTTP/JSON] Resposta invalida; leitura nao sera reenviada")
            failures += 1
        time.sleep(retry_delay(failures, config.INTERVAL_SECONDS, config.BACKOFF_MAX_SECONDS))

if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("[ATMOS] Interrompido pelo console")
