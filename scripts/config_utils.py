#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared config helpers for the api-test skill."""
from __future__ import annotations

import copy
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

CONFIG_FILENAME = "api-test.yml"
TEMPLATE_FILENAME = "api-test.template.yml"
PLACEHOLDER_VALUES = {
    "",
    "xxxxx",
    "REPLACE_ME",
    "your-postman-workspace-id",
    "your-postman-api-key",
    "your-password",
}


class ConfigBootstrapRequired(RuntimeError):
    """Raised when the target repo config was created and needs user edits."""


def ensure_python_package(module_name: str, package_name: str | None = None) -> Any:
    """Import a module, installing the backing package on demand."""
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        package = package_name or module_name
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return importlib.import_module(module_name)


yaml = ensure_python_package("yaml", "pyyaml")


def template_path() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / TEMPLATE_FILENAME


def normalize_config_path(path_arg: str | None = None) -> Path:
    if path_arg:
        return Path(path_arg).expanduser().resolve()
    return (Path.cwd() / CONFIG_FILENAME).resolve()


def ensure_gitignore_entry(repo_root: Path, entry: str) -> None:
    gitignore_path = repo_root / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text(encoding="utf-8")
        lines = content.splitlines()
    else:
        content = ""
        lines = []

    if entry in lines:
        return

    with gitignore_path.open("a", encoding="utf-8") as handle:
        if content and not content.endswith("\n"):
            handle.write("\n")
        handle.write(f"{entry}\n")


def init_config_file(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(template_path().read_text(encoding="utf-8"), encoding="utf-8")
    ensure_gitignore_entry(config_path.parent, config_path.name)


def _merge_with_template(data: Any, template: Any) -> Tuple[Any, bool]:
    if isinstance(data, dict) and isinstance(template, dict):
        merged: Dict[str, Any] = {}
        changed = False
        for key, template_value in template.items():
            if key in data:
                merged_value, child_changed = _merge_with_template(data[key], template_value)
                merged[key] = merged_value
                changed = changed or child_changed
            else:
                merged[key] = copy.deepcopy(template_value)
                changed = True
        for key, value in data.items():
            if key not in template:
                merged[key] = value
        if list(data.keys()) != list(merged.keys()):
            changed = True
        return merged, changed

    if isinstance(data, list) and isinstance(template, list):
        return data, False

    return data, False


def write_yaml(path: Path, data: Dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )


def load_config(config_path: Path) -> Tuple[Dict[str, Any], bool]:
    if not config_path.exists():
        init_config_file(config_path)
        raise ConfigBootstrapRequired(
            f"已在仓库根目录生成 `{config_path.name}`，并追加到 `.gitignore`。"
            " 请先补齐配置后再重试。"
        )

    template_data = yaml.safe_load(template_path().read_text(encoding="utf-8")) or {}
    config_data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config_data, dict):
        raise SystemExit(f"配置文件格式错误：{config_path}")

    merged, changed = _merge_with_template(config_data, template_data)
    if changed:
        write_yaml(config_path, merged)
    return merged, changed


def get_value(data: Dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def find_missing_fields(data: Dict[str, Any], dotted_paths: Iterable[str]) -> List[str]:
    missing: List[str] = []
    for dotted_path in dotted_paths:
        value = get_value(data, dotted_path)
        if value is None:
            missing.append(dotted_path)
            continue
        if isinstance(value, str) and value.strip() in PLACEHOLDER_VALUES:
            missing.append(dotted_path)
    return missing
