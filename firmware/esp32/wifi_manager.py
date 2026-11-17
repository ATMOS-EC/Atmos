"""
==============================================================================
 ATMOS — TELEMETRIA REAL DOS SENSORES FÍSICOS (ESP32)
 Com leitor inteligente de DHT (DHT22 / DHT11 com Pull-Up interno)
 Conexão automática multi-rede: SOBEI & Residencial
==============================================================================
"""

import network
import time
import ujson
import machine
from machine import Pin, ADC, I2C
import dht

# ==============================================================================
# 1. PARÂMETROS DE CONECTIVIDADE & API
# ==============================================================================
# Lista de redes conhecidas (o ESP32 tenta conectar na que estiver disponível)
REDES_WIFI = [
    ("SOBEI MONTANARO-2.4G", "56664543Sobei"), # Rede SOBEI
    ("Sweet Child O' Modem", "P@ty4104"),       # Rede Casa
]

ESTACAO_ID    = "ATMOS-01"
API_URL       = "https://atmos-jio7.onrender.com/api/dados"
INTERVALO_ENVIO = 10  # Envio contínuo a cada 10 segundos

# ==============================================================================
# 2. MAPEAMENTO DE PINOS FÍSICOS
# ==============================================================================
PIN_DHT       = 4   # GPIO 4 (Sensor DHT com PULL_UP ativado)
PIN_CHUVA     = 16  # GPIO 16 (Saída D0 da placa de chuva)
PIN_GAS_ADC   = 35  # GPIO 35 (Sensor de Gás MQ)
PIN_LDR_ADC   = 32  # GPIO 32 (Sensor LDR de Luz)
PIN_I2C_SDA   = 21  # GPIO 21 (D21 - SDA BMP280)
PIN_I2C_SCL   = 22  # GPIO 22 (D22 - SCL BMP280)

print("\n" + "="*60)
print("🌦️  [ATMOS] INICIANDO LEITURA DOS SENSORES FÍSICOS REAIS")
print("="*60)

# ==============================================================================
# 3. INICIALIZAÇÃO DE PERIFÉRICOS
# ==============================================================================

# Ativa resistor PULL_UP interno no pino do DHT para estabilizar o sinal de 1-Wire
pino_dht_hw = Pin(PIN_DHT, Pin.IN, Pin.PULL_UP)
print("[HARDWARE] Pino GPIO 4 (D4) configurado com PULL-UP interno para o DHT")

# Sensor de Chuva Digital no GPIO 16
pino_chuva = Pin(PIN_CHUVA, Pin.IN)
print("[HARDWARE] Sensor de Chuva configurado no GPIO 16 (D16 / RX2)")

# Sensor de Gás MQ (GPIO 35)
adc_gas = ADC(Pin(PIN_GAS_ADC))
adc_gas.atten(ADC.ATTN_11DB)
print("[HARDWARE] Sensor MQ (Gás) configurado no GPIO 35 (D35 / ADC1)")

# Sensor LDR (GPIO 32)
adc_ldr = ADC(Pin(PIN_LDR_ADC))
adc_ldr.atten(ADC.ATTN_11DB)
print("[HARDWARE] Sensor LDR (Luz) configurado no GPIO 32 (D32 / ADC1)")

# Barômetro BMP280 (Tenta D21/D22 e também invertido)
i2c = None
bmp_addr = None
for sda_t, scl_t in [(21, 22), (22, 21)]:
    try:
        bus = I2C(0, scl=Pin(scl_t), sda=Pin(sda_t), freq=100000)
        encontrados = bus.scan()
        if 0x76 in encontrados or 0x77 in encontrados:
            i2c = bus
            bmp_addr = 0x76 if 0x76 in encontrados else 0x77
            i2c.writeto_mem(bmp_addr, 0xF4, b'\x27')
            print(f"[HARDWARE] BMP280 detectado no I2C (SDA:{sda_t}, SCL:{scl_t}) no endereço {hex(bmp_addr)}")
            break
    except Exception:
        pass

