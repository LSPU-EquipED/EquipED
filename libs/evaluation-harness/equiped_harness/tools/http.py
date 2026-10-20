"""One GET-only, pinned TLS transport. No proxy, cookies, redirects or retries.

Every call must be charged by the caller before entering get(), including DNS.
Async resolver and socket factory are genuine I/O boundaries for synthetic tests.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import ssl
import time
import zlib
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import parse_qsl, unquote, urlsplit

from pydantic import SecretStr

from .contracts import Code, VerificationError

LIMIT = 128 * 1024
DOCUMENT_LIMIT = 1024 * 1024
HEADER_LIMIT = 16 * 1024
PROVIDERS = frozenset(
    {
        "api.search.brave.com",
        "api.crossref.org",
        "api.datacite.org",
        "html.duckduckgo.com",
    }
)
USER_AGENT = "EquipED-PublicVerification/1.0"


def validate_url(url: str, *, provider: bool = False) -> str:
    try:
        p = urlsplit(url)
        host = p.hostname or ""
        if (
            len(url) > 2048
            or not url.isascii()
            or any(ord(c) <= 32 for c in url)
            or p.scheme != "https"
            or p.port not in {None, 443}
            or p.username is not None
            or p.password is not None
            or p.fragment
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", host)
            or "." not in host
            or ".." in host
            or host.endswith(".")
            or "\\" in unquote(url)
            or any(ord(c) < 32 for c in unquote(url))
        ):
            raise ValueError
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError
        if provider:
            if host not in PROVIDERS:
                raise ValueError
        else:
            # No signed/session/search/private query URLs. Small explicit public
            # metadata query allowlist, never arbitrary model/user query strings.
            pairs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
            google_books_redirect = (
                host in {"books.google.com", "books.google.com.ph"}
                and p.path == "/books"
            )
            if len(pairs) > 4 or any(
                (
                    k not in {"id", "doi", "lang"}
                    and not (google_books_redirect and k == "redir_esc" and v == "y")
                )
                or not re.fullmatch(r"[A-Za-z0-9._:/()+-]{1,180}", v)
                for k, v in pairs
            ):
                raise ValueError
            if re.search(r"(?i)\.(pdf|zip|exe|docx?)(?:$|[/?])", unquote(p.path)):
                raise ValueError
        return host
    except (ValueError, UnicodeError):
        raise VerificationError(Code.SECURITY) from None


def public_address(value: str) -> str:
    try:
        ip = ipaddress.ip_address(value)
        effective = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) else ip
        effective = effective or ip
        if not effective.is_global or effective.is_multicast or effective.is_reserved:
            raise ValueError
        return str(ip)
    except ValueError:
        raise VerificationError(Code.SECURITY) from None


@dataclass(frozen=True)
class Request:
    url: str = field(repr=False)
    kind: str
    token: SecretStr | None = field(default=None, repr=False)


@dataclass(frozen=True)
class Response:
    status: int
    headers: dict[str, str]
    body: bytes = field(repr=False)


class Transport(Protocol):
    async def get(self, request: Request, deadline: float) -> Response: ...


async def resolve(host: str):
    return await asyncio.get_running_loop().getaddrinfo(
        host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )


class PinnedHTTPS:
    def __init__(
        self,
        *,
        resolver=resolve,
        connector=asyncio.open_connection,
        clock=time.monotonic,
    ):
        self.resolver = resolver
        self.connector = connector
        self.clock = clock
        self.ssl = ssl.create_default_context()
        self.ssl.minimum_version = ssl.TLSVersion.TLSv1_2

    async def get(self, request: Request, deadline: float) -> Response:
        writer = None

        async def bounded(awaitable):
            remaining = deadline - self.clock()
            if remaining <= 0:
                if hasattr(awaitable, "close"):
                    awaitable.close()
                raise VerificationError(Code.DEADLINE)
            return await asyncio.wait_for(awaitable, remaining)

        try:
            if request.kind not in {
                "crossref",
                "datacite",
                "brave",
                "duckduckgo",
                "robots",
                "document",
            }:
                raise VerificationError(Code.INVALID)
            provider = request.kind in {"crossref", "datacite", "brave", "duckduckgo"}
            host = validate_url(request.url, provider=provider)
            expected = {
                "crossref": "api.crossref.org",
                "datacite": "api.datacite.org",
                "brave": "api.search.brave.com",
                "duckduckgo": "html.duckduckgo.com",
            }.get(request.kind)
            if expected and host != expected:
                raise VerificationError(Code.SECURITY)
            if request.token is not None and (
                host != "api.search.brave.com" or request.kind != "brave"
            ):
                raise VerificationError(Code.SECURITY)
            answers = await bounded(self.resolver(host))
            if not answers:
                raise VerificationError(Code.SECURITY)
            addresses = tuple(public_address(a[4][0]) for a in answers)
            # Validate ALL answers before selecting any numeric address. Never
            # pass the original host to connect (DNS rebinding/second resolution).
            reader, writer = await bounded(
                self.connector(
                    addresses[0],
                    443,
                    ssl=self.ssl,
                    server_hostname=host,
                    ssl_handshake_timeout=max(0.001, deadline - self.clock()),
                    limit=HEADER_LIMIT + 1,
                )
            )
            peer = writer.get_extra_info("peername")
            if not peer or public_address(peer[0]) != addresses[0]:
                raise VerificationError(Code.SECURITY)
            parts = urlsplit(request.url)
            target = parts.path or "/"
            if parts.query:
                target += "?" + parts.query
            accept = {
                "robots": "text/plain",
                "document": "text/html",
                "duckduckgo": "text/html",
            }.get(request.kind, "application/json")
            headers = [
                f"GET {target} HTTP/1.1",
                f"Host: {host}",
                f"User-Agent: {USER_AGENT}",
                f"Accept: {accept}",
                "Accept-Encoding: gzip",
                "Connection: close",
            ]
            if request.token is not None:
                token = request.token.get_secret_value()
                if (
                    not token
                    or len(token) > 1024
                    or any(ord(c) < 33 or ord(c) > 126 for c in token)
                ):
                    raise VerificationError(Code.KEY)
                headers.append(f"X-Subscription-Token: {token}")
            writer.write(("\r\n".join(headers) + "\r\n\r\n").encode("ascii"))
            await bounded(writer.drain())
            try:
                raw = await bounded(reader.readuntil(b"\r\n\r\n"))
            except asyncio.LimitOverrunError:
                raise VerificationError(Code.LIMIT) from None
            if len(raw) > HEADER_LIMIT:
                raise VerificationError(Code.LIMIT)
            lines = raw.decode("ascii").split("\r\n")
            match = re.fullmatch(
                r"HTTP/1\.[01] ([1-5][0-9]{2})(?: [^\r\n]*)?", lines[0]
            )
            if not match:
                raise VerificationError(Code.MALFORMED)
            status = int(match[1])
            response_headers: dict[str, str] = {}
            critical_headers = {
                "content-length",
                "transfer-encoding",
                "content-encoding",
                "content-type",
                "location",
            }
            for line in lines[1:]:
                if not line:
                    continue
                key, sep, value = line.partition(":")
                key = key.lower()
                if not sep or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9a-z-]+", key):
                    raise VerificationError(Code.MALFORMED)
                value = value.strip(" \t")
                if any(ord(char) < 32 and char != "\t" for char in value):
                    raise VerificationError(Code.MALFORMED)
                # Only fields used by this GET client are retained. In
                # particular, Set-Cookie is never stored or replayed.
                if key in critical_headers:
                    if key in response_headers:
                        raise VerificationError(Code.MALFORMED)
                    response_headers[key] = value
            transfer = response_headers.get("transfer-encoding")
            length = response_headers.get("content-length")
            body_limit = DOCUMENT_LIMIT if request.kind == "document" else LIMIT
            if transfer and (transfer != "chunked" or length is not None):
                raise VerificationError(Code.MALFORMED)
            if length is not None and (
                not length.isdigit() or int(length) > body_limit
            ):
                raise VerificationError(Code.LIMIT)
            encoding = response_headers.get("content-encoding", "identity")
            if encoding not in {"identity", "gzip"}:
                raise VerificationError(Code.MALFORMED)
            decoder = (
                zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
            )
            compressed = 0
            body = bytearray()

            def add(data):
                nonlocal compressed
                compressed += len(data)
                if compressed > body_limit:
                    raise VerificationError(Code.LIMIT)
                if decoder:
                    data = decoder.decompress(data, body_limit + 1 - len(body))
                    if decoder.unconsumed_tail:
                        raise VerificationError(Code.LIMIT)
                body.extend(data)
                if len(body) > body_limit:
                    raise VerificationError(Code.LIMIT)

            if transfer:
                while True:
                    line = await bounded(reader.readuntil(b"\r\n"))
                    if len(line) > 16 or not re.fullmatch(b"[0-9a-fA-F]+\r\n", line):
                        raise VerificationError(Code.MALFORMED)
                    size = int(line, 16)
                    if size > body_limit - compressed:
                        raise VerificationError(Code.LIMIT)
                    if size == 0:
                        if await bounded(reader.readexactly(2)) != b"\r\n":
                            raise VerificationError(Code.MALFORMED)
                        break
                    add(await bounded(reader.readexactly(size)))
                    if await bounded(reader.readexactly(2)) != b"\r\n":
                        raise VerificationError(Code.MALFORMED)
            elif length is not None:
                remaining = int(length)
                while remaining:
                    chunk = await bounded(reader.readexactly(min(8192, remaining)))
                    remaining -= len(chunk)
                    add(chunk)
            else:
                while chunk := await bounded(reader.read(8192)):
                    add(chunk)
            if decoder and (not decoder.eof or decoder.unused_data):
                raise VerificationError(Code.MALFORMED)
            if self.clock() >= deadline:
                raise VerificationError(Code.DEADLINE)
            # Error/redirect bodies are never interpreted or retained by adapters.
            if status == 200:
                mime = response_headers.get("content-type", "").split(";")[0].lower()
                allowed = {
                    "robots": {"text/plain"},
                    "document": {"text/html"},
                    "duckduckgo": {"text/html"},
                }.get(request.kind, {"application/json", "application/vnd.api+json"})
                if mime not in allowed:
                    raise VerificationError(Code.MALFORMED)
                bytes(body).decode("utf-8", errors="strict")
            return Response(
                status,
                {
                    k: v
                    for k, v in response_headers.items()
                    if k in {"content-type", "location"}
                },
                bytes(body) if status == 200 else b"",
            )
        except VerificationError:
            raise
        except TimeoutError:
            raise VerificationError(Code.DEADLINE) from None
        except (
            OSError,
            ValueError,
            UnicodeError,
            asyncio.IncompleteReadError,
            asyncio.LimitOverrunError,
            zlib.error,
        ):
            raise VerificationError(Code.MALFORMED) from None
        finally:
            if writer is not None:
                writer.close()
