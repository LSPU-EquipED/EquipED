"""Exercise production HTTPS parsing at resolver/TLS-stream boundaries, not live I/O."""

import asyncio
import gzip
import os
import socket
import ssl

import pytest
from equiped_harness.agents.itso.tools.contracts import Code, VerificationError
from equiped_harness.tools.http import (
    DOCUMENT_LIMIT,
    LIMIT,
    PinnedHTTPS,
    Request,
    public_address,
    validate_url,
)
from pydantic import SecretStr


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example/",
        "https://public.example:444/",
        "https://user:pw@public.example/",
        "https://public.example/#fragment",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://public.example/?X-Amz-Signature=secret",
        "https://public.example/?token=signed",
        "https://public.example/?utm_source=tracking",
        "https://public.example/?id=ok&auth=bad",
        "https://public.example/file.pdf",
        "https://public.example/%0d%0aX-Evil:true",
        "https://public.example\\@127.0.0.1/",
        "https://public.example./",
        "https://a..example/",
        "https://public.example/?id=" + "x" * 181,
        "https://public.example/?invalid",
        "https://books.google.com/books?id=abc&redir_esc=n",
        "https://books.google.com.evil.example/books?id=abc&redir_esc=y",
        "https://books.google.com/other?id=abc&redir_esc=y",
        "https://example.org/books?id=abc&redir_esc=y",
    ],
)
def test_unsafe_url_rejected(url):
    with pytest.raises(VerificationError, match="unsafe_destination"):
        validate_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://books.google.com/books?id=abc&redir_esc=y",
        "https://books.google.com.ph/books?id=abc&redir_esc=y",
    ],
)
def test_google_books_catalogue_redirect_query_is_narrowly_allowed(url):
    assert validate_url(url) in {"books.google.com", "books.google.com.ph"}


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.1",
        "172.16.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "192.0.2.1",
        "100.64.0.1",
        "224.0.0.1",
        "240.0.0.1",
        "::1",
        "::",
        "fe80::1",
        "fc00::1",
        "2001:db8::1",
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
    ],
)
def test_ip_denylist_including_mapped(ip):
    with pytest.raises(VerificationError):
        public_address(ip)


class Writer:
    def __init__(self, peer="93.184.216.34"):
        self.peer = peer
        self.sent = bytearray()
        self.closed = False

    def get_extra_info(self, name):
        assert name == "peername"
        return self.peer, 443

    def write(self, value):
        self.sent.extend(value)

    async def drain(self):
        pass

    def close(self):
        self.closed = True


def raw_response(body=b"{}", headers=None, status=200):
    h = {"Content-Type": "application/json", "Content-Length": str(len(body))}
    h.update(headers or {})
    return (
        f"HTTP/1.1 {status} Synthetic\r\n"
        + "\r\n".join(f"{k}: {v}" for k, v in h.items())
        + "\r\n\r\n"
    ).encode() + body


def make_transport(
    raw=None, addresses=("93.184.216.34",), peer="93.184.216.34", clock=lambda: 100.0
):
    writer = Writer(peer)
    events = []

    async def resolver(host):
        events.append(("dns", host))
        return [
            (
                socket.AF_INET6 if ":" in ip else socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (ip, 443),
            )
            for ip in addresses
        ]

    async def connector(host, port, **kwargs):
        events.append(("connect", host, port, kwargs))
        reader = asyncio.StreamReader(limit=LIMIT + 1)
        reader.feed_data(raw if raw is not None else raw_response())
        reader.feed_eof()
        return reader, writer

    return (
        PinnedHTTPS(resolver=resolver, connector=connector, clock=clock),
        writer,
        events,
    )


def test_dns_validate_all_then_pin_sni_host_peer_no_ambient_auth(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    transport, writer, events = make_transport()
    result = run(
        transport.get(
            Request("https://api.crossref.org/works/10.1234%2Fsynthetic", "crossref"),
            105,
        )
    )
    assert result.status == 200
    assert events[0] == ("dns", "api.crossref.org")
    assert events[1][1:3] == ("93.184.216.34", 443)
    options = events[1][3]
    assert options["server_hostname"] == "api.crossref.org"
    assert (
        options["ssl"].verify_mode == ssl.CERT_REQUIRED
        and options["ssl"].check_hostname
    )
    assert b"Host: api.crossref.org\r\n" in writer.sent
    assert b"GET /works/10.1234%2Fsynthetic HTTP/1.1" in writer.sent
    assert b"Authorization" not in writer.sent and b"Cookie" not in writer.sent
    assert writer.closed


@pytest.mark.parametrize(
    "addresses", [("93.184.216.34", "127.0.0.1"), ("::ffff:10.0.0.1",), ()]
)
def test_all_dns_answers_validated_before_any_socket(addresses):
    transport, writer, events = make_transport(addresses=addresses)
    with pytest.raises(VerificationError):
        run(transport.get(Request("https://public.example/reference", "document"), 105))
    assert len(events) == 1 and not writer.sent


def test_peer_rebind_blocked_before_http_write():
    transport, writer, events = make_transport(peer="93.184.216.35")
    with pytest.raises(VerificationError, match="unsafe_destination"):
        run(transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105))
    assert len(events) == 2 and not writer.sent and writer.closed


