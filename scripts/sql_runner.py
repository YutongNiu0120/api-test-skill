#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Execute api-test SQL files against MySQL using PyMySQL."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

from config_utils import (
    ConfigBootstrapRequired,
    ensure_python_package,
    find_missing_fields,
    get_value,
    load_config,
    normalize_config_path,
)

pymysql = ensure_python_package("pymysql", "PyMySQL")
ALLOWED_SQL_FILENAMES = {"seed.sql", "cleanup.sql"}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _append_log(log_file: Path | None, line: str) -> None:
    if log_file is None:
        return
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(line.rstrip() + "\n")


def _require_allowed_sql(sql_path: Path) -> None:
    if sql_path.name not in ALLOWED_SQL_FILENAMES:
        raise SystemExit("仅允许执行输出目录中的 seed.sql 或 cleanup.sql。")


def _database_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
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
        ],
    )
    if missing:
        raise SystemExit(f"缺少数据库配置：{', '.join(missing)}")

    db_type = str(get_value(cfg, "database.type")).strip().lower()
    if db_type != "mysql":
        raise SystemExit(f"当前仅支持 MySQL，收到 database.type={db_type!r}")

    return {
        "host": str(get_value(cfg, "database.host")).strip(),
        "port": int(get_value(cfg, "database.port")),
        "database": str(get_value(cfg, "database.database")).strip(),
        "user": str(get_value(cfg, "database.username")).strip(),
        "password": str(get_value(cfg, "database.password")),
        "charset": str(get_value(cfg, "database.charset")).strip(),
    }


def split_sql_statements(sql_text: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    quote: str | None = None
    line_comment = False
    block_comment = False
    index = 0
    length = len(sql_text)

    while index < length:
        char = sql_text[index]
        next_char = sql_text[index + 1] if index + 1 < length else ""

        if line_comment:
            if char == "\n":
                line_comment = False
            index += 1
            continue

        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                index += 2
            else:
                index += 1
            continue

        if quote:
            current.append(char)
            if char == quote:
                if next_char == quote and quote == "'":
                    current.append(next_char)
                    index += 2
                    continue
                if index == 0 or sql_text[index - 1] != "\\":
                    quote = None
            index += 1
            continue

        if char == "-" and next_char == "-":
            third = sql_text[index + 2] if index + 2 < length else ""
            if third in {"", " ", "\t", "\r", "\n"}:
                line_comment = True
                index += 2
                continue

        if char == "#":
            line_comment = True
            index += 1
            continue

        if char == "/" and next_char == "*":
            block_comment = True
            index += 2
            continue

        if char in {"'", '"', "`"}:
            quote = char
            current.append(char)
            index += 1
            continue

        if char == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue

        current.append(char)
        index += 1

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def execute_sql_file(
    *,
    sql_path: Path,
    cfg: Dict[str, Any],
    log_file: Path | None = None,
    label: str | None = None,
) -> Dict[str, Any]:
    _require_allowed_sql(sql_path)
    db_cfg = _database_config(cfg)
    sql_label = label or sql_path.name

    if not sql_path.exists():
        summary = {"status": "skipped", "reason": "file_not_found", "sql_file": str(sql_path)}
        _append_log(log_file, f"[{_now()}] skip {sql_label}: file not found -> {sql_path}")
        return summary

    sql_text = sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    if not statements:
        summary = {"status": "skipped", "reason": "empty_sql", "sql_file": str(sql_path)}
        _append_log(log_file, f"[{_now()}] skip {sql_label}: no executable statement")
        return summary

    _append_log(
        log_file,
        f"[{_now()}] start {sql_label}: host={db_cfg['host']} port={db_cfg['port']} "
        f"database={db_cfg['database']} user={db_cfg['user']} statements={len(statements)}",
    )
    started = time.time()
    executed = 0
    connection = pymysql.connect(
        host=db_cfg["host"],
        port=db_cfg["port"],
        user=db_cfg["user"],
        password=db_cfg["password"],
        database=db_cfg["database"],
        charset=db_cfg["charset"],
        autocommit=False,
    )

    try:
        with connection.cursor() as cursor:
            for index, statement in enumerate(statements, start=1):
                cursor.execute(statement)
                executed = index
                preview = " ".join(statement.split())[:160]
                _append_log(log_file, f"[{_now()}] executed #{index}: {preview}")
        connection.commit()
    except Exception as exc:  # noqa: BLE001
        connection.rollback()
        _append_log(log_file, f"[{_now()}] failed {sql_label}: {exc}")
        return {
            "status": "failed",
            "sql_file": str(sql_path),
            "statement_count": len(statements),
            "executed_count": executed,
            "error": str(exc),
            "duration_ms": int((time.time() - started) * 1000),
        }
    finally:
        connection.close()

    duration_ms = int((time.time() - started) * 1000)
    _append_log(log_file, f"[{_now()}] done {sql_label}: executed={executed} duration_ms={duration_ms}")
    return {
        "status": "ok",
        "sql_file": str(sql_path),
        "statement_count": len(statements),
        "executed_count": executed,
        "duration_ms": duration_ms,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="api-test.yml", help="配置文件路径")
    parser.add_argument("--sql", required=True, help="仅允许 seed.sql 或 cleanup.sql")
    parser.add_argument("--log", help="日志文件路径")
    parser.add_argument("--label", help="日志展示用标签")
    args = parser.parse_args()

    config_path = normalize_config_path(args.config)
    try:
        cfg, _ = load_config(config_path)
    except ConfigBootstrapRequired as exc:
        raise SystemExit(str(exc)) from exc

    summary = execute_sql_file(
        sql_path=Path(args.sql).expanduser().resolve(),
        cfg=cfg,
        log_file=Path(args.log).expanduser().resolve() if args.log else None,
        label=args.label,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["status"] in {"ok", "skipped"} else 1)


if __name__ == "__main__":
    main()
