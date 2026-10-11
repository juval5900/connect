import platform
import subprocess
import time


def run_icmp_check(host: str, timeout_seconds: int = 2):
    """Executes an OS ping command and captures round-trip latency."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
    command = [
        "ping",
        param,
        "1",
        timeout_param,
        str(timeout_seconds * 1000),
        host,
    ]

    start = time.perf_counter()
    try:
        proc = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        latency = round((time.perf_counter() - start) * 1000, 2)
        if proc.returncode == 0:
            return "UP", latency, "ICMP Echo Reply received"
        return "DOWN", None, "Host unreachable / ping timed out"
    except Exception as e:
        return "ERROR", None, str(e)