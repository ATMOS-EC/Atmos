"""POST pequeno via sockets: timeout, TLS verificado e resposta limitada.

Sem redirects/reenvios automaticos; nao depende de requests/urequests.
"""
import json


class APIError(Exception):
    pass


def parse_url(url, allow_http=False):
    if not isinstance(url, str) or any(c in url for c in ("\r", "\n", " ", "#")):
        raise ValueError("URL invalida")
    scheme, sep, rest = url.partition("://")
    if not sep or scheme not in ("https", "http"):
        raise ValueError("Use uma URL http(s) completa")
    if scheme == "http" and not allow_http:
        raise ValueError("HTTP sem TLS desabilitado")
    authority, slash, path = rest.partition("/")
    if not authority or "@" in authority or "?" in authority or authority.count(":") > 1:
        raise ValueError("Host invalido; use DNS ou IPv4, sem credenciais")
    host, colon, port = authority.partition(":")
    port = int(port) if colon else (443 if scheme == "https" else 80)
    if not host or not 1 <= port <= 65535:
        raise ValueError("Host/porta invalido")
    if host.lower() in ("localhost", "127.0.0.1", "0.0.0.0") or host.startswith("127."):
        raise ValueError("Loopback aponta para o proprio ESP32")
    return scheme, host, port, "/" + path if slash else "/", authority


def write_all(stream, data):
    offset = 0
    while offset < len(data):
        sent = stream.write(data[offset:])
        if not sent:
            raise OSError("Conexao encerrada durante envio")
        offset += sent


def read_line(stream, limit):
    line = bytearray()
    while len(line) < limit:
        byte = stream.read(1)
        if not byte:
            raise APIError("Resposta HTTP incompleta")
        line.extend(byte)
        if byte == b"\n":
            return bytes(line)
    raise APIError("Cabecalho HTTP excede limite")


def read_response(stream):
    status_line = read_line(stream, 256)
    try:
        version, status, _ = status_line.decode().split(" ", 2)
        status = int(status)
        if version not in ("HTTP/1.0", "HTTP/1.1") or not 100 <= status <= 599:
            raise ValueError()
    except (ValueError, UnicodeError):
        raise APIError("Status HTTP invalido")
    headers = {}
    used = len(status_line)
    while used < 4096:
        line = read_line(stream, min(1024, 4096 - used))
        used += len(line)
        if line == b"\r\n":
            break
        if b":" not in line:
            raise APIError("Cabecalho HTTP invalido")
        key, value = line.split(b":", 1)
        headers[key.strip().lower()] = value.strip().lower()
    else:
        raise APIError("Cabecalhos HTTP excedem limite")
    # Erros/redirects nao precisam de corpo, que pode conter detalhes internos.
    if not 200 <= status < 300:
        return status
    if status != 200:
        raise APIError("Sucesso HTTP diferente do contrato esperado (200)")
    if b"transfer-encoding" in headers:
        raise APIError("Resposta chunked nao suportada; resultado do POST incerto")
    try:
        length = int(headers.get(b"content-length", b"-1"))
    except ValueError:
        raise APIError("Content-Length invalido")
    if not 0 < length <= 4096:
        raise APIError("Corpo JSON ausente ou excede 4096 bytes")
    body = bytearray()
    while len(body) < length:
        chunk = stream.read(min(512, length - len(body)))
        if not chunk:
            raise APIError("Corpo HTTP incompleto; resultado do POST incerto")
        body.extend(chunk)
    try:
        result = json.loads(bytes(body).decode())
    except (ValueError, UnicodeError):
        raise APIError("Resposta JSON invalida; resultado do POST incerto")
    if not isinstance(result, dict) or not isinstance(result.get("dados"), dict):
        raise APIError("Resposta diferente do contrato da API")
    return status


class APIClient:
    def __init__(self, cfg):
        self.cfg = cfg
        self.target = parse_url(cfg.API_URL, cfg.ALLOW_LOCAL_HTTP)

    def post(self, payload):
        import socket
        scheme, host, port, path, authority = self.target
        body = json.dumps(payload).encode()
        header = (
            "POST {} HTTP/1.0\r\nHost: {}\r\nContent-Type: application/json\r\n"
            "Accept: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n"
        ).format(path, authority, len(body)).encode()
        raw = None
        stream = None
        try:
            context = None
            if scheme == "https":
                import ssl
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
                context.verify_mode = ssl.CERT_REQUIRED
                context.load_verify_locations(cafile=self.cfg.TLS_CA_FILE)
            # getaddrinfo pode bloquear alem do timeout no port MicroPython.
            address = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0]
            raw = socket.socket(address[0], address[1], address[2])
            raw.settimeout(self.cfg.HTTP_TIMEOUT_SECONDS)
            raw.connect(address[-1])
            stream = context.wrap_socket(raw, server_hostname=host) if context else raw
            write_all(stream, header)
            write_all(stream, body)
            return read_response(stream)
        finally:
            # Fecha TLS e socket inclusive em falhas de handshake/JSON/timeout.
            if stream is not None:
                stream.close()
            if raw is not None and raw is not stream:
                raw.close()
