"""Convenience launcher for the API and dashboard."""

import os
import sys
import subprocess

from api.config import settings


def main():
    print("Starting API and dashboard...")
    api_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        settings.host,
        "--port",
        str(settings.port),
    ]
    dashboard_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "dashboard/app.py",
        "--server.port",
        str(settings.dashboard_port),
        "--server.address",
        settings.host,
    ]

    api_process = subprocess.Popen(api_cmd)
    dashboard_process = subprocess.Popen(dashboard_cmd)

    try:
        api_process.wait()
    except KeyboardInterrupt:
        api_process.terminate()
        dashboard_process.terminate()

    dashboard_process.terminate()


if __name__ == "__main__":
    main()