def test_brave_token_header_is_fixed_host_only_never_page_or_crossref():
    token = SecretStr("synthetic-token")
    transport, writer, _ = make_transport()
    run(
        transport.get(
            Request(
                "https://api.search.brave.com/res/v1/web/search?q=Synthetic",
                "brave",
                token,
            ),
            105,
        )
    )
    assert b"X-Subscription-Token: synthetic-token\r\n" in writer.sent
    for url, kind in (
        ("https://public.example/reference", "document"),
        ("https://api.crossref.org/works/x", "crossref"),
        ("https://api.crossref.org/works/x", "brave"),
    ):
        transport, writer, events = make_transport()
        with pytest.raises(VerificationError):
            run(transport.get(Request(url, kind, token), 105))
        assert not events and not writer.sent


def test_duckduckgo_html_provider_is_pinned_and_credential_free():
    html = b"<html></html>"
    transport, writer, events = make_transport(
        raw_response(html, {"Content-Type": "text/html; charset=utf-8"})
    )
    result = run(
        transport.get(
            Request("https://html.duckduckgo.com/html/?q=approved", "duckduckgo"),
            105,
        )
    )
    assert result.body == html
    assert events[0] == ("dns", "html.duckduckgo.com")
    assert b"Accept: text/html\r\n" in writer.sent
    assert b"X-Subscription-Token" not in writer.sent
    for request in (
        Request("https://api.search.brave.com/res/v1/web/search?q=x", "duckduckgo"),
        Request("https://html.duckduckgo.com/html/?q=x", "duckduckgo", SecretStr("x")),
    ):
        transport, writer, events = make_transport()
        with pytest.raises(VerificationError):
            run(transport.get(request, 105))
        assert not events and not writer.sent


def test_transport_does_not_follow_redirect_or_forward_token():
    raw = raw_response(b"", {"Location": "https://other.example/"}, 302)
    transport, writer, events = make_transport(raw)
    result = run(
        transport.get(
            Request(
                "https://api.search.brave.com/res/v1/web/search?q=Synthetic",
                "brave",
                SecretStr("synthetic"),
            ),
            105,
        )
    )
    assert result.status == 302 and result.body == b"" and len(events) == 2
    assert writer.sent.count(b"GET ") == 1


@pytest.mark.parametrize(
    "raw,code",
    [
        (raw_response(b"x" * (LIMIT + 1)), Code.LIMIT),
        (
            raw_response(
                gzip.compress(b"x" * (LIMIT + 1)), {"Content-Encoding": "gzip"}
            ),
            Code.LIMIT,
        ),
        (
            raw_response(
                gzip.compress(b"x") + gzip.compress(b"y"), {"Content-Encoding": "gzip"}
            ),
            Code.MALFORMED,
        ),
        (raw_response(b"bad", {"Content-Encoding": "gzip"}), Code.MALFORMED),
        (raw_response(b"{}", {"Content-Type": "application/pdf"}), Code.MALFORMED),
        (raw_response(b"\xff", {"Content-Type": "application/json"}), Code.MALFORMED),
        (
            b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nContent-Length: 0\r\n\r\n",
            Code.MALFORMED,
        ),
        (raw_response(b"", {"Transfer-Encoding": "chunked"}), Code.MALFORMED),
        (b"HTTP/1.1 200 OK\r\nX-Huge: " + b"x" * 17000 + b"\r\n\r\n", Code.LIMIT),
        (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n20001\r\n",
            Code.LIMIT,
        ),
    ],
)
def test_response_stream_bounds_and_strict_format(raw, code):
    transport, writer, _ = make_transport(raw)
    with pytest.raises(VerificationError) as exc:
        run(transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105))
    assert exc.value.code == code and writer.closed


def test_streamed_gzip_and_chunked_and_exact_limit():
    for raw, expected in (
        (
            raw_response(
                gzip.compress(b'{"synthetic":true}'), {"Content-Encoding": "gzip"}
            ),
            b'{"synthetic":true}',
        ),
        (
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n",
            b"{}",
        ),
        (raw_response(b"x" * LIMIT), b"x" * LIMIT),
        (b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}", b"{}"),
    ):
        transport, _, _ = make_transport(raw)
        result = run(
            transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105)
        )
        assert result.body == expected


