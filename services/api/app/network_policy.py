"""Conservative HTTPS fetch with DNS pinning and bounded redirects/body."""

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urljoin, urlsplit


class FetchDenied(ValueError):
    pass


MAX_URL_LENGTH = 2048
MAX_FETCH_BYTES = 65536
MAX_REDIRECTS = 3


def validated_https_url(value: str) -> str:
    if not value or len(value) > MAX_URL_LENGTH or any(ord(char) < 33 or ord(char) == 127 for char in value) or "\\" in value:
        raise FetchDenied("HTTPS URL contains unsupported characters")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise FetchDenied("HTTPS URL is invalid") from exc
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or port not in {None, 443}:
        raise FetchDenied("Only public HTTPS URLs on port 443 are allowed")
    host = parsed.hostname
    if host.endswith(".") or ("." not in host and ":" not in host):
        raise FetchDenied("HTTPS URL must use a public hostname")
    return value


def public_addresses(host: str) -> list[str]:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if not literal.is_global:
            raise FetchDenied("HTTPS target resolves to a non-public address")
        return [str(literal)]
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchDenied("HTTPS hostname could not be resolved") from exc
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or len(addresses) > 16:
        raise FetchDenied("HTTPS hostname has no bounded address set")
    try:
        parsed = [ipaddress.ip_address(value) for value in addresses]
    except ValueError as exc:
        raise FetchDenied("HTTPS hostname returned an invalid address") from exc
    if not all(address.is_global for address in parsed):
        raise FetchDenied("HTTPS target resolves to a non-public address")
    return addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str) -> None:
        super().__init__(host, port=443, timeout=3, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        plain = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self._context.wrap_socket(plain, server_hostname=self.host)
        except OSError:
            plain.close()
            raise


def fetch_https_text(url: str) -> tuple[str, str]:
    """Return final URL and UTF-8 body; never connect to an unvalidated address."""
    current = validated_https_url(url)
    for redirect in range(MAX_REDIRECTS + 1):
        parsed = urlsplit(current)
        address = public_addresses(parsed.hostname or "")
        connection = PinnedHTTPSConnection(parsed.hostname or "", address[0])
        try:
            path = parsed.path or "/"
            if parsed.query:
                path += f"?{parsed.query}"
            connection.request("GET", path, headers={"Accept": "text/plain, text/markdown, text/html", "Accept-Encoding": "identity", "User-Agent": "NEXUS/1.0"})
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location")
                if not location or redirect == MAX_REDIRECTS:
                    raise FetchDenied("HTTPS redirect limit reached")
                current = validated_https_url(urljoin(current, location))
                continue
            if response.status != 200:
                raise FetchDenied(f"HTTPS target returned status {response.status}")
            media_type = (response.getheader("Content-Type") or "").split(";", 1)[0].lower().strip()
            if media_type not in {"text/plain", "text/markdown", "text/html"}:
                raise FetchDenied("HTTPS target did not return supported text")
            if (response.getheader("Content-Encoding") or "identity").lower() != "identity":
                raise FetchDenied("Compressed HTTPS responses are not supported")
            length = response.getheader("Content-Length")
            if length:
                try:
                    if int(length) > MAX_FETCH_BYTES:
                        raise FetchDenied("HTTPS response exceeds 64 KiB")
                except ValueError as exc:
                    raise FetchDenied("HTTPS response length is invalid") from exc
            body = response.read(MAX_FETCH_BYTES + 1)
            if len(body) > MAX_FETCH_BYTES:
                raise FetchDenied("HTTPS response exceeds 64 KiB")
            try:
                return current, body.decode("utf-8")
            except UnicodeError as exc:
                raise FetchDenied("HTTPS response must be UTF-8 text") from exc
        except (OSError, http.client.HTTPException) as exc:
            raise FetchDenied("HTTPS request failed") from exc
        finally:
            connection.close()
    raise FetchDenied("HTTPS redirect limit reached")
