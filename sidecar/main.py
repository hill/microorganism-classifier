"""Sidecar entry point. Tauri spawns this, or you can run it standalone with `just sidecar`."""

import argparse

import uvicorn

from sidecar.api import create_app
from sidecar.process_lifetime import watch_parent_and_exit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    # If our parent dies (e.g. Tauri force-quit), shut ourselves down so the
    # port is freed for the next launch.
    watch_parent_and_exit()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
