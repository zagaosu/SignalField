from __future__ import annotations

import argparse

import uvicorn

from .config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description="信号场 SignalField 本地服务")
    parser.add_argument("--host", default=None, help="监听地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=None, help="端口（默认 8765）")
    args = parser.parse_args()
    settings = Settings.from_env()
    host = args.host or settings.host
    port = args.port or settings.port
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
