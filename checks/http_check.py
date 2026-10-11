import time
import urllib.error
import urllib.request


def run_http_check(host: str, port: int = 8000, timeout_seconds: float = 3.0):
    """Probes SAP ICM / Web Dispatcher /sap/public/ping endpoint."""
    target_port = port if port else 8000
    url = f"http://{host}:{target_port}/sap/public/ping"
    start = time.perf_counter()
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "ConnectivityMonitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            latency = round((time.perf_counter() - start) * 1000, 2)
            code = response.getcode()
            return "UP", latency, f"HTTP {code} OK (/sap/public/ping)"
    except urllib.error.HTTPError as e:
        latency = round((time.perf_counter() - start) * 1000, 2)
        return "WARNING", latency, f"HTTP {e.code} ({e.reason})"
    except urllib.error.URLError as e:
        return "DOWN", None, f"ICM Unreachable: {e.reason}"
    except Exception as e:
        return "ERROR", None, str(e)