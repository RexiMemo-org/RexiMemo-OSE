#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time

PORT = int(os.environ.get("REXIMEMO_PORT", "8080"))
DOCS_ARGUMENT = "docs:enabled"


def docs_enabled_from_args():
    return DOCS_ARGUMENT in sys.argv[1:]


def _force_project_working_directory():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))


def _import_twisted():
    try:
        from twisted.internet import reactor
        from twisted.web import server
    except ImportError as exc:
        raise SystemExit("Twisted is required. Install dependencies with: python3 -m pip install -r requirements.txt") from exc
    return reactor, server


class Log:
    def __init__(self):
        os.makedirs("logs", exist_ok=True)
        self.handle = open("logs/reximemo.log", "a", encoding="utf-8")

    def write(self, text, silent=False):
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), str(text).rstrip())
        if not silent:
            print(line)
        self.handle.write(line + "\n")
        self.handle.flush()

    def close(self):
        self.handle.close()


def create_site(*, docs_enabled=False):
    _force_project_working_directory()
    reactor, twisted_server = _import_twisted()
    import DB  # initializes SQLite
    import hatena
    log = Log()
    hatena.ServerLog = log

    class ProxyCompatibleSite(twisted_server.Site):
        def buildProtocol(self, addr):
            protocol = super().buildProtocol(addr)
            original = protocol.dataReceived

            def data_received(data):
                for host in (b"flipnote.hatena.com", b"ugomemo.hatena.ne.jp"):
                    data = data.replace(b"GET http://" + host, b"GET ")
                    data = data.replace(b"POST http://" + host, b"POST ")
                return original(data)

            protocol.dataReceived = data_received
            return protocol

    return reactor, ProxyCompatibleSite(hatena.Setup(docs_enabled=docs_enabled)), log


def main():
    docs_enabled = docs_enabled_from_args()
    reactor, site, log = create_site(docs_enabled=docs_enabled)
    log.write("RexiMemo OSE starting on port %d" % PORT)
    log.write("DSi mode uses the historical HTTP proxy path; NAS/DNS/auth services are not included.")
    if docs_enabled:
        log.write("Built-in documentation enabled at /docs")
    reactor.listenTCP(PORT, site)
    try:
        reactor.run()
    finally:
        log.write("Server shutdown", True)
        log.close()


if __name__ == "__main__":
    main()
