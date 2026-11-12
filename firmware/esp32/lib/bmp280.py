"""Driver I2C BMP280; compensacao float do datasheet Bosch, apendice 8.1.

Implementacao local, sem dependencia de pacote externo. Nao atende BME280.
"""
import struct
import time


class BMP280:
    def __init__(self, i2c, address=None):
        self.i2c = i2c
        if address is None:
            found = [a for a in i2c.scan() if a in (0x76, 0x77)]
            if len(found) != 1:
                raise OSError("BMP280 ausente ou enderecos ambiguos")
            address = found[0]
        if address not in (0x76, 0x77):
            raise ValueError("Endereco BMP280 invalido")
        self.address = address
        if self._read(0xD0, 1)[0] != 0x58:
            raise OSError("Chip nao e BMP280 (ID esperado 0x58)")
        self.i2c.writeto_mem(address, 0xE0, b"\xb6")
        time.sleep_ms(10)
        self._wait_ready(1)
        self.cal = struct.unpack("<HhhHhhhhhhhh", self._read(0x88, 24))
        if self.cal[3] == 0:
            raise OSError("Calibracao BMP280 invalida")

    def _read(self, register, length):
        return self.i2c.readfrom_mem(self.address, register, length)

    def _wait_ready(self, mask):
        start = time.ticks_ms()
        while self._read(0xF3, 1)[0] & mask:
            if time.ticks_diff(time.ticks_ms(), start) > 100:
                raise OSError("BMP280 ocupado: timeout")
            time.sleep_ms(2)

    def pressure_hpa(self):
        # Forced mode, temperatura x1, pressao x1. Cada chamada e uma nova conversao.
        self.i2c.writeto_mem(self.address, 0xF4, b"\x25")
        time.sleep_ms(10)
        self._wait_ready(8)
        data = self._read(0xF7, 6)
        raw_p = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_t = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        if raw_p == 0x80000 or raw_t == 0x80000:
            raise OSError("BMP280 sem conversao valida")
        return self.compensate(raw_t, raw_p) / 100.0

    def compensate(self, raw_t, raw_p):
        t1, t2, t3, p1, p2, p3, p4, p5, p6, p7, p8, p9 = self.cal
        v1 = (raw_t / 16384.0 - t1 / 1024.0) * t2
        v2 = ((raw_t / 131072.0 - t1 / 8192.0) ** 2) * t3
        fine = v1 + v2
        v1 = fine / 2.0 - 64000.0
        v2 = v1 * v1 * p6 / 32768.0
        v2 += v1 * p5 * 2.0
        v2 = v2 / 4.0 + p4 * 65536.0
        v1 = (p3 * v1 * v1 / 524288.0 + p2 * v1) / 524288.0
        v1 = (1.0 + v1 / 32768.0) * p1
        if v1 == 0:
            raise OSError("Divisor BMP280 invalido")
        pressure = (1048576.0 - raw_p - v2 / 4096.0) * 6250.0 / v1
        v1 = p9 * pressure * pressure / 2147483648.0
        v2 = pressure * p8 / 32768.0
        return pressure + (v1 + v2 + p7) / 16.0
