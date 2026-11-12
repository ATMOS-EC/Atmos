"""Leituras fisicas ou simuladas; nunca substitui falha fisica por dado ficticio."""
import time


class SensorError(Exception):
    pass


class SimulatedSensors:
    def __init__(self):
        self.step = 0

    def read(self):
        self.step += 1
        phase = self.step % 20
        return {
            "temperatura": round(24.0 + phase * 0.2, 1),
            "umidade": round(70.0 - phase * 0.5, 1),
            "pressao": round(1010.0 + phase * 0.1, 1),
            "qualidade_ar": 900 + phase * 10,
            "luminosidade": 1800 + phase * 20,
            "chuva": phase in (17, 18, 19),
        }


class PhysicalSensors:
    def __init__(self, cfg):
        if not cfg.HARDWARE_CONFIRMED:
            raise SensorError("Confirme placa, pinagem e niveis eletricos em config.py")
        import dht
        from machine import ADC, I2C, Pin

        self.cfg = cfg
        self.dht = dht.DHT22(Pin(cfg.DHT_PIN))
        self.i2c = I2C(0, sda=Pin(cfg.I2C_SDA_PIN),
                       scl=Pin(cfg.I2C_SCL_PIN), freq=100000)
        self.bmp = None  # Inicializacao tardia permite testar os outros sensores isolados.
        self.mq = ADC(Pin(cfg.MQ135_PIN))
        self.ldr = ADC(Pin(cfg.LDR_PIN))
        for adc in (self.mq, self.ldr):
            adc.atten(ADC.ATTN_11DB)
            adc.width(ADC.WIDTH_12BIT)
        self.rain = Pin(cfg.RAIN_PIN, Pin.IN)
        self.started = time.ticks_ms()
        self.last_dht = None

    def _adc(self, adc):
        values = []
        for _ in range(self.cfg.ADC_SAMPLES):
            values.append(adc.read())
            time.sleep_ms(5)
        return sum(values) // len(values)

    def read_one(self, name):
        try:
            if name == "dht":
                now = time.ticks_ms()
                if self.last_dht is not None and time.ticks_diff(now, self.last_dht) < 2000:
                    raise SensorError("Aguarde 2 segundos entre leituras DHT22")
                self.last_dht = now
                self.dht.measure()
                return {"temperatura": self.dht.temperature(), "umidade": self.dht.humidity()}
            if name == "bmp":
                from lib.bmp280 import BMP280
                if self.bmp is None:
                    self.bmp = BMP280(self.i2c, self.cfg.BMP280_ADDRESS)
                try:
                    return {"pressao": self.bmp.pressure_hpa()}
                except OSError:
                    self.bmp = None
                    raise
            if name == "mq":
                if time.ticks_diff(time.ticks_ms(), self.started) < self.cfg.MQ135_WARMUP_SECONDS * 1000:
                    raise SensorError("MQ135 em aquecimento operacional")
                return {"qualidade_ar": self._adc(self.mq)}
            if name == "ldr":
                return {"luminosidade": self._adc(self.ldr)}
            if name == "rain":
                return {"chuva": self.rain.value() == self.cfg.RAIN_ACTIVE_LEVEL}
            raise ValueError("Sensor desconhecido")
        except OSError:
            raise SensorError("Falha de comunicacao com sensor: " + name)

    def read(self):
        reading = {}
        for name in ("dht", "bmp", "mq", "ldr", "rain"):
            reading.update(self.read_one(name))
        return reading
