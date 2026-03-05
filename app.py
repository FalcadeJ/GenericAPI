import base64
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
LOG_FILE = DATA_DIR / "requests.json"
WRITE_LOCK = threading.Lock()
MAX_BODY_CHARS = int(os.getenv("MAX_BODY_CHARS", "1000000"))


def _ensure_log_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        LOG_FILE.write_text("[]", encoding="utf-8")


def _normalize_query_params() -> dict:
    params = {}
    for key in request.args.keys():
        values = request.args.getlist(key)
        params[key] = values if len(values) > 1 else values[0]
    return params


def _get_projuris_signature() -> str | None:
    return (
        request.headers.get("X_Projuris_Signature")
        or request.headers.get("X-Projuris-Signature")
        or request.environ.get("HTTP_X_PROJURIS_SIGNATURE")
    )


def _extract_body() -> tuple[str, object, str | None, bool]:
    raw = request.get_data(cache=True) or b""
    payload_truncated = False

    parsed_json = request.get_json(silent=True)
    if parsed_json is not None:
        raw_text = raw.decode("utf-8", errors="replace")
        if len(raw_text) > MAX_BODY_CHARS:
            raw_text = raw_text[:MAX_BODY_CHARS]
            payload_truncated = True
        return "json", parsed_json, raw_text, payload_truncated

    if request.form:
        form_data = {}
        for key in request.form.keys():
            values = request.form.getlist(key)
            form_data[key] = values if len(values) > 1 else values[0]
        raw_text = raw.decode("utf-8", errors="replace")
        if len(raw_text) > MAX_BODY_CHARS:
            raw_text = raw_text[:MAX_BODY_CHARS]
            payload_truncated = True
        return "form", form_data, raw_text, payload_truncated

    if request.files:
        files = {}
        for key, file_storage in request.files.items():
            files[key] = {
                "filename": file_storage.filename,
                "content_type": file_storage.content_type,
                "content_length": file_storage.content_length,
            }
        raw_text = raw.decode("utf-8", errors="replace")
        if len(raw_text) > MAX_BODY_CHARS:
            raw_text = raw_text[:MAX_BODY_CHARS]
            payload_truncated = True
        return "multipart", files, raw_text, payload_truncated

    if raw:
        try:
            raw_text = raw.decode("utf-8")
            if len(raw_text) > MAX_BODY_CHARS:
                raw_text = raw_text[:MAX_BODY_CHARS]
                payload_truncated = True
            return "raw_text", raw_text, raw_text, payload_truncated
        except UnicodeDecodeError:
            raw_b64 = base64.b64encode(raw).decode("ascii")
            if len(raw_b64) > MAX_BODY_CHARS:
                raw_b64 = raw_b64[:MAX_BODY_CHARS]
                payload_truncated = True
            return "raw_base64", raw_b64, raw_b64, payload_truncated

    return "empty", None, None, payload_truncated


def _append_log(entry: dict) -> None:
    _ensure_log_file()
    with WRITE_LOCK:
        try:
            existing = json.loads(LOG_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []

        existing.append(entry)
        temp_file = LOG_FILE.with_suffix(".tmp")
        temp_file.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_file.replace(LOG_FILE)


def _print_request_to_console(entry: dict) -> None:
    print("\n" + "=" * 80)
    print("[webhook] nova requisição recebida")
    print(json.dumps(entry, ensure_ascii=False, indent=2, default=str))
    print("=" * 80 + "\n", flush=True)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def generic_webhook(path: str):
    payload_type, payload, raw_body, payload_truncated = _extract_body()
    request_id = str(uuid.uuid4())

    log_entry = {
        "request_id": request_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "method": request.method,
        "scheme": request.scheme,
        "host": request.host,
        "url": request.url,
        "base_url": request.base_url,
        "path": "/" + path if path else "/",
        "full_path": request.full_path.rstrip("?"),
        "query_string": request.query_string.decode("utf-8", errors="replace"),
        "query_params": _normalize_query_params(),
        "headers": dict(request.headers),
        "content_type": request.content_type,
        "content_length": request.content_length,
        "mimetype": request.mimetype,
        "remote_port": request.environ.get("REMOTE_PORT"),
        "server_protocol": request.environ.get("SERVER_PROTOCOL"),
        "is_secure": request.is_secure,
        "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
        "projuris_signature": _get_projuris_signature(),
        "payload_type": payload_type,
        "payload": payload,
        "raw_body": raw_body,
        "payload_truncated": payload_truncated,
    }

    _print_request_to_console(log_entry)
    _append_log(log_entry)

    return (
        jsonify(
            {
                "status": "OK",
                "message": "Webhook recebido.",
                "request_id": request_id,
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
