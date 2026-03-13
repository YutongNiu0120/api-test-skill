#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Postman 推送脚本（示例）

用途：供 Codex 通过 MCP 运行，创建或更新 Postman Collection。
约束：
- body 使用 postman/collection.api.json（外层带 collection 包装）
- 若配置文件缺失，会自动写入模板并提示用户补齐 `postman.collection`、`postman.api_key`、`postman.workspace_id`、`postman.url_prefix_var`
- `postman.collection` 为必填，表示目标 Collection 名称
- 当前输出目录会作为一个 controller folder 合并到目标 Collection 下；同名 folder 会被替换，其他 folder 保留
- 更新前会保留旧 Collection 中同名 URL 前缀变量的已有值

用法：
  python scripts/postman_push.py --config api-test.yml --out <输出目录>

说明：
  这只是“推送器”示例。代码扫描/索引/生成 collection 的逻辑建议直接用 Codex 对项目进行解析，
  不强制依赖脚本。你也可以完全跳过本脚本，改用 MCP 的 HTTP 工具直接调用。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Tuple, List, Optional

import urllib.request
import urllib.error

from config_utils import ConfigBootstrapRequired, load_config, normalize_config_path


class PostmanRequestError(RuntimeError):
    """Raised when a Postman API call fails."""


def _get_api_key(cfg: Dict[str, Any]) -> str:
    postman = cfg.get("postman", {})
    v = (postman.get("api_key") or "").strip()
    if not v or v == "xxxxx":
        raise SystemExit("未配置 postman.api_key，无法推送 Postman。")
    return v


def _get_collection_name(cfg: Dict[str, Any]) -> str:
    postman = cfg.get("postman", {})
    v = (postman.get("collection") or "").strip()
    if not v or v in {"REPLACE_ME", "xxxxx"}:
        raise SystemExit("未配置 postman.collection，无法确定目标 Collection。")
    return v


def _get_url_prefix_var(cfg: Dict[str, Any]) -> str:
    postman = cfg.get("postman", {})
    v = (postman.get("url_prefix_var") or "").strip()
    if not v or v in {"REPLACE_ME", "xxxxx"}:
        raise SystemExit("未配置 postman.url_prefix_var，无法稳定生成 Postman URL。")
    return v


def _get_url_prefix_value(cfg: Dict[str, Any]) -> str:
    postman = cfg.get("postman", {})
    return (postman.get("url_prefix_value") or "").strip()


def _http_request(method: str, url: str, api_key: str, payload: Optional[Dict[str, Any]] = None) -> Tuple[int, Dict[str, Any], str]:
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, method=method)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        status = resp.status
    return status, (json.loads(raw) if raw else {}), raw


