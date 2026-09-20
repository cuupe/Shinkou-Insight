from __future__ import annotations

import ipaddress
from urllib.parse import urlparse


class SecurityPolicyError(ValueError):
    pass


def enforce_scope(
    expected_workspace_id: int,
    expected_project_id: int,
    workspace_id: int,
    project_id: int,
) -> tuple[int, int]:
    """Reject cross-tenant identifiers before a tool or model call is made."""

    if expected_workspace_id <= 0 or expected_project_id <= 0:
        raise SecurityPolicyError("expected scope must be positive")
    if workspace_id != expected_workspace_id or project_id != expected_project_id:
        raise SecurityPolicyError("workspace or project scope mismatch")
    return workspace_id, project_id


def validate_external_url(value: str) -> str:
    """Allow only public HTTP(S) URLs without resolving DNS.

    Network clients must still enforce an egress allow-list and re-check the
    resolved address. This validator is the application-level first gate.
    """

    parsed = urlparse(str(value).strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise SecurityPolicyError("only credential-free HTTP(S) URLs are allowed")
    host = parsed.hostname.rstrip(".").casefold()
    blocked_names = {"localhost", "metadata.google.internal", "host.docker.internal"}
    if host in blocked_names or host.endswith((".localhost", ".local", ".internal")):
        raise SecurityPolicyError("private or metadata host is not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    ):
        raise SecurityPolicyError("private or reserved address is not allowed")
    return parsed.geturl()
