#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run api-test seed, Postman CLI, reporting, and conditional cleanup."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config_utils import ConfigBootstrapRequired, find_missing_fields, get_value, load_config, normalize_config_path
from sql_runner import execute_sql_file


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _validate_autotest_config(cfg: Dict[str, Any]) -> None:
    enabled = bool(get_value(cfg, "autotest.enabled"))
    if not enabled:
        raise SystemExit("autotest.enabled=false，已跳过自动执行。")

    missing = find_missing_fields(
        cfg,
        [
            "database.type",
            "database.host",
            "database.port",
            "database.database",
            "database.username",
            "database.password",
            "database.charset",
            "postman.url_prefix_var",
            "postman.url_prefix_value",
        ],
    )
    if missing:
        raise SystemExit(f"自动执行缺少配置：{', '.join(missing)}")

    sql_dialect = str(get_value(cfg, "generation.sql_dialect") or "").strip().lower()
    if sql_dialect != "mysql":
        raise SystemExit(f"当前自动执行仅支持 mysql，收到 generation.sql_dialect={sql_dialect!r}")


def _postman_env_vars(cfg: Dict[str, Any]) -> List[str]:
    env_args: List[str] = []
    url_prefix_var = str(get_value(cfg, "postman.url_prefix_var")).strip()
    url_prefix_value = str(get_value(cfg, "postman.url_prefix_value")).strip()
    env_args.extend(["--env-var", f"{url_prefix_var}={url_prefix_value}"])

    token = os.getenv("API_TEST_TOKEN") or os.getenv("POSTMAN_TOKEN")
    if token:
        env_args.extend(["--env-var", f"token={token}"])
    return env_args


def _parse_postman_report(report_path: Path) -> Dict[str, Any]:
    report = _load_json(report_path)
    run = report.get("run") or {}
    stats = run.get("stats") or {}
    tests = stats.get("tests") or {}
    failures = run.get("failures") or []

    failed_requests: List[str] = []
    for failure in failures:
        source = failure.get("source") or {}
        name = source.get("name") or failure.get("error", {}).get("name") or failure.get("message")
        if name:
            failed_requests.append(str(name))

    return {
        "tests_total": tests.get("total"),
        "tests_failed": tests.get("failed"),
        "tests_pending": tests.get("pending"),
        "assertions_total": (stats.get("assertions") or {}).get("total"),
        "assertions_failed": (stats.get("assertions") or {}).get("failed"),
        "requests_total": (stats.get("requests") or {}).get("total"),
        "requests_failed": (stats.get("requests") or {}).get("failed"),
        "failed_requests": failed_requests,
    }


def _run_postman_cli(*, repo_root: Path, out_dir: Path, report_dir: Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    postman_cmd = shutil.which("postman")
    if not postman_cmd:
        raise SystemExit("未找到 Postman CLI，请先安装并确保 `postman` 在 PATH 中。")

    collection_path = out_dir / "postman" / "collection.import.json"
    if not collection_path.exists():
        raise SystemExit(f"未找到 Postman Collection 文件：{collection_path}")

    log_path = report_dir / "postman-run.log"
    json_report = report_dir / "postman-run.json"
    junit_report = report_dir / "postman-run.junit.xml"
    html_report = report_dir / "postman-run.html"

    command = [
        postman_cmd,
        "collection",
        "run",
        str(collection_path),
        "--working-dir",
        str(repo_root),
        "--reporters",
        "cli,json,junit,html",
        "--reporter-json-structure",
        "newman",
        "--reporter-json-export",
        str(json_report),
        "--reporter-junit-export",
        str(junit_report),
        "--reporter-html-export",
        str(html_report),
    ]
    command.extend(_postman_env_vars(cfg))

    completed = subprocess.run(  # noqa: S603
        command,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    _write_text(log_path, completed.stdout)

    summary = {
        "status": "ok" if completed.returncode == 0 else "failed",
        "command": command,
        "exit_code": completed.returncode,
        "log_file": str(log_path),
        "json_report": str(json_report),
        "junit_report": str(junit_report),
        "html_report": str(html_report),
        "token_source": "env" if (os.getenv("API_TEST_TOKEN") or os.getenv("POSTMAN_TOKEN")) else "none",
    }
    summary.update(_parse_postman_report(json_report))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="api-test.yml", help="配置文件路径")
    parser.add_argument("--out", required=True, help="本次生成的输出目录")
    args = parser.parse_args()

    config_path = normalize_config_path(args.config)
    try:
        cfg, _ = load_config(config_path)
    except ConfigBootstrapRequired as exc:
        raise SystemExit(str(exc)) from exc

    _validate_autotest_config(cfg)

    repo_root = config_path.parent
    out_dir = Path(args.out).expanduser().resolve()
    report_dir = out_dir / "report"
    report_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "started_at_utc": _now(),
        "config_file": str(config_path),
        "output_dir": str(out_dir),
        "autotest": {
            "enabled": bool(get_value(cfg, "autotest.enabled")),
            "always_cleanup": bool(get_value(cfg, "autotest.always_cleanup")),
        },
    }

    seed_log = report_dir / "seed.log"
    cleanup_log = report_dir / "cleanup.log"
    seed_path = out_dir / "sql" / "seed.sql"
    cleanup_path = out_dir / "sql" / "cleanup.sql"

    seed_summary = execute_sql_file(sql_path=seed_path, cfg=cfg, log_file=seed_log, label="seed")
    summary["seed"] = seed_summary
    if seed_summary["status"] == "failed":
        summary["postman"] = {"status": "skipped", "reason": "seed_failed"}
        summary["cleanup"] = {"status": "skipped", "reason": "seed_failed"}
        summary["finished_at_utc"] = _now()
        summary["overall_status"] = "failed"
        summary_path = report_dir / "run-summary.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    postman_summary = _run_postman_cli(repo_root=repo_root, out_dir=out_dir, report_dir=report_dir, cfg=cfg)
    summary["postman"] = postman_summary

    always_cleanup = bool(get_value(cfg, "autotest.always_cleanup"))
    should_cleanup = seed_summary["status"] == "ok" and (always_cleanup or postman_summary["status"] == "ok")
    if should_cleanup:
        cleanup_summary = execute_sql_file(sql_path=cleanup_path, cfg=cfg, log_file=cleanup_log, label="cleanup")
    else:
        cleanup_summary = {"status": "skipped", "reason": "policy_not_matched", "sql_file": str(cleanup_path)}
    summary["cleanup"] = cleanup_summary

    success = postman_summary["status"] == "ok" and cleanup_summary["status"] in {"ok", "skipped"}
    summary["finished_at_utc"] = _now()
    summary["overall_status"] = "ok" if success else "failed"

    summary_path = report_dir / "run-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