def test_document_responses_allow_up_to_one_mib_while_provider_limit_stays_small():
    body = b"x" * (LIMIT + 1)
    transport, _, _ = make_transport(
        raw_response(body, {"Content-Type": "text/html; charset=utf-8"})
    )

    result = run(transport.get(Request("https://public.example/book", "document"), 105))

    assert result.body == body

    provider, _, _ = make_transport(raw_response(body))
    with pytest.raises(VerificationError) as exc:
        run(provider.get(Request("https://api.crossref.org/works/x", "crossref"), 105))
    assert exc.value.code == Code.LIMIT


@pytest.mark.parametrize(
    "body,headers",
    [
        (b"x" * (DOCUMENT_LIMIT + 1), {"Content-Type": "text/html"}),
        (
            gzip.compress(b"x" * (DOCUMENT_LIMIT + 1)),
            {"Content-Type": "text/html", "Content-Encoding": "gzip"},
        ),
        (
            gzip.compress(os.urandom(DOCUMENT_LIMIT + 1)),
            {"Content-Type": "text/html", "Content-Encoding": "gzip"},
        ),
        (
            gzip.compress(bytes(range(256)) * 4097),
            {"Content-Type": "text/html", "Content-Encoding": "gzip"},
        ),
    ],
)
def test_document_compressed_and_decompressed_bodies_stay_bounded(body, headers):
    transport, writer, _ = make_transport(raw_response(body, headers))

    with pytest.raises(VerificationError) as exc:
        run(transport.get(Request("https://public.example/book", "document"), 105))

    assert exc.value.code == Code.LIMIT
    assert writer.closed


def test_repeated_unconsumed_vary_is_ignored():
    transport, _, _ = make_transport(
        raw_response(b"{}", {"Vary": "Accept-Encoding\r\nVary: Accept"})
    )
    result = run(
        transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105)
    )
    assert result.body == b"{}"
    assert "vary" not in result.headers


def test_repeated_unconsumed_headers_are_ignored_and_not_returned():
    raw = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Content-Length: 2\r\nSet-Cookie: first=one; Path=/\r\n"
        b"Set-Cookie: second=two; Path=/\r\nServer-Timing: edge;dur=2\r\n"
        b"Server-Timing: origin;dur=5\r\nX-Trace: one\r\nX-Trace: two\r\n\r\n{}"
    )
    transport, _, _ = make_transport(raw)

    result = run(
        transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105)
    )

    assert result.body == b"{}"
    assert "set-cookie" not in result.headers
    assert "server-timing" not in result.headers
    assert result.headers == {"content-type": "application/json"}


@pytest.mark.parametrize(
    "header,value",
    [
        ("Content-Length", "2"),
        ("Transfer-Encoding", "chunked"),
        ("Content-Encoding", "identity"),
        ("Content-Type", "application/json"),
        ("Location", "https://example.org/"),
    ],
)
def test_duplicate_semantic_headers_are_rejected_case_insensitively(header, value):
    raw = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        + f"{header}: {value}\r\n{header.upper()}: {value}\r\n\r\n{{}}".encode()
    )
    transport, writer, _ = make_transport(raw)

    with pytest.raises(VerificationError) as exc:
        run(transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105))

    assert exc.value.code == Code.MALFORMED
    assert writer.closed

    duplicate_length = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Content-Length: 2\r\nContent-Length: 2\r\n\r\n{}"
    )
    transport, writer, _ = make_transport(duplicate_length)
    with pytest.raises(VerificationError) as exc:
        run(transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105))
    assert exc.value.code == Code.MALFORMED
    assert writer.closed


def test_dns_timeout_in_attempt_deadline_no_extra_http_unit():
    async def stalled_resolver(host):
        await asyncio.sleep(1)

    transport, writer, events = make_transport()
    transport.resolver = stalled_resolver
    with pytest.raises(VerificationError) as exc:
        run(
            transport.get(
                Request("https://api.crossref.org/works/x", "crossref"), 100.001
            )
        )
    assert exc.value.code == Code.DEADLINE
    assert not events and not writer.sent


def test_absolute_deadline_applies_before_dns_and_after_dns_to_connect():
    now = [100.0]
    transport, writer, events = make_transport(clock=lambda: now[0])
    with pytest.raises(VerificationError, match="tool_deadline_exceeded"):
        run(transport.get(Request("https://api.crossref.org/works/x", "crossref"), 100))
    assert not events

    async def dns(host):
        now[0] = 106
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 443),
            )
        ]

    transport.resolver = dns
    now[0] = 100
    with pytest.raises(VerificationError, match="tool_deadline_exceeded"):
        run(transport.get(Request("https://api.crossref.org/works/x", "crossref"), 105))
    assert not events and not writer.sent
