"""Self-terminate when our parent process dies.

When the Tauri shell is force-quit (or any other "ungraceful" exit), the
sidecar is reparented to launchd (PID 1) and would otherwise keep holding
port 8765 indefinitely. This watcher polls our PPID and shuts the process
down the moment we notice we've been orphaned, so the next `just dev` finds
a free port.

Linux has prctl(PR_SET_PDEATHSIG) for this, macOS has kqueue NOTE_EXIT.
PPID polling is the portable choice and adequate at ~2s granularity.
"""

import os
import signal
import sys
import threading
import time


_POLL_INTERVAL_S = 2.0
_HARD_EXIT_AFTER_S = 5.0


def _watch(initial_ppid: int) -> None:
    while True:
        time.sleep(_POLL_INTERVAL_S)
        current = os.getppid()
        if current == initial_ppid:
            continue
        print(
            f"sidecar: parent {initial_ppid} died (reparented to {current}), shutting down",
            file=sys.stderr,
            flush=True,
        )
        # SIGTERM triggers uvicorn's graceful shutdown which runs the FastAPI
        # lifespan and cleans up the camera worker.
        os.kill(os.getpid(), signal.SIGTERM)
        # If graceful shutdown stalls, force-exit so we always release the port.
        time.sleep(_HARD_EXIT_AFTER_S)
        os._exit(1)


def watch_parent_and_exit() -> None:
    """Spawn a daemon thread that kills this process when its parent dies."""
    initial_ppid = os.getppid()
    # If we were launched directly by init/launchd we have no meaningful parent
    # to watch (and PPID will never change away from 1).
    if initial_ppid <= 1:
        return
    threading.Thread(target=_watch, args=(initial_ppid,), daemon=True).start()
