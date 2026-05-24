import argparse
import logging
import sys

import uvicorn

from app.settings import get_settings
from app.web_server import GofrSecWebServer

VERSION = "0.1.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="gofr-sec Web Server - Bootstrap security service")
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host address to bind to (default: from env or 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port number to listen on (default: from env or 8062)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Logging level (default: from GOFRSEC_LOG_LEVEL or INFO)",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings(reload=True, require_auth=False)

    if args.host:
        settings.server.host = args.host
    if args.port:
        settings.server.web_port = args.port
    if args.log_level:
        settings.log.level = args.log_level.upper()

    log_level = getattr(logging, settings.log.level.upper(), logging.INFO)
    logging.basicConfig(level=log_level)

    server = GofrSecWebServer(version=VERSION)

    banner = f"""
{'=' * 80}
  gofr-sec Web Server - Starting
{'=' * 80}
  Version:          {VERSION}
  Transport:        HTTP REST API
  Host:             {settings.server.host}
  Port:             {settings.server.web_port}

  Endpoints:
    - Docs:          http://{settings.server.host}:{settings.server.web_port}/docs
    - Health Check:  http://{settings.server.host}:{settings.server.web_port}/ping
    - Status:        http://{settings.server.host}:{settings.server.web_port}/v1/status

  Purpose:
    - Bootstrap web surface for gofr-sec
    - Placeholder routes while auth and token APIs are implemented
{'=' * 80}
    """

    try:
        print(banner)
        uvicorn.run(
            server.app,
            host=settings.server.host,
            port=settings.server.web_port,
            log_level=settings.log.level.lower(),
        )
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Failed to start gofr-sec web server: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
