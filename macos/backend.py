"""Private desktop entry point. Resources stay in the bundle; user data does not."""
import argparse
import json
import os
from pathlib import Path
import signal
import ssl  # Fail at startup if the packaged TLS libraries are missing.
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import App, serve


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--ready-file', type=Path, required=True)
    parser.add_argument('--parent-pid', type=int, required=True)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    server = serve(App(args.db), 0)
    ready = args.ready_file
    temporary = ready.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(dict(port=server.server_port, pid=os.getpid())))
        temporary.replace(ready)
        def watch_parent():
            while True:
                time.sleep(1)
                if os.getppid() != args.parent_pid:
                    os.kill(os.getpid(), signal.SIGTERM)
                    return
        threading.Thread(target=watch_parent, daemon=True).start()
        server.serve_forever()
    finally:
        server.server_close()
        ready.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
