"""Measure loopback API latency against an isolated, freshly migrated database."""

import argparse
import json
import os
import platform
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import median

import httpx

API_ROOT = Path(__file__).resolve().parents[1]


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int((len(ordered) - 1) * fraction))]


def measure(client: httpx.Client, method: str, path: str, count: int, **kwargs) -> dict:
    timings = []
    for _ in range(count):
        started = time.perf_counter()
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        timings.append((time.perf_counter() - started) * 1000)
    return {
        "samples": count,
        "median_ms": round(median(timings), 2),
        "p95_ms": round(percentile(timings, 0.95), 2),
        "max_ms": round(max(timings), 2),
    }


def measure_concurrent(client: httpx.Client, path: str, count: int, workers: int) -> dict:
    def call(_index: int) -> float:
        started = time.perf_counter()
        client.get(path).raise_for_status()
        return (time.perf_counter() - started) * 1000

    wall_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        timings = list(pool.map(call, range(count)))
    elapsed = time.perf_counter() - wall_started
    return {
        "samples": count,
        "clients": workers,
        "median_ms": round(median(timings), 2),
        "p95_ms": round(percentile(timings, 0.95), 2),
        "max_ms": round(max(timings), 2),
        "requests_per_second": round(count / elapsed, 1),
    }


def measure_sustained(client: httpx.Client, seconds: int, workers: int = 4) -> dict:
    deadline = time.perf_counter() + seconds

    def run_client() -> tuple[list[float], int]:
        timings = []
        errors = 0
        while time.perf_counter() < deadline:
            started = time.perf_counter()
            try:
                client.get("/ready").raise_for_status()
            except httpx.HTTPError:
                errors += 1
            else:
                timings.append((time.perf_counter() - started) * 1000)
        return timings, errors

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _index: run_client(), range(workers)))
    elapsed = time.perf_counter() - started
    timings = [value for client_timings, _ in results for value in client_timings]
    errors = sum(failures for _, failures in results)
    if not timings:
        raise RuntimeError("Sustained sample had no successful requests")
    return {
        "seconds": round(elapsed, 2),
        "clients": workers,
        "successful_requests": len(timings),
        "errors": errors,
        "median_ms": round(median(timings), 2),
        "p95_ms": round(percentile(timings, 0.95), 2),
        "max_ms": round(max(timings), 2),
        "requests_per_second": round(len(timings) / elapsed, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sustain-seconds", type=int, default=0, help="optional 5–120 second four-client /ready sample")
    options = parser.parse_args()
    if options.sustain_seconds and not 5 <= options.sustain_seconds <= 120:
        parser.error("--sustain-seconds must be between 5 and 120")
    with tempfile.TemporaryDirectory(prefix="nexus-perf-") as temp_dir:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        env = {
            **os.environ,
            "DATABASE_URL": f"sqlite:///{(Path(temp_dir) / 'nexus.db').as_posix()}",
            "DATA_DIR": temp_dir,
            "OLLAMA_MODEL": "",
            "APPROVED_WORKSPACES": "",
        }
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=API_ROOT, env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
            cwd=API_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=5, trust_env=False) as client:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("API exited before readiness")
                    try:
                        if client.get("/ready").status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("API did not become ready")
                results = {
                    "platform": platform.platform(),
                    "python": platform.python_version(),
                    "health": measure(client, "GET", "/health", 100),
                    "ready": measure(client, "GET", "/ready", 100),
                    "ready_four_clients": measure_concurrent(client, "/ready", 100, 4),
                    "create_task": measure(client, "POST", "/api/v1/tasks", 10, headers={"X-Nexus-Intent": "local"}, json={"goal": "Measure the local synthetic task path"}),
                }
                if options.sustain_seconds:
                    results["ready_sustained"] = measure_sustained(client, options.sustain_seconds)
                print(json.dumps(results, indent=2))
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            time.sleep(0.5)


if __name__ == "__main__":
    main()
