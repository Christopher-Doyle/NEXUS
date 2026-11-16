import pytest

from app.network_policy import FetchDenied, fetch_https_text, public_addresses, validated_https_url


@pytest.mark.parametrize("url", [
    "http://example.com/", "https://localhost/", "https://example.com:8443/",
    "https://user:pass@example.com/", "https://example.com/#secret",
    "https://example.com\\@127.0.0.1/", "https://example.com/\nHost: evil",
])
def test_only_unambiguous_https_urls_are_accepted(url) -> None:
    with pytest.raises(FetchDenied):
        validated_https_url(url)


def test_dns_rejects_any_private_answer(monkeypatch) -> None:
    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [
        (None, None, None, None, ("93.184.215.14", 443)),
        (None, None, None, None, ("127.0.0.1", 443)),
    ])
    with pytest.raises(FetchDenied, match="non-public"):
        public_addresses("example.com")


def test_fetch_pins_public_dns_and_revalidates_redirect(monkeypatch) -> None:
    connections = []

    class Response:
        status = 200

        def getheader(self, name):
            return {"Content-Type": "text/plain", "Content-Length": "5"}.get(name)

        def read(self, _limit):
            return b"Notes"

    class Connection:
        def __init__(self, host, address):
            connections.append((host, address))

        def request(self, method, path, headers):
            assert method == "GET"
            assert path == "/notes"
            assert headers["Accept-Encoding"] == "identity"

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.215.14", 443))])
    monkeypatch.setattr("app.network_policy.PinnedHTTPSConnection", Connection)
    assert fetch_https_text("https://example.com/notes") == ("https://example.com/notes", "Notes")
    assert connections == [("example.com", "93.184.215.14")]

    class Redirect(Response):
        status = 302

        def getheader(self, name):
            return "https://127.0.0.1/private" if name == "Location" else None

    monkeypatch.setattr(Connection, "getresponse", lambda self: Redirect())
    with pytest.raises(FetchDenied, match="non-public"):
        fetch_https_text("https://example.com/notes")


def test_fetch_rejects_oversized_response(monkeypatch) -> None:
    class Response:
        status = 200

        def getheader(self, name):
            return "text/plain" if name == "Content-Type" else None

        def read(self, limit):
            return b"x" * limit

    class Connection:
        def __init__(self, _host, _address):
            pass

        def request(self, *_args, **_kwargs):
            pass

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr("app.network_policy.socket.getaddrinfo", lambda *_args, **_kwargs: [(None, None, None, None, ("93.184.215.14", 443))])
    monkeypatch.setattr("app.network_policy.PinnedHTTPSConnection", Connection)
    with pytest.raises(FetchDenied, match="exceeds"):
        fetch_https_text("https://example.com/notes")