def _log_line(log_file: Path, line: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _call_postman(
    *,
    log_file: Path,
    method: str,
    url: str,
    api_key: str,
    action_desc: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[int, Dict[str, Any], str]:
    headers = {"X-API-Key": api_key}
    if payload is not None:
        headers["Content-Type"] = "application/json"

    _log_line(log_file, f"[{_utc_now()}] {method} {url}")
    _log_line(log_file, f"[{_utc_now()}] request_headers={headers}")
    if payload is not None:
        _log_line(log_file, f"[{_utc_now()}] request_body={json.dumps(payload, ensure_ascii=False)}")

    try:
        status, res, raw = _http_request(method, url, api_key, payload)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if hasattr(e, "read") else ""
        _log_line(log_file, f"[{_utc_now()}] HTTPError status={e.code} action={action_desc}")
        if body:
            _log_line(log_file, f"[{_utc_now()}] response={body}")
        raise PostmanRequestError(f"{action_desc}失败：HTTP {e.code}") from e
    except urllib.error.URLError as e:
        _log_line(log_file, f"[{_utc_now()}] URLError reason={e.reason} action={action_desc}")
        raise PostmanRequestError(f"{action_desc}失败：{e.reason}") from e

    _log_line(log_file, f"[{_utc_now()}] status={status} action={action_desc}")
    if raw:
        _log_line(log_file, f"[{_utc_now()}] response={raw}")
    return status, res, raw


def _extract_collection_uid(summary: Dict[str, Any]) -> str:
    return str((summary.get("uid") or summary.get("id") or "")).strip()


def _find_workspace_collection_by_name(
    *,
    api_base: str,
    workspace_id: str,
    api_key: str,
    collection_name: str,
    log_file: Path,
) -> Optional[Dict[str, Any]]:
    ws_url = f"{api_base}/workspaces/{workspace_id}"
    _, ws_res, _ = _call_postman(
        log_file=log_file,
        method="GET",
        url=ws_url,
        api_key=api_key,
        action_desc="拉取 workspace",
    )
    collections: List[Dict[str, Any]] = (ws_res.get("workspace") or {}).get("collections") or []
    for collection in collections:
        if (collection.get("name") or "").strip() == collection_name:
            return collection
    return None


def _get_collection_variable_list(collection: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(collection.get("variable"), list):
        return [dict(item) for item in collection.get("variable") or [] if isinstance(item, dict)]
    if isinstance(collection.get("variables"), list):
        return [dict(item) for item in collection.get("variables") or [] if isinstance(item, dict)]
    return []


def _set_collection_variable_list(collection: Dict[str, Any], variables: List[Dict[str, Any]]) -> None:
    collection["variable"] = variables
    collection.pop("variables", None)


def _get_collection_variable_value(collection: Dict[str, Any], key: str) -> str:
    for variable in _get_collection_variable_list(collection):
        if (variable.get("key") or "").strip() == key:
            return str(variable.get("value") or "").strip()
    return ""


def _remove_collection_variable(collection: Dict[str, Any], key: str) -> None:
    variables = [
        variable
        for variable in _get_collection_variable_list(collection)
        if (variable.get("key") or "").strip() != key
    ]
    if variables:
        _set_collection_variable_list(collection, variables)
    else:
        collection.pop("variable", None)
        collection.pop("variables", None)


def _upsert_collection_variable(collection: Dict[str, Any], key: str, value: str) -> None:
    variables = _get_collection_variable_list(collection)
    for variable in variables:
        if (variable.get("key") or "").strip() == key:
            variable["value"] = value
            variable["type"] = variable.get("type") or "string"
            _set_collection_variable_list(collection, variables)
            return
    variables.append({"key": key, "value": value, "type": "string"})
    _set_collection_variable_list(collection, variables)


def _apply_url_prefix_variable(
    *,
    payload_collection: Dict[str, Any],
    existing_collection: Optional[Dict[str, Any]],
    url_prefix_var: str,
    configured_value: str,
    log_file: Path,
) -> str:
    existing_value = ""
    if existing_collection:
        existing_value = _get_collection_variable_value(existing_collection, url_prefix_var)

    if existing_value:
        _upsert_collection_variable(payload_collection, url_prefix_var, existing_value)
        _log_line(
            log_file,
            f"[{_utc_now()}] preserve existing collection variable key='{url_prefix_var}' value_source='existing_collection'",
        )
        return "existing_collection"

    if configured_value:
        _upsert_collection_variable(payload_collection, url_prefix_var, configured_value)
        _log_line(
            log_file,
            f"[{_utc_now()}] apply configured collection variable key='{url_prefix_var}' value_source='config'",
        )
        return "config"

    _remove_collection_variable(payload_collection, url_prefix_var)
    _log_line(
        log_file,
        f"[{_utc_now()}] no collection variable value for key='{url_prefix_var}', keep placeholder only in request URLs",
    )
    return "none"


def _ensure_controller_folder(payload_collection: Dict[str, Any], folder_name: str) -> None:
    items = payload_collection.get("item")
    if not isinstance(items, list):
        payload_collection["item"] = [{"name": folder_name, "item": []}]
        return
    if len(items) == 1:
        first = items[0]
        if isinstance(first, dict) and (first.get("name") or "").strip() == folder_name and isinstance(first.get("item"), list):
            return
    payload_collection["item"] = [{"name": folder_name, "item": items}]


def _merge_controller_folder(
    existing_collection: Dict[str, Any],
    controller_folder: Dict[str, Any],
) -> None:
    existing_items = existing_collection.get("item")
    if not isinstance(existing_items, list):
        existing_items = []
    folder_name = (controller_folder.get("name") or "").strip()
    merged = []
    replaced = False
    for item in existing_items:
        if isinstance(item, dict) and (item.get("name") or "").strip() == folder_name:
            merged.append(controller_folder)
            replaced = True
        else:
            merged.append(item)
    if not replaced:
        merged.append(controller_folder)
    existing_collection["item"] = merged


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="api-test.yml", help="配置文件路径")
    ap.add_argument("--out", required=True, help="输出目录（包含 postman/collection.api.json）")
    ap.add_argument(
        "--force",
        action="store_true",
        help="兼容保留。当前默认就会覆盖同名 Collection 内容；该参数不再是必需项。",
    )
    args = ap.parse_args()

    config_path = normalize_config_path(args.config)
    try:
        cfg, _ = load_config(config_path)
    except ConfigBootstrapRequired as exc:
        raise SystemExit(str(exc)) from exc
    postman_cfg = cfg.get("postman", {})
    if not postman_cfg.get("push_enabled", False):
        raise SystemExit("postman.push_enabled=false，已跳过推送。")

    api_base = postman_cfg.get("api_base", "https://api.getpostman.com").rstrip("/")
    workspace_id = (postman_cfg.get("workspace_id") or "").strip()
    if not workspace_id or workspace_id in {"REPLACE_ME", "xxxxx"}:
        raise SystemExit("未配置 postman.workspace_id，无法推送 Postman。")

    out_dir = Path(args.out)
    payload_file = out_dir / "postman" / "collection.api.json"
    if not payload_file.exists():
        raise SystemExit(f"未找到文件：{payload_file}")

    log_file = out_dir / "postman" / "push.log"
    payload_text = payload_file.read_text(encoding="utf-8")
    payload = json.loads(payload_text)
    api_key = _get_api_key(cfg)
    target_collection_name = _get_collection_name(cfg)
    url_prefix_var = _get_url_prefix_var(cfg)
    url_prefix_value = _get_url_prefix_value(cfg)
    meta_file = out_dir / "postman" / "push.meta.json"
    collection_payload = payload.get("collection") or {}
    collection_payload.setdefault("info", {})
    collection_payload["info"]["name"] = target_collection_name
    controller_folder_name = out_dir.name
    _ensure_controller_folder(collection_payload, controller_folder_name)
    controller_folder = ((collection_payload.get("item") or [None])[0]) if isinstance(collection_payload.get("item"), list) else None
    if not isinstance(controller_folder, dict):
        raise SystemExit("payload 缺少可用的 controller folder，无法推送。")

    try:
        existing_summary = _find_workspace_collection_by_name(
            api_base=api_base,
            workspace_id=workspace_id,
            api_key=api_key,
            collection_name=target_collection_name,
            log_file=log_file,
        )
    except PostmanRequestError as e:
        raise SystemExit(f"Postman 拉取 workspace 失败：{e}") from e

    existing_uid = _extract_collection_uid(existing_summary or {})
    existing_collection = None
    if existing_uid:
        detail_url = f"{api_base}/collections/{existing_uid}"
        try:
            _, existing_res, _ = _call_postman(
                log_file=log_file,
                method="GET",
                url=detail_url,
                api_key=api_key,
                action_desc="读取旧 collection",
            )
        except PostmanRequestError as e:
            raise SystemExit(f"Postman 读取旧 collection 失败：{e}") from e
        existing_collection = (existing_res.get("collection") or {}) if isinstance(existing_res, dict) else {}

    url_prefix_source = _apply_url_prefix_variable(
        payload_collection=collection_payload,
        existing_collection=existing_collection,
        url_prefix_var=url_prefix_var,
        configured_value=url_prefix_value,
        log_file=log_file,
    )

    action = "create"
    res: Dict[str, Any]
    status: int

    if existing_uid:
        if isinstance(existing_collection, dict) and existing_collection:
            existing_collection.setdefault("info", {})
            existing_collection["info"]["name"] = target_collection_name
            if "auth" not in existing_collection and "auth" in collection_payload:
                existing_collection["auth"] = collection_payload["auth"]
            _merge_controller_folder(existing_collection, controller_folder)
            _apply_url_prefix_variable(
                payload_collection=existing_collection,
                existing_collection=existing_collection,
                url_prefix_var=url_prefix_var,
                configured_value=url_prefix_value,
                log_file=log_file,
            )
            payload["collection"] = existing_collection
        update_url = f"{api_base}/collections/{existing_uid}"
        try:
            status, res, _ = _call_postman(
                log_file=log_file,
                method="PUT",
                url=update_url,
                api_key=api_key,
                action_desc="更新 collection",
                payload=payload,
            )
            action = "update"
        except PostmanRequestError as update_error:
            _log_line(log_file, f"[{_utc_now()}] update failed: {update_error}")
            raise SystemExit(f"Postman 更新 collection 失败：{update_error}") from update_error
        action = "merge_folder"
    else:
        create_url = f"{api_base}/collections?workspace={workspace_id}"
        try:
            status, res, _ = _call_postman(
                log_file=log_file,
                method="POST",
                url=create_url,
                api_key=api_key,
                action_desc="创建 collection",
                payload=payload,
            )
        except PostmanRequestError as e:
            raise SystemExit(f"Postman 创建 collection 失败：{e}") from e

    meta = {
        "workspace_id": workspace_id,
        "collection_name": target_collection_name,
        "collection_uid": (res.get("collection") or {}).get("uid") or existing_uid,
        "status": "ok" if 200 <= status < 300 else f"http_{status}",
        "action": action,
        "controller_folder_name": controller_folder_name,
        "url_prefix_var": url_prefix_var,
        "url_prefix_value_source": url_prefix_source,
        "pushed_at_utc": _utc_now(),
    }
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # 仅打印必要信息（不含 key）
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
