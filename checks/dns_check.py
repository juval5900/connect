import socket
import time


def run_dns_check(host: str):
    """Resolves FQDN to IP and tests reverse PTR resolution."""
    start = time.perf_counter()
    try:
        resolved_ip = socket.gethostbyname(host)
        dns_latency = round((time.perf_counter() - start) * 1000, 2)

        try:
            reverse_host = socket.gethostbyaddr(resolved_ip)[0]
            details = f"Resolved: {resolved_ip} | PTR: {reverse_host}"
        except socket.herror:
            details = f"Resolved: {resolved_ip} | Reverse PTR not configured"

        return "RESOLVED", dns_latency, details
    except socket.gaierror:
        return "FAILED", None, "DNS resolution failed (Hostname not found)"
    except Exception as e:
        return "ERROR", None, str(e)