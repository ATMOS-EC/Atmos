"""Reconexao limitada, sem registrar SSID ou senha."""
import time


class WiFiManager:
    def __init__(self, cfg, ssid, password):
        import network
        self.cfg = cfg
        self.ssid = ssid
        self.password = password
        interface = getattr(network.WLAN, "IF_STA", None)
        if interface is None:
            interface = network.STA_IF
        self.wlan = network.WLAN(interface)
        self.wlan.active(True)
        # ESP32 suporta limitar as tentativas internas do driver.
        self.wlan.config(reconnects=0)

    def connect(self):
        if self.wlan.isconnected():
            return True
        if not self.ssid or not self.password:
            return False
        for attempt in range(self.cfg.WIFI_ATTEMPTS):
            try:
                self.wlan.disconnect()
                self.wlan.connect(self.ssid, self.password)
                start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), start) < self.cfg.WIFI_TIMEOUT_SECONDS * 1000:
                    if self.wlan.isconnected():
                        print("[WIFI] Conectado")
                        return True
                    if self.wlan.status() < 0:
                        break
                    time.sleep_ms(250)
                self.wlan.disconnect()
            except OSError:
                print("[WIFI] Falha na tentativa", attempt + 1)
            if attempt + 1 < self.cfg.WIFI_ATTEMPTS:
                time.sleep(min(2 ** attempt, 4))
        print("[WIFI] Limite de tentativas atingido")
        return False


def sync_clock():
    # NTP e necessario para verificar a validade dos certificados HTTPS.
    # Tambem e possivel ajustar RTC por USB antes de iniciar.
    if time.gmtime()[0] >= 2025:
        return True
    try:
        import ntptime
        ntptime.timeout = 5
        ntptime.settime()
        return time.gmtime()[0] >= 2025
    except (OSError, ImportError):
        print("[TLS] Ajuste o RTC por USB ou permita acesso ao NTP")
        return False
