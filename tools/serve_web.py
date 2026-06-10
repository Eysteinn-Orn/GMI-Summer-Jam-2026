#!/usr/bin/env python3
"""Serve the Web build locally with the COOP/COEP headers that the
threaded (SharedArrayBuffer) wasm build requires.

Usage:
    python tools/serve_web.py [port]    # default 8765, serves build/web/
"""

import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "build" / "web"

class CrossOriginIsolatedHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    handler = partial(CrossOriginIsolatedHandler, directory=str(ROOT))
    print(f"serving {ROOT} at http://localhost:{port}/")
    HTTPServer(("", port), handler).serve_forever()

if __name__ == "__main__":
    main()
