#!/usr/bin/env python3
"""
Usage:
  python scripts/api_smoke_test.py --base-url http://127.0.0.1:8000
  python scripts/api_smoke_test.py --base-url http://127.0.0.1:8000 --audio ./sample.wav
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class HttpResult:
    status: int
    body: Any


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> HttpResult:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url=url, method=method.upper(), headers=headers, data=data)
    try:
        with urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8")
            return HttpResult(status=res.status, body=json.loads(raw) if raw else {})
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        body = raw
        try:
            body = json.loads(raw)
        except Exception:
            pass
        return HttpResult(status=exc.code, body=body)


def _multipart_form_data(fields: dict[str, str], file_field: str, file_path: str) -> tuple[bytes, str]:
    boundary = f"----SpeakNodeBoundary{uuid.uuid4().hex}"
    line = b"\r\n"
    parts: list[bytes] = []

    for key, value in fields.items():
        parts.extend(
            [
                f"--{boundary}".encode("utf-8"),
                f'Content-Disposition: form-data; name="{key}"'.encode("utf-8"),
                b"",
                str(value).encode("utf-8"),
            ]
        )

    filename = os.path.basename(file_path)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    parts.extend(
        [
            f"--{boundary}".encode("utf-8"),
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"'.encode("utf-8"),
            f"Content-Type: {content_type}".encode("utf-8"),
            b"",
            file_bytes,
            f"--{boundary}--".encode("utf-8"),
            b"",
        ]
    )

    body = line.join(parts)
    content_type_header = f"multipart/form-data; boundary={boundary}"
    return body, content_type_header


def _request_multipart(url: str, fields: dict[str, str], file_field: str, file_path: str) -> HttpResult:
    body, ctype = _multipart_form_data(fields, file_field, file_path)
    headers = {"Content-Type": ctype, "Accept": "application/json"}
    req = Request(url=url, method="POST", headers=headers, data=body)
    try:
        with urlopen(req, timeout=120) as res:
            raw = res.read().decode("utf-8")
            return HttpResult(status=res.status, body=json.loads(raw) if raw else {})
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        body = raw
        try:
            body = json.loads(raw)
        except Exception:
            pass
        return HttpResult(status=exc.code, body=body)


def _print_step(name: str, ok: bool, payload: Any) -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {name}")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:1000])


def _assert_status(result: HttpResult, expected: int | tuple[int, ...], step: str) -> None:
    allowed = expected if isinstance(expected, tuple) else (expected,)
    if result.status not in allowed:
        _print_step(step, False, {"status": result.status, "body": result.body})
        raise RuntimeError(f"{step} failed: status={result.status}, expected={allowed}")
    _print_step(step, True, {"status": result.status, "body": result.body})


def run(base_url: str, chat_id: str, audio_path: str | None, meeting_title: str) -> None:
    base_url = base_url.rstrip("/")
    test_chat_id = f"{chat_id}_{uuid.uuid4().hex[:8]}"

    health = _request_json("GET", f"{base_url}/health")
    _assert_status(health, 200, "GET /health")

    create_chat = _request_json("POST", f"{base_url}/chats", {"chat_id": test_chat_id})
    _assert_status(create_chat, 200, "POST /chats")

    chats = _request_json("GET", f"{base_url}/chats")
    _assert_status(chats, 200, "GET /chats")

    if audio_path:
        if not os.path.exists(audio_path):
            raise RuntimeError(f"Audio file not found: {audio_path}")
        analyze = _request_multipart(
            f"{base_url}/analyze",
            fields={"chat_id": test_chat_id, "meeting_title": meeting_title},
            file_field="file",
            file_path=audio_path,
        )
        _assert_status(analyze, (200, 400), "POST /analyze")
    else:
        print("[SKIP] POST /analyze (no --audio provided)")

    meetings_qs = urlencode({"chat_id": test_chat_id, "limit": 20})
    meetings = _request_json("GET", f"{base_url}/meetings?{meetings_qs}")
    _assert_status(meetings, 200, "GET /meetings")

    graph_export = _request_json("GET", f"{base_url}/graph/export?chat_id={test_chat_id}")
    _assert_status(graph_export, 200, "GET /graph/export")

    agent = _request_json(
        "POST",
        f"{base_url}/agent/query",
        {"chat_id": test_chat_id, "question": "현재 저장된 회의 요약을 알려줘."},
    )
    _assert_status(agent, (200, 404), "POST /agent/query")

    reset = _request_json("DELETE", f"{base_url}/chats/{test_chat_id}")
    _assert_status(reset, 200, "DELETE /chats/{chat_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="SpeakNode API smoke test")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--chat-id", default="smoke")
    parser.add_argument("--audio", default=None, help="Optional audio file path")
    parser.add_argument("--meeting-title", default="Smoke Test Meeting")
    args = parser.parse_args()

    try:
        run(args.base_url, args.chat_id, args.audio, args.meeting_title)
        print("\nSmoke test completed.")
        return 0
    except (RuntimeError, URLError) as exc:
        print(f"\nSmoke test failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
