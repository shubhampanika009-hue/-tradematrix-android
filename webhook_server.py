"""
webhook_server.py - self-healing asyncio HTTP server (standard library only).

Why not FastAPI inside the APK?  FastAPI -> pydantic v2 -> pydantic-core (Rust) has no
python-for-android recipe, so the Buildozer build fails. asyncio streams need nothing extra.

Routes
  POST /webhook  -> handler(payload: dict) -> (status:int, message:str)
  GET  /health   -> 200

Robustness
  * if the port is busy, the next 5 ports are tried (self.port holds the one in use)
  * if binding fails or the loop dies, it retries with exponential back-off (1s .. 30s)
  * request size / time limits, max 64 concurrent connections, handler timeout
"""
import asyncio
import json
import threading
from typing import Callable, Optional, Tuple

from core.logger import log

MAX_BODY = 64 * 1024
READ_TIMEOUT = 5
HANDLER_TIMEOUT = 10
MAX_CLIENTS = 64
PORT_TRIES = 6

REASONS = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 404: "Not Found",
           405: "Method Not Allowed", 413: "Payload Too Large", 500: "Internal Server Error",
           503: "Service Unavailable"}


class WebhookServer:
    def __init__(self, host: str, port: int,
                 handler: Callable[[dict], Tuple[int, str]],
                 on_status: Optional[Callable[[str], None]] = None):
        self.host, self.base_port, self.port = host, port, port
        self.handler, self.on_status = handler, on_status
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.running = threading.Event()
        self._stopping = threading.Event()
        self._active = 0

    # ---- lifecycle -------------------------------------------------------
    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name="webhook")
        self.thread.start()

    def stop(self):
        self._stopping.set()
        loop = self.loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

    def _status(self, msg: str):
        log.info(msg)
        if self.on_status:
            try:
                self.on_status(msg)
            except Exception:
                log.exception("on_status callback failed")

    def _run(self):
        backoff = 1
        while not self._stopping.is_set():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop, server = loop, None
            try:
                server = loop.run_until_complete(self._bind())
                self.running.set()
                self._status(f"Listening on port {self.port}")
                backoff = 1
                if not self._stopping.is_set():
                    loop.run_forever()
            except Exception as e:
                log.exception("webhook server error")
                self._status(f"Server error: {e}. Retry in {backoff}s")
            finally:
                self.running.clear()
                try:
                    if server:
                        server.close()
                        loop.run_until_complete(server.wait_closed())
                    loop.close()
                except Exception:
                    pass
            if self._stopping.wait(backoff):
                break
            backoff = min(backoff * 2, 30)

    async def _bind(self):
        last: Optional[Exception] = None
        for p in range(self.base_port, self.base_port + PORT_TRIES):
            try:
                srv = await asyncio.start_server(self._client, self.host, p)
                self.port = p
                return srv
            except OSError as e:
                last = e
        raise last or OSError("no free port")

    # ---- request handling ------------------------------------------------
    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        if self._active >= MAX_CLIENTS:
            await self._safe_reply(writer, 503, "busy")
            return self._close(writer)
        self._active += 1
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), READ_TIMEOUT)
            lines = head.decode("latin-1").split("\r\n")
            method, path, _ = lines[0].split(" ", 2)
            headers = {}
            for ln in lines[1:]:
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    headers[k.strip().lower()] = v.strip()
            length = int(headers.get("content-length", "0") or 0)
            if length < 0 or length > MAX_BODY:
                return await self._reply(writer, 413, "payload too large")
            body = (await asyncio.wait_for(reader.readexactly(length), READ_TIMEOUT)
                    if length else b"")
            path = path.split("?")[0]

            if path == "/health" and method == "GET":
                return await self._reply(writer, 200, "ok")
            if path != "/webhook":
                return await self._reply(writer, 404, "not found")
            if method != "POST":
                return await self._reply(writer, 405, "POST only")
            try:
                payload = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return await self._reply(writer, 400, "body is not valid JSON")
            try:
                status, msg = await asyncio.wait_for(
                    self.loop.run_in_executor(None, self.handler, payload), HANDLER_TIMEOUT)
            except asyncio.TimeoutError:
                status, msg = 500, "handler timeout"
            await self._reply(writer, status, msg)
        except Exception as e:
            log.debug("bad client request: %r", e)
            await self._safe_reply(writer, 400, "bad request")
        finally:
            self._active -= 1
            self._close(writer)

    @staticmethod
    def _close(writer):
        try:
            writer.close()
        except Exception:
            pass

    async def _safe_reply(self, writer, status, msg):
        try:
            await self._reply(writer, status, msg)
        except Exception:
            pass

    @staticmethod
    async def _reply(writer: asyncio.StreamWriter, status: int, msg: str):
        body = json.dumps({"status": "ok" if status == 200 else "error", "message": msg}).encode()
        writer.write(f"HTTP/1.1 {status} {REASONS.get(status, 'Error')}\r\n"
                     f"Content-Type: application/json\r\nContent-Length: {len(body)}\r\n"
                     f"Connection: close\r\n\r\n".encode() + body)
        await writer.drain()