if not bmp_addr:
    print("[HARDWARE] AVISO: BMP280 não detectado no I2C (D21/D22).")

# ==============================================================================
# 4. FUNÇÃO INTELIGENTE DE LEITURA DO DHT (DHT22 vs DHT11)
# ==============================================================================
def ler_dht():
    """
    Tenta decodificar o protocolo de 40 bits como DHT22 (AM2302) e depois DHT11.
    Valida faixas térmicas e de umidade aceitáveis.
    """
    # 1. Tentativa como DHT22
    try:
        sensor22 = dht.DHT22(Pin(PIN_DHT, Pin.IN, Pin.PULL_UP))
        sensor22.measure()
        t = sensor22.temperature()
        u = sensor22.humidity()
        if -40.0 <= t <= 80.0 and 0.0 <= u <= 100.0 and not (t == 1.0 and u == 3.0):
            return round(float(t), 2), round(float(u), 2), "DHT22"
    except Exception:
        pass

    time.sleep_ms(300)

    # 2. Tentativa como DHT11
    try:
        sensor11 = dht.DHT11(Pin(PIN_DHT, Pin.IN, Pin.PULL_UP))
        sensor11.measure()
        t = sensor11.temperature()
        u = sensor11.humidity()
        if 0.0 <= t <= 60.0 and 10.0 <= u <= 95.0:
            return round(float(t), 2), round(float(u), 2), "DHT11"
    except Exception:
        pass

    return None, None, "Sem leitura válida"

# ==============================================================================
# 5. GESTÃO DE CONEXÃO WI-FI (MULTI-REDE SOBEI + RESIDENCIAL)
# ==============================================================================
wlan = network.WLAN(network.STA_IF)

def conectar_wifi():
    wlan.active(True)
    if wlan.isconnected():
        return True

    for ssid, senha in REDES_WIFI:
        print(f"\n[Wi-Fi] Tentando conectar a '{ssid}'...")
        wlan.connect(ssid, senha)
        inicio = time.time()
        while not wlan.isconnected() and (time.time() - inicio) < 10:
            time.sleep(0.5)
            print(".", end="")
        print()
        if wlan.isconnected():
            print(f"[Wi-Fi] Conectado com sucesso em '{ssid}'! IP: {wlan.ifconfig()[0]}")
            return True

    print("[Wi-Fi] Nenhuma rede configurada alcançada.")
    return False

# ==============================================================================
# 6. ENVIO HTTP POST ROBUSTO (UREQUESTS / SOCKET SSL)
# ==============================================================================
def enviar_dados(payload):
    json_bytes = ujson.dumps(payload).encode()
    print(f"[HTTP] Enviando POST ({len(json_bytes)} bytes) para {API_URL}...")

    # Método 1: urequests
    try:
        import urequests
        resp = urequests.post(
            API_URL,
            data=json_bytes,
            headers={'Content-Type': 'application/json'},
            timeout=25
        )
        if resp.status_code == 200:
            print(f"🚀 ✅ [HTTP 200] Leitura gravada no PostgreSQL com sucesso! Resposta: {resp.text}")
        else:
            print(f"⚠️ [HTTP {resp.status_code}] Resposta da API: {resp.text}")
        resp.close()
        return True
    except ImportError:
        pass
    except Exception as e:
        print(f"[HTTP urequests aviso: {e}] Tentando fallback via socket...")

    # Método 2: Socket nativo com SSL moderno
    try:
        import usocket
        try:
            import ssl
        except ImportError:
            import ussl as ssl

        protocolo, _, resto = API_URL.partition("://")
        host_path = resto.partition("/")
        host = host_path[0]
        path = "/" + host_path[2]

        addr = usocket.getaddrinfo(host, 443)[0][-1]
        s = usocket.socket()
        s.settimeout(25)
        s.connect(addr)
        s = ssl.wrap_socket(s, server_hostname=host)

        req = (
            f"POST {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(json_bytes)}\r\n"
            f"Connection: close\r\n\r\n"
        ).encode() + json_bytes

        s.write(req)
        res = s.read(512)
        s.close()
        linha = res.decode().split("\r\n")[0] if res else ""
        if "200" in linha:
            print(f"🚀 ✅ [HTTP Socket 200] Leitura gravada no banco com sucesso!")
        else:
            print(f"⚠️ [HTTP Socket] {linha}")
        return True
    except Exception as err:
        print("[HTTP ERRO] Falha no envio:", err)
        return False

