from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .clarifier import clarify_user_input, load_clarifier_session
from .config import PROJECT_ROOT
from .exceptions import ClarifierRequestError


CLARIFIER_WEB_PAGE = PROJECT_ROOT / "web" / "clarifier.html"


def run_clarifier_turn(
    *,
    message: str,
    session_payload: str = "",
    brief: str = "",
    model: str | None = None,
    prefer_llm: bool = False,
) -> dict[str, Any]:
    normalized_message = str(message or "").strip()
    if not normalized_message:
        raise ClarifierRequestError("message must not be empty.")

    session = None
    if session_payload.strip():
        try:
            session = load_clarifier_session(session_payload)
        except Exception as exc:
            raise ClarifierRequestError(f"invalid session payload: {exc}") from exc

    result = clarify_user_input(
        normalized_message,
        session=session,
        original_brief=brief,
        model=model,
        prefer_llm=prefer_llm,
    )
    return result.to_dict()


class ClarifierHttpHandler(BaseHTTPRequestHandler):
    server_version = "SIEClarifierHTTP/0.1"

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, payload: str, status: HTTPStatus = HTTPStatus.OK, content_type: str = "text/html; charset=utf-8") -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ClarifierRequestError(f"invalid json body: {exc}") from exc
        if not isinstance(payload, dict):
            raise ClarifierRequestError("json body must be an object.")
        return payload

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/":
            self._send_text(CLARIFIER_WEB_PAGE.read_text(encoding="utf-8"))
            return
        if route == "/api/health":
            self._send_json({"status": "ok"})
            return
        self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route != "/api/clarify":
            self._send_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json_body()
            result = run_clarifier_turn(
                message=str(payload.get("message", "")).strip(),
                session_payload=str(payload.get("session", "") or ""),
                brief=str(payload.get("brief", "") or ""),
                model=(str(payload.get("model", "")).strip() or None),
                prefer_llm=bool(payload.get("prefer_llm", False)),
            )
        except ClarifierRequestError as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:  # pragma: no cover - defensive server guard
            self._send_json({"error": f"internal server error: {exc}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json(result)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def serve_clarifier_web(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> str:
    if not CLARIFIER_WEB_PAGE.exists():
        raise FileNotFoundError(f"clarifier web page not found: {CLARIFIER_WEB_PAGE}")

    address = (host, int(port))
    server = ThreadingHTTPServer(address, ClarifierHttpHandler)
    url = f"http://{host}:{port}"
    print(url)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return url
