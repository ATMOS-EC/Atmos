"""Testes CPython isolados: nao importam .env, nao usam rede nem hardware."""
import io
import json
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import config
from api_client import APIClient, APIError, parse_url, read_response, write_all
from lib.bmp280 import BMP280
from main import validate_config
from payload import PendingBuffer, build_payload, retry_delay
from sensors import PhysicalSensors, SensorError, SimulatedSensors


def response(body, status=200):
    return io.BytesIO(("HTTP/1.1 %s OK\r\nContent-Length: %s\r\n\r\n" %
                       (status, len(body))).encode() + body)


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.reading = SimulatedSensors().read()

    def test_many_simulated_readings_match_actual_pydantic_model(self):
        # Abre SOMENTE o modelo, nunca config.py/main.py do backend (load_dotenv).
        model_path = ROOT.parents[1] / "backend/app/models/leitura.py"
        namespace = {}
        exec(compile(model_path.read_text(encoding="utf-8"), str(model_path), "exec"), namespace)
        model = namespace["DadosSensores"]
        sensors = SimulatedSensors()
        for _ in range(100):
            payload = build_payload("ATMOS-SIM-01", sensors.read())
            parsed = model(**json.loads(json.dumps(payload)))
            self.assertEqual(parsed.estacao_id, "ATMOS-SIM-01")
            self.assertIs(type(parsed.chuva), bool)

    def test_required_fields_and_types(self):
        self.assertEqual(set(build_payload("SIM", self.reading)), {
            "estacao_id", "temperatura", "umidade", "pressao", "qualidade_ar",
            "luminosidade", "chuva"})
        for key in self.reading:
            invalid = dict(self.reading)
            del invalid[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_payload("SIM", invalid)

    def test_invalid_values(self):
        for key, value in (("umidade", 101), ("temperatura", float("nan")),
                           ("pressao", float("inf")), ("qualidade_ar", -1),
                           ("luminosidade", 2.5), ("chuva", 1), ("temperatura", True)):
            invalid = dict(self.reading)
            invalid[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_payload("SIM", invalid)

    def test_empty_station(self):
        with self.assertRaises(ValueError):
            build_payload(" ", self.reading)

    def test_config_defaults_safe(self):
        validate_config(config)
        self.assertTrue(config.SIMULATION)
        self.assertFalse(config.SEND_ENABLED)
        cfg = types.SimpleNamespace(**{k: getattr(config, k) for k in dir(config) if k.isupper()})
        cfg.SIMULATION = False
        cfg.SEND_ENABLED = True
        with self.assertRaises(ValueError):
            validate_config(cfg)
        cfg.SIMULATION = True
        cfg.SIMULATION_STATION_ID = cfg.STATION_ID
        with self.assertRaises(ValueError):
            validate_config(cfg)


class ReliabilityTests(unittest.TestCase):
    def test_buffer_capacity_expiry_and_consumption(self):
        queue = PendingBuffer(2, 100, lambda a, b: a - b)
        self.assertFalse(queue.add("old", 0))
        queue.add("middle", 30)
        self.assertTrue(queue.add("new", 60))
        self.assertEqual(queue.expire(130), 1)
        self.assertEqual(queue.take(), "new")
        self.assertIsNone(queue.take())

    def test_ticks_wraparound(self):
        diff = lambda a, b: ((a - b + 512) % 1024) - 512
        queue = PendingBuffer(2, 100, diff)
        queue.add("sample", 1000)
        self.assertEqual(queue.expire(80), 1)

    def test_backoff_is_bounded(self):
        self.assertEqual([retry_delay(n, 60, 300) for n in range(6)],
                         [60, 60, 120, 240, 300, 300])

    def test_physical_requires_confirmation(self):
        with self.assertRaises(SensorError):
            PhysicalSensors(config)


class BMPTests(unittest.TestCase):
    def test_bosch_reference_compensation(self):
        bmp = BMP280.__new__(BMP280)
        bmp.cal = (27504, 26435, -1000, 36477, -10685, 3024,
                   2855, 140, -7, 15500, -14600, 6000)
        self.assertAlmostEqual(bmp.compensate(519888, 415148), 100653.27, places=2)

    def test_i2c_driver_address_and_pascal_conversion(self):
        calibration = struct.pack("<HhhHhhhhhhhh", 27504, 26435, -1000, 36477,
                                  -10685, 3024, 2855, 140, -7, 15500, -14600, 6000)
        raw = bytes((0x65, 0x5A, 0xC0, 0x7E, 0xED, 0x00))
        class I2C:
            def scan(self): return [0x76]
            def readfrom_mem(self, address, register, length):
                return {0xD0: b"\x58", 0xF3: b"\0", 0x88: calibration, 0xF7: raw}[register]
            def writeto_mem(self, *args): pass
        with patch("lib.bmp280.time.sleep_ms", create=True), \
                patch("lib.bmp280.time.ticks_ms", return_value=0, create=True):
            bmp = BMP280(I2C())
            self.assertAlmostEqual(bmp.pressure_hpa(), 1006.5327, places=4)
        bus = I2C()
        bus.scan = lambda: [0x76, 0x77]
        with self.assertRaises(OSError): BMP280(bus)
        bus.scan = lambda: []
        with self.assertRaises(OSError): BMP280(bus)


class HTTPTests(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(parse_url("https://example.com/api/dados")[:4],
                         ("https", "example.com", 443, "/api/dados"))
        self.assertEqual(parse_url("http://192.168.1.5:8000/api/dados", True)[2], 8000)
        for url in ("http://example.com/", "https://localhost/", "https://127.0.0.2/",
                    "https://user:password@example.com/", "https://example.com/\r\nx", "ftp://x"):
            with self.subTest(url=url), self.assertRaises(ValueError): parse_url(url)

    def test_success_json(self):
        body = json.dumps({"mensagem": "ok", "dados": {}}).encode()
        self.assertEqual(read_response(response(body)), 200)

    def test_http_error_needs_no_body(self):
        for status in (301, 422, 429, 503):
            self.assertEqual(read_response(response(b"", status)), status)

    def test_bad_json_truncated_or_large_response(self):
        for data in (b"not json", b"[]", b'{}'):
            with self.assertRaises(APIError): read_response(response(data))
        for data in (b"HTTP/1.1 200 OK\r\nContent-Length: 8000\r\n\r\n",
                     b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\n{}",
                     b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n",
                     b"garbage\r\n", b"HTTP/1.1 200 OK\r\nX: " + b"a" * 5000):
            with self.assertRaises(APIError): read_response(io.BytesIO(data))

    def test_partial_write(self):
        class Stream:
            data = b""
            def write(self, data):
                self.data += data[:2]
                return len(data[:2])
        stream = Stream()
        write_all(stream, b"abcdefg")
        self.assertEqual(stream.data, b"abcdefg")

    def test_timeout_closes_socket_without_retry(self):
        class Socket:
            closed = False
            writes = 0
            def settimeout(self, value): self.timeout = value
            def connect(self, address): pass
            def write(self, data):
                self.writes += 1
                raise OSError("timeout")
            def close(self): self.closed = True
        sock = Socket()
        cfg = types.SimpleNamespace(API_URL="http://192.168.1.5/api/dados", ALLOW_LOCAL_HTTP=True,
                                    HTTP_TIMEOUT_SECONDS=20)
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.168.1.5", 80))]), \
                patch("socket.socket", return_value=sock):
            with self.assertRaises(OSError): APIClient(cfg).post({})
        self.assertTrue(sock.closed)
        self.assertEqual(sock.writes, 1)
        self.assertEqual(sock.timeout, 20)


class MainLoopTests(unittest.TestCase):
    def test_offline_buffer_then_uncertain_post_is_never_retried(self):
        import main
        cfg = types.SimpleNamespace(**{k: getattr(config, k) for k in dir(config) if k.isupper()})
        cfg.SEND_ENABLED = True
        posts = []
        clock = [0]
        class WiFi:
            attempts = 0
            def __init__(self, *args): pass
            def connect(self):
                self.attempts += 1
                return self.attempts > 1
        class Client:
            target = ("https",)
            def __init__(self, *args): pass
            def post(self, payload):
                posts.append(payload)
                if len(posts) == 1: raise OSError("resposta perdida")
                return 200
        def sleep(seconds):
            clock[0] += seconds * 1000
            if len(posts) == 2: raise KeyboardInterrupt()
        modules = {
            "secrets": types.SimpleNamespace(WIFI_SSID="fake", WIFI_PASSWORD="fake"),
            "wifi_manager": types.SimpleNamespace(WiFiManager=WiFi, sync_clock=lambda: True),
            "api_client": types.SimpleNamespace(APIClient=Client, APIError=APIError),
        }
        with patch.dict(sys.modules, modules), patch.object(main, "config", cfg), \
                patch("main.time.ticks_ms", side_effect=lambda: clock[0], create=True), \
                patch("main.time.ticks_diff", side_effect=lambda a, b: a - b, create=True), \
                patch("main.time.sleep", side_effect=sleep), patch("builtins.print"):
            with self.assertRaises(KeyboardInterrupt): main.run()
        self.assertEqual(len(posts), 2)
        self.assertNotEqual(posts[0]["temperatura"], posts[1]["temperatura"])
        self.assertTrue(all(p["estacao_id"] == "ATMOS-SIM-01" for p in posts))


class PeripheralTests(unittest.TestCase):
    def test_dht_interval_adc_and_rain_polarity_without_bmp(self):
        cfg = types.SimpleNamespace(**{k: getattr(config, k) for k in dir(config) if k.isupper()})
        cfg.HARDWARE_CONFIRMED = True
        cfg.MQ135_WARMUP_SECONDS = 1
        clock = [0]
        class Pin:
            IN = 0
            def __init__(self, *args): pass
            def value(self): return 0
        class ADC:
            ATTN_11DB = 3
            WIDTH_12BIT = 12
            def __init__(self, pin): pass
            def atten(self, value): pass
            def width(self, value): pass
            def read(self): return 1234
        class DHT:
            def __init__(self, pin): pass
            def measure(self): pass
            def temperature(self): return 26.5
            def humidity(self): return 65.0
        modules = {
            "machine": types.SimpleNamespace(Pin=Pin, ADC=ADC, I2C=lambda *a, **kw: None),
            "dht": types.SimpleNamespace(DHT22=DHT),
        }
        with patch.dict(sys.modules, modules), \
                patch("sensors.time.ticks_ms", side_effect=lambda: clock[0], create=True), \
                patch("sensors.time.ticks_diff", side_effect=lambda a, b: a - b, create=True), \
                patch("sensors.time.sleep_ms", create=True):
            sensors = PhysicalSensors(cfg)
            self.assertEqual(sensors.read_one("dht")["temperatura"], 26.5)
            with self.assertRaises(SensorError): sensors.read_one("dht")
            with self.assertRaises(SensorError): sensors.read_one("mq")
            clock[0] = 2000
            self.assertEqual(sensors.read_one("dht")["umidade"], 65.0)
            self.assertEqual(sensors.read_one("mq")["qualidade_ar"], 1234)
            self.assertEqual(sensors.read_one("ldr")["luminosidade"], 1234)
            self.assertIs(sensors.read_one("rain")["chuva"], True)
            cfg.RAIN_ACTIVE_LEVEL = 1
            self.assertIs(sensors.read_one("rain")["chuva"], False)

    def test_wifi_reconnect_attempts_are_bounded(self):
        from wifi_manager import WiFiManager
        cfg = types.SimpleNamespace(WIFI_ATTEMPTS=3, WIFI_TIMEOUT_SECONDS=1)
        class WLAN:
            IF_STA = 0
            attempts = 0
            def __init__(self, interface): pass
            def active(self, value): pass
            def config(self, **kwargs): pass
            def isconnected(self): return False
            def disconnect(self): pass
            def connect(self, *args): self.attempts += 1
            def status(self): return -1
        network = types.SimpleNamespace(WLAN=WLAN)
        with patch.dict(sys.modules, {"network": network}), \
                patch("wifi_manager.time.ticks_ms", return_value=0, create=True), \
                patch("wifi_manager.time.ticks_diff", return_value=0, create=True), \
                patch("wifi_manager.time.sleep"), patch("builtins.print"):
            wifi = WiFiManager(cfg, "fake", "fake")
            self.assertFalse(wifi.connect())
            self.assertEqual(wifi.wlan.attempts, 3)

    def test_tls_requires_ca_hostname_and_closes_both_streams(self):
        body = b'{"dados":{}}'
        class Socket:
            closed = False
            def settimeout(self, value): pass
            def connect(self, address): pass
            def close(self): self.closed = True
        class Stream(io.BytesIO):
            def write(self, data): return len(data)
        stream = Stream(response(body).getvalue())
        raw = Socket()
        class Context:
            def __init__(self, protocol): self.protocol = protocol
            def load_verify_locations(self, **kwargs): self.ca = kwargs["cafile"]
            def wrap_socket(self, sock, server_hostname):
                self.hostname = server_hostname
                return stream
        context = Context(1)
        ssl = types.SimpleNamespace(SSLContext=lambda p: context,
                                    PROTOCOL_TLS_CLIENT=1, CERT_REQUIRED=2)
        cfg = types.SimpleNamespace(API_URL="https://example.com/api/dados", ALLOW_LOCAL_HTTP=False,
                                    HTTP_TIMEOUT_SECONDS=20, TLS_CA_FILE="ca.der")
        with patch.dict(sys.modules, {"ssl": ssl}), \
                patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("example.com", 443))]), \
                patch("socket.socket", return_value=raw):
            self.assertEqual(APIClient(cfg).post({}), 200)
        self.assertEqual(context.verify_mode, 2)
        self.assertEqual(context.hostname, "example.com")
        self.assertEqual(context.ca, "ca.der")
        self.assertTrue(raw.closed)
        self.assertTrue(stream.closed)


if __name__ == "__main__":
    unittest.main()
