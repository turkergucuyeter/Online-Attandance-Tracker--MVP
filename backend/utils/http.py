import json
from http import HTTPStatus
from typing import Any


def parse_json_body(handler) -> Any:
    content_length = int(handler.headers.get('Content-Length', 0))
    if content_length == 0:
        return None
    raw = handler.rfile.read(content_length)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        handler.send_error(HTTPStatus.BAD_REQUEST, 'Geçersiz JSON')
        return None


def send_json(handler, data: Any, status: int = 200):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def send_no_content(handler):
    handler.send_response(HTTPStatus.NO_CONTENT)
    handler.end_headers()
