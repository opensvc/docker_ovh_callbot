# -*- encoding: utf-8 -*-
"""
HTTP front for the call bot.

  POST /call    start the oncall loop in the background, answer 202 at once.
                Only one loop runs at a time: a request received while a loop
                is running is logged and answered 200 "already running".
  GET  /health  liveness and last run status, no authentication.

Authentication of POST /call, at least one of:

  CALLBOT_HMAC_SECRET   X-Hub-Signature: sha1=<hmac-sha1 of the body>
                        (the Zammad webhook signature)
  CALLBOT_TOKEN         Authorization: Bearer <token>

Other variables:

  CALLBOT_LISTEN=0.0.0.0:8080
"""

import hashlib
import hmac
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import callbot

log = callbot.log

MAX_BODY = 64 * 1024


class State(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.last = None

    def snapshot(self):
        with self.lock:
            return {"running": self.running, "last": self.last}


class Handler(BaseHTTPRequestHandler):
    server_version = "callbot"
    state = None
    numbers = None
    hmac_secret = None
    token = None

    def log_message(self, fmt, *args):
        # don't flood the logs with the load balancer health checks
        if self.path == "/health" and len(args) > 1 and str(args[1]) == "200":
            return
        log.info("%s %s", self.client(), fmt % args)

    def client(self):
        return self.headers.get("X-Forwarded-For") or self.client_address[0]

    def reply(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "not found"})
        data = self.state.snapshot()
        data["status"] = "ok"
        self.reply(200, data)

    def do_POST(self):
        if self.path != "/call":
            return self.reply(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self.reply(400, {"error": "bad content length"})
        if length > MAX_BODY:
            return self.reply(413, {"error": "body too large"})
        body = self.rfile.read(length) if length else b""
        if not self.authorized(body):
            log.warning("%s unauthorized call request", self.client())
            return self.reply(401, {"error": "unauthorized"})
        if not self.start_loop():
            log.info("%s call request ignored: a loop is already running", self.client())
            return self.reply(200, {"status": "already running"})
        log.info("%s call request accepted", self.client())
        self.reply(202, {"status": "started"})

    def authorized(self, body):
        if self.hmac_secret:
            sig = self.headers.get("X-Hub-Signature", "")
            expected = "sha1=" + hmac.new(self.hmac_secret.encode(), body, hashlib.sha1).hexdigest()
            if hmac.compare_digest(sig, expected):
                return True
        if self.token:
            auth = self.headers.get("Authorization", "")
            if hmac.compare_digest(auth, "Bearer " + self.token):
                return True
        return False

    def start_loop(self):
        with self.state.lock:
            if self.state.running:
                return False
            self.state.running = True
        threading.Thread(target=self.loop, daemon=True).start()
        return True

    def loop(self):
        started = time.time()
        try:
            rc = callbot.CallBot().run(self.numbers)
        except Exception as exc:
            log.exception("call loop crashed: %s", exc)
            rc = callbot.EXIT_NO_ACK
        with self.state.lock:
            self.state.running = False
            self.state.last = {
                "started": int(started),
                "ended": int(time.time()),
                "acknowledged": rc == callbot.EXIT_OK,
            }


def serve(numbers):
    hmac_secret = callbot.env_str("CALLBOT_HMAC_SECRET")
    token = callbot.env_str("CALLBOT_TOKEN")
    if not hmac_secret and not token:
        log.error("set CALLBOT_HMAC_SECRET and/or CALLBOT_TOKEN. exiting.")
        return callbot.EXIT_CONFIG
    listen = callbot.env_str("CALLBOT_LISTEN", "0.0.0.0:8080")
    host, _, port = listen.rpartition(":")
    try:
        port = int(port)
    except ValueError:
        log.error("CALLBOT_LISTEN=%r is not host:port. exiting.", listen)
        return callbot.EXIT_CONFIG

    Handler.state = State()
    Handler.numbers = numbers
    Handler.hmac_secret = hmac_secret
    Handler.token = token
    httpd = ThreadingHTTPServer((host, port), Handler)
    log.info(
        "listening on %s:%s, auth %s",
        host, port,
        " ".join(n for n, v in (("hmac", hmac_secret), ("token", token)) if v),
    )
    httpd.serve_forever()
    return callbot.EXIT_OK
