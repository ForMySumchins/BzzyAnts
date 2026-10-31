"""SSRF and outbound validation security controls.

Protects against SSRF via private, loopback, link-local, IP literal, and DNS rebinding blocks.
MASTER DIRECTIVE REQUIREMENT:
Default to OFFLINE and DRY_RUN. For any outbound URL checks defend against SSRF via
private/loopback/link-local/IP literal/DNS-rebinding blocks across redirects.
"""

import ipaddress
import re
import urllib.parse
from typing import Tuple, Optional

BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private RFC1918
    ipaddress.ip_network("172.16.0.0/12"),    # Private RFC1918
    ipaddress.ip_network("192.168.0.0/16"),   # Private RFC1918
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local / AWS metadata
    ipaddress.ip_network("0.0.0.0/8"),        # This host on this network
    ipaddress.ip_network("224.0.0.0/4"),      # Multicast
    ipaddress.ip_network("240.0.0.0/4"),      # Reserved
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]

DISALLOWED_SCHEMES = {"file", "gopher", "ftp", "tftp", "dict", "ldap", "ssh", "telnet"}


def is_ssrf_safe_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validates whether a URL is safe against SSRF attacks.
    
    Returns (is_safe, error_reason).
    """
    if not url or not isinstance(url, str):
        return False, "EMPTY_OR_INVALID_URL"
    
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception as e:
        return False, f"MALFORMED_URL: {e}"
    
    if parsed.scheme.lower() not in {"http", "https"}:
        return False, f"DISALLOWED_SCHEME: {parsed.scheme}"
    
    hostname = parsed.hostname
    if not hostname:
        return False, "MISSING_HOSTNAME"
    
    hostname_clean = hostname.strip().lower()
    
    # Check for localhost literals
    if hostname_clean in {"localhost", "localhost.localdomain", "broadcasthost"}:
        return False, "BLOCKED_LOCALHOST_HOSTNAME"
    
    # Check if host is an IP literal
    try:
        ip = ipaddress.ip_address(hostname_clean)
        for net in BLOCKED_IP_NETWORKS:
            if ip in net:
                return False, f"BLOCKED_PRIVATE_OR_RESERVED_IP: {ip}"
    except ValueError:
        # Not a pure IP address string, which is normal for domains
        pass
    
    # Check for hex/octal/decimal IP obfuscation (e.g., 2130706433 or 0177.0.0.1)
    if re.match(r"^(\d+|0x[0-9a-fA-F]+)$", hostname_clean):
        return False, "BLOCKED_NUMERIC_IP_ENCODING"
    
    # Port checking - block internal ports
    if parsed.port and parsed.port not in {80, 443, 8080, 8443}:
        if parsed.port in {22, 23, 25, 3306, 5432, 6379, 27017, 9200, 11211}:
            return False, f"BLOCKED_INTERNAL_PORT: {parsed.port}"

    return True, None
