import socket
import time


def run_tcp_check(host: str, port: int, timeout_seconds: float = 2.5):
    """Attempts a 3-way TCP socket handshake to verify service listener and firewall rules."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_seconds)
    start = time.perf_counter()
    try:
        sock.connect((host, int(port)))
        latency = round((time.perf_counter() - start) * 1000, 2)
        sock.close()
        return "OPEN", latency, f"TCP Handshake success on port {port}"
    except socket.timeout:
        return "TIMEOUT", None, f"Port {port} timed out (Firewall drop)"
    except ConnectionRefusedError:
        return (
            "REFUSED",
            None,
            f"Port {port} connection refused (Service down)",
        )
    except Exception as e:
        return "ERROR", None, str(e)
    finally:
        sock.close()