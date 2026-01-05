from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sys
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from flask import Blueprint, Response, jsonify, render_template, request

repo_root = Path(__file__).resolve().parents[1]
repo_root_str = str(repo_root)
if repo_root_str in sys.path:
    sys.path.remove(repo_root_str)
sys.path.insert(0, repo_root_str)

try:
    from mediaweb.utils.aws_sigv4 import aws_v4_headers
except ImportError as exc:
    raise ImportError(
        "mediaweb.utils.aws_sigv4 is required to access the media bucket."
    ) from exc


SELECT_FIELDS = """
    id, workspace_id, fingerprint, tiny_fingerprint, object_key,
    file_name, file_path, created_at
"""


@dataclass(frozen=True)
class MediaWebConfig:
    db_path: str
    storage_endpoint: str
    storage_bucket: str
    storage_region: str
    storage_access_key: str
    storage_secret_key: str
    storage_session_token: str


def _encode_path(path: str) -> str:
    return quote(path, safe="/-_.~")


def _parse_storage_endpoint(endpoint: str) -> tuple[str, str]:
    parsed = urlparse(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise RuntimeError(f"invalid storage endpoint: {endpoint}")
    return parsed.scheme, parsed.netloc


def _build_s3_headers(
    config: MediaWebConfig,
    method: str,
    canonical_uri: str,
    payload: bytes = b"",
) -> dict[str, str]:
    extra_headers: dict[str, str] = {}
    if config.storage_session_token:
        extra_headers["x-amz-security-token"] = config.storage_session_token
    scheme, host = _parse_storage_endpoint(config.storage_endpoint)
    return aws_v4_headers(
        config.storage_access_key,
        config.storage_secret_key,
        config.storage_region,
        "s3",
        method,
        host,
        canonical_uri,
        payload,
        extra_headers,
    )


def _s3_request(config: MediaWebConfig, method: str, object_key: str, payload: bytes = b"") -> tuple[int, bytes, Any]:
    scheme, host = _parse_storage_endpoint(config.storage_endpoint)
    path = f"/{config.storage_bucket}/{object_key.lstrip('/')}"
    canonical_uri = _encode_path(path)
    url = f"{scheme}://{host}{canonical_uri}"
    headers = _build_s3_headers(config, method, canonical_uri, payload)
    req = Request(url, data=payload if method in {"PUT", "POST"} else None, headers=headers, method=method)
    with urlopen(req, timeout=30) as resp:
        return resp.status, resp.read(), resp.headers


def _open_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _fetch_items(db_path: str, since_id: int | None = None):
    query = f"""
        SELECT {SELECT_FIELDS}
        FROM media_files
        WHERE object_key IS NOT NULL AND object_key != ''
    """
    params: tuple[Any, ...] = ()
    if since_id is not None:
        query += " AND id > ?"
        params = (since_id,)
        query += " ORDER BY id ASC"
    else:
        query += " ORDER BY created_at DESC"
    with _open_db(db_path) as conn:
        return conn.execute(query, params).fetchall()


def _resolve_db_error(db_path: str, error: Exception) -> str:
    db_file = Path(db_path)
    if not db_file.exists():
        return f"未找到数据库：{db_path}"
    if "no such table" in str(error):
        return "数据库缺少 media_files 表"
    return f"数据库读取失败：{error}"


def create_media_blueprint(config: MediaWebConfig) -> Blueprint:
    media_root = Path(__file__).resolve().parents[1] / "mediaweb"
    bp = Blueprint(
        "media",
        __name__,
        static_folder=str(media_root / "static"),
        template_folder=str(media_root / "templates"),
        static_url_path="/static",
    )

    def _row_to_item(row: sqlite3.Row) -> dict[str, Any]:
        created = datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
        return {**dict(row), "created_at": created}

    @bp.route("/")
    def index():
        api_base = request.script_root + "/media"
        try:
            rows = _fetch_items(config.db_path)
            items = [_row_to_item(row) for row in rows]
            error_message = None
        except Exception as exc:
            items = []
            error_message = _resolve_db_error(config.db_path, exc)
        return render_template("index.html", items=items, api_base=api_base, error_message=error_message)

    @bp.route("/api/media")
    def api_media():
        since_id = request.args.get("since_id", "0")
        try:
            since_id = int(since_id)
        except ValueError:
            return jsonify({"error": "invalid since_id"}), 400
        try:
            rows = _fetch_items(config.db_path, since_id=since_id)
            items = [_row_to_item(row) for row in rows]
            return jsonify({"items": items})
        except Exception as exc:
            return jsonify({"error": _resolve_db_error(config.db_path, exc)}), 404

    @bp.route("/preview")
    def preview():
        object_key = request.args.get("object_key", "")
        if not object_key:
            return Response("missing object_key", status=400)
        status, body, headers = _s3_request(config, "GET", object_key)
        if status != 200:
            return Response(f"upstream status={status}", status=502)
        content_type = headers.get("Content-Type", "application/octet-stream")
        resp = Response(body, status=200, content_type=content_type)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @bp.route("/delete", methods=["POST"])
    def delete_item():
        record_id = request.form.get("record_id", "")
        object_key = request.form.get("object_key", "")
        if not record_id or not object_key:
            return jsonify({"ok": False, "error": "missing record_id/object_key"}), 400
        _s3_request(config, "DELETE", object_key)
        with _open_db(config.db_path) as conn:
            conn.execute("DELETE FROM media_files WHERE id=?", (record_id,))
            conn.commit()
        return jsonify({"ok": True, "id": record_id})

    return bp