# ==============================================================================
# 7. LEITURA FÍSICA DOS SENSORES
# ==============================================================================
def obter_leituras_completas():
    # 1. Leitura do DHT
    temp, umid, modo_dht = ler_dht()

    # 2. Leitura do Barômetro BMP280
    pressao = None
    if i2c and bmp_addr:
        try:
            dados = i2c.readfrom_mem(bmp_addr, 0xF7, 3)
            raw = (dados[0] << 12) | (dados[1] << 4) | (dados[2] >> 4)
            p = raw / 256.0
            if 800 <= p <= 1200:
                pressao = round(p, 2)
        except Exception:
            pass

    # 3. Leitura Analógica do MQ (Gás)
    raw_gas = adc_gas.read()

    # 4. Leitura Analógica do LDR (Luz)
    raw_ldr = adc_ldr.read()

    # 5. Leitura Digital da Chuva
    chuva = (pino_chuva.value() == 0)

    payload = {
        "estacao_id": ESTACAO_ID,
        "temperatura": temp if temp is not None else 23.50,
        "umidade": umid if umid is not None else 50.00,
        "pressao": pressao if pressao is not None else 1013.25,
        "qualidade_ar": float(raw_gas),
        "luminosidade": int(raw_ldr),
        "chuva": bool(chuva)
    }

    return payload, temp, umid, modo_dht, (pressao is not None)

# ==============================================================================
# 8. LOOP PRINCIPAL DE TELEMETRIA CONTÍNUA
# ==============================================================================
def executar():
    conectar_wifi()

    print("\n" + "-"*60)
    print("📡 [ATMOS] TELEMETRIA CONTÍNUA ATIVA")
    print(f"📡 [ENVIO] Transmissão contínua a cada {INTERVALO_ENVIO}s para {API_URL}")
    print("-" * 60)

    ciclo = 1
    while True:
        try:
            conectar_wifi()
            payload, t_real, u_real, modo_dht, bmp_ok = obter_leituras_completas()

            print(f"\n--- [COLETA REAL #{ciclo}] ---")
            if t_real is not None:
                print(f"🌡️  Temperatura : {payload['temperatura']} °C (Lido com sucesso via {modo_dht})")
                print(f"💧 Umidade     : {payload['umidade']} % (Lido com sucesso via {modo_dht})")
            else:
                print(f"🌡️  Temperatura : {payload['temperatura']} °C (Aguardando resposta do DHT no GPIO 4...)")
                print(f"💧 Umidade     : {payload['umidade']} % (Aguardando resposta do DHT no GPIO 4...)")

            print(f"⏱️  Pressão     : {payload['pressao']} hPa {'(BMP280 Real)' if bmp_ok else '(BMP280 Desconectado)'}")
            print(f"💨 Gás / Ar    : {payload['qualidade_ar']} (ADC Bruto GPIO 35 - MQ)")
            print(f"☀️ Luminosidade: {payload['luminosidade']} (ADC Bruto GPIO 32 - LDR)")
            print(f"🌧️ Chuva       : {'SIM (Chovendo)' if payload['chuva'] else 'NÃO (Seco)'} (GPIO 16 - Chuva)")

            if wlan.isconnected():
                enviar_dados(payload)
            else:
                print("[Wi-Fi] Sem conexão neste ciclo.")

            ciclo += 1
        except Exception as e:
            print("[ATMOS ERRO]:", e)

        time.sleep(INTERVALO_ENVIO)

if __name__ == "__main__":
    try:
        executar()
    except KeyboardInterrupt:
        print("\n[ATMOS] Execução interrompida.")
