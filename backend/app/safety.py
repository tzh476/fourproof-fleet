from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import parse_qsl, urlsplit


INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("instruction_override", re.compile(r"ignore\s+(all\s+)?(previous|prior|system)(\s+system)?\s+instructions?", re.I)),
    ("secret_exfiltration", re.compile(r"(reveal|send|upload|exfiltrat\w*)\s+.{0,45}(secret|token|credential|api[ _-]?key)", re.I)),
    ("tool_coercion", re.compile(r"(must|always)\s+(call|invoke|execute|run)\s+.{0,40}(tool|command|shell)", re.I)),
    ("role_impersonation", re.compile(r"(system|developer)\s*(message|instruction)\s*:", re.I)),
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def flatten_strings(value: Any) -> list[str]:
    output: list[str] = []
    if isinstance(value, str):
        output.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            output.append(str(key))
            output.extend(flatten_strings(item))
    elif isinstance(value, list):
        for item in value:
            output.extend(flatten_strings(item))
    return output


def scan_prompt_injection(value: Any) -> list[str]:
    text = "\n".join(flatten_strings(value))[:80_000]
    return [label for label, pattern in INJECTION_PATTERNS if pattern.search(text)]


def _is_forbidden_ip(raw: str) -> bool:
    address = ipaddress.ip_address(raw)
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def validate_public_http_url(url: str, *, resolve_dns: bool = False) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http and https URLs are accepted")
    if parsed.username or parsed.password:
        raise ValueError("URL credentials are not accepted")
    if parsed.fragment:
        raise ValueError("URL fragments are not accepted because they are not sent to the evidence source")
    sensitive_query_names = re.compile(r"^(api[_-]?key|access[_-]?token|auth|authorization|credential|secret|signature|sig)$", re.I)
    if any(sensitive_query_names.match(name) for name, _ in parse_qsl(parsed.query, keep_blank_values=True)):
        raise ValueError("credential-like query parameters are not accepted")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL hostname is required")
    if hostname.lower() in {"localhost", "localhost.localdomain"} or hostname.lower().endswith(".local"):
        raise ValueError("local hostnames are blocked")
    try:
        if _is_forbidden_ip(hostname):
            raise ValueError("private or non-routable addresses are blocked")
    except ValueError as error:
        if "does not appear to be" not in str(error):
            raise
    if resolve_dns:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
        if not addresses or any(_is_forbidden_ip(address) for address in addresses):
            raise ValueError("hostname resolves to a private or non-routable address")
    return url
