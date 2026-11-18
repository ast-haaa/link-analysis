"""URL and SSRF validation utilities.

Protects against Server-Side Request Forgery (SSRF) by validating URL schemes,
filtering dangerous hostnames, resolving DNS records, and checking IP ranges.
"""

import asyncio
import ipaddress
import re
import socket
from typing import List, Tuple
from urllib.parse import urlsplit


class URLValidationError(ValueError):
    """Raised when a URL has invalid format or forbidden scheme."""
    pass


class SSRFSecurityError(ValueError):
    """Raised when a URL targets internal, private, loopback, or reserved destinations."""
    pass


# Disallowed top-level domains or hostname suffixes
BLOCKED_HOSTNAME_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".lan",
    ".corp",
    ".home.arpa",
    ".test",
    ".invalid",
    ".onion",
)

# Known dangerous/metadata hostnames
BLOCKED_HOSTNAMES = {
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}

# Explicit extra restricted IPv4 networks
RESTRICTED_IPV4_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),         # Current network
    ipaddress.ip_network("10.0.0.0/8"),        # Private network RFC 1918
    ipaddress.ip_network("100.64.0.0/10"),     # Shared address space / CGNAT RFC 6598
    ipaddress.ip_network("127.0.0.0/8"),       # Loopback RFC 1122
    ipaddress.ip_network("169.254.0.0/16"),    # Link-local / AWS/GCP metadata RFC 3927
    ipaddress.ip_network("172.16.0.0/12"),     # Private network RFC 1918
    ipaddress.ip_network("192.0.0.0/24"),      # IETF Protocol Assignments RFC 6890
    ipaddress.ip_network("192.0.2.0/24"),      # Documentation TEST-NET-1 RFC 5737
    ipaddress.ip_network("192.168.0.0/16"),    # Private network RFC 1918
    ipaddress.ip_network("198.18.0.0/15"),     # Benchmarking RFC 2544
    ipaddress.ip_network("198.51.100.0/24"),   # Documentation TEST-NET-2 RFC 5737
    ipaddress.ip_network("203.0.113.0/24"),    # Documentation TEST-NET-3 RFC 5737
    ipaddress.ip_network("224.0.0.0/4"),       # Multicast RFC 5771
    ipaddress.ip_network("240.0.0.0/4"),       # Reserved for future use RFC 1112
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
]

# Explicit extra restricted IPv6 networks
RESTRICTED_IPV6_NETWORKS = [
    ipaddress.ip_network("::1/128"),           # Loopback RFC 4291
    ipaddress.ip_network("::/128"),            # Unspecified RFC 4291
    ipaddress.ip_network("::ffff:0:0/96"),     # IPv4-mapped addresses RFC 4291
    ipaddress.ip_network("64:ff9b::/96"),      # IPv4/IPv6 translation RFC 6052
    ipaddress.ip_network("100::/64"),          # Discard prefix RFC 6666
    ipaddress.ip_network("2001:db8::/32"),     # Documentation RFC 3849
    ipaddress.ip_network("2002::/16"),         # 6to4 RFC 3056
    ipaddress.ip_network("fc00::/7"),          # Unique local address (ULA) RFC 4193
    ipaddress.ip_network("fe80::/10"),         # Link-local unicast RFC 4291
    ipaddress.ip_network("ff00::/8"),          # Multicast RFC 4291
]


def is_ip_allowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Check if an IP address is a safe, publicly routable address.

    Rejects private, loopback, link-local, reserved, multicast, and unspecified addresses.
    """
    # Handle IPv4-mapped IPv6 (e.g. ::ffff:127.0.0.1)
    if ip.version == 6 and ip.ipv4_mapped:
        return is_ip_allowed(ip.ipv4_mapped)

    # Standard built-in checks
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return False

    # Check against explicit restricted networks
    if ip.version == 4:
        for net in RESTRICTED_IPV4_NETWORKS:
            if ip in net:
                return False
    else:
        for net in RESTRICTED_IPV6_NETWORKS:
            if ip in net:
                return False

    return True


def validate_hostname_syntax(hostname: str) -> None:
    """Validate hostname syntax and block internal/local domain names."""
    lower_host = hostname.lower().strip(".")

    if not lower_host:
        raise URLValidationError("Hostname cannot be empty.")

    if lower_host in BLOCKED_HOSTNAMES:
        raise SSRFSecurityError(
            f"Blocked target '{lower_host}': Access to local or internal hostnames is prohibited (SSRF protection)."
        )

    for suffix in BLOCKED_HOSTNAME_SUFFIXES:
        if lower_host.endswith(suffix) or lower_host == suffix.strip("."):
            raise SSRFSecurityError(
                f"Blocked target '{lower_host}': Access to '{suffix}' domains is prohibited (SSRF protection)."
            )

    # If it's a single label with no dot and not an IP, it is an internal machine name (e.g., 'router', 'nas')
    if "." not in lower_host and ":" not in lower_host:
        raise SSRFSecurityError(
            f"Blocked target '{lower_host}': Single-label internal hostnames are prohibited (SSRF protection)."
        )


def validate_url(url_str: str) -> Tuple[str, str, int]:
    """Validate URL syntax, scheme, and basic host requirements.

    Returns:
        Tuple of (clean_url, hostname, port)
    """
    if not isinstance(url_str, str):
        raise URLValidationError("URL must be a string.")

    cleaned = url_str.strip()
    if not cleaned:
        raise URLValidationError("URL cannot be empty.")

    try:
        parsed = urlsplit(cleaned)
    except Exception as e:
        raise URLValidationError(f"Invalid URL structure: {e}") from e

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise URLValidationError(
            f"Invalid scheme '{scheme}'. Only HTTP and HTTPS URLs are allowed."
        )

    if not parsed.netloc:
        raise URLValidationError("URL must contain a valid domain or network location.")

    if parsed.username or parsed.password:
        raise URLValidationError("URLs containing embedded credentials are not allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise URLValidationError("URL must include a valid hostname.")

    # Determine default port
    port = parsed.port or (443 if scheme == "https" else 80)
    if not (1 <= port <= 65535):
        raise URLValidationError(f"Invalid port number: {port}")

    # Check if literal IP
    try:
        # Strip brackets from IPv6 literal if present
        raw_ip_str = hostname.strip("[]")
        ip_obj = ipaddress.ip_address(raw_ip_str)
        if not is_ip_allowed(ip_obj):
            raise SSRFSecurityError(
                f"Blocked target IP '{hostname}': Private, loopback, and internal IP addresses are prohibited (SSRF protection)."
            )
    except ValueError:
        # Not a raw IP literal, proceed to hostname syntax checks
        validate_hostname_syntax(hostname)

    return cleaned, hostname, port


async def resolve_and_validate_host(hostname: str, port: int = 80) -> List[str]:
    """Asynchronously resolve a hostname via DNS and ensure all resolved IPs are safe.

    Returns:
        List of verified safe IP address strings.

    Raises:
        SSRFSecurityError: If any resolved address belongs to a restricted IP range.
        URLValidationError: If DNS resolution fails.
    """
    raw_host = hostname.strip("[]")

    # If it is already a direct IP address
    try:
        ip_obj = ipaddress.ip_address(raw_host)
        if not is_ip_allowed(ip_obj):
            raise SSRFSecurityError(
                f"Blocked IP '{raw_host}': Destination is in a restricted network range (SSRF protection)."
            )
        return [str(ip_obj)]
    except ValueError:
        pass  # It's a domain name, resolve via DNS

    loop = asyncio.get_running_loop()
    try:
        # Resolve both IPv4 and IPv6 addresses
        addr_info = await loop.getaddrinfo(
            raw_host,
            port,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as e:
        raise URLValidationError(f"Could not resolve host '{hostname}': {e}") from e
    except Exception as e:
        raise URLValidationError(f"DNS resolution failed for '{hostname}': {e}") from e

    if not addr_info:
        raise URLValidationError(f"No IP addresses found for host '{hostname}'.")

    safe_ips: List[str] = []
    seen: set = set()

    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]

        if ip_str in seen:
            continue
        seen.add(ip_str)

        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            raise SSRFSecurityError(
                f"DNS returned unparseable IP address '{ip_str}' for host '{hostname}'."
            )

        if not is_ip_allowed(ip_obj):
            raise SSRFSecurityError(
                f"SSRF Protection: Host '{hostname}' resolved to prohibited address '{ip_str}' "
                f"(private/internal/loopback/reserved range)."
            )

        safe_ips.append(ip_str)

    if not safe_ips:
        raise SSRFSecurityError(
            f"Host '{hostname}' has no safe, publicly routable IP addresses."
        )

    return safe_ips
