# API Test

[![Stars](https://img.shields.io/github/stars/YutongNiu0120/api-test-skill?style=social)](https://github.com/YutongNiu0120/api-test-skill/stargazers)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/codex-skill-green)](./SKILL.md)

[English](./README.md) | 简体中文

`api-test` 是一个面向 Spring Controller 的 Codex Skill，用来生成后端 API 自测包，并支持按需执行自动测试闭环。

它可以生成：
- `seed.sql` 和 `cleanup.sql`
- 带只读断言的 Postman Collection
- 覆盖率与证据链分析报告
- 可推送到 Postman Workspace 的集合载荷
- 基于 Python + MySQL + Postman CLI 的自动测试执行报告

## 这个项目解决什么问题

很多团队能生成 Postman 用例，但很少能同时做到：
- 用例能回溯到 Controller、Service、Mapper、XML、数据表证据链
- 覆盖真实业务分支，而不是只凑几个 happy path
- 自动执行时仍然控制住 SQL 边界和清理策略
- 既适合在 Postman UI 手工排查，也适合命令行自动回归

这个项目就是围绕这些问题设计的。

## 核心能力

- 从源码生成 controller 级 API 自测包，而不是人工维护一堆请求清单。
- 推断类似 `ApiResponse<T>` 的统一响应包装，并生成匹配的断言。
- 通过固定负数 ID 生成 seed / cleanup SQL，降低测试数据污染风险。
- 把当前 controller 的结果作为 folder 挂到指定 Postman Collection 下，而不是覆盖整个 Collection。
- 支持可选自动执行链路：`seed.sql -> Postman CLI -> report -> cleanup.sql`。
- 在目标仓库根目录自动初始化 `api-test.yml`，并自动加入 `.gitignore`。

## 安全性优势

- 不允许执行任意 SQL。自动执行只会运行 `sql/seed.sql` 和 `sql/cleanup.sql`。
- 不读取现有数据库数据来“猜”测试数据，避免误碰线上或共享环境数据。
- 初始化配置文件时会自动加入 `.gitignore`，避免明文配置误提交。
- CLI 执行 token 支持从环境变量读取，不要求硬编码到仓库里。
- 生成的 Postman 断言脚本是只读的，不会修改 Postman 变量。
- 是否自动清理完全由 `autotest.always_cleanup` 控制，便于在安全和排查之间做取舍。

## 项目依赖

运行依赖：
- Python 3.10+
- `PyYAML`
- `PyMySQL`
- Postman CLI
- MySQL

Python 依赖已经写在 [requirements.txt](./requirements.txt)。

可选工具：
- GitHub CLI，如果你希望直接用命令行创建和推送公开仓库

## 快速开始

1. 安装 Python 依赖：

```bash
pip install -r requirements.txt
```

2. 把这个仓库放到本地 Codex skills 目录，或者作为可复用模板使用。

3. 让 skill 在目标项目根目录自动初始化 `api-test.yml`。

4. 针对某个 Spring Controller 生成测试包。

5. 如需自动执行：

```bash
python scripts/autotest_runner.py --config api-test.yml --out .api-test/<ControllerName>_<timestamp>
```

## 默认工作流

- 从目标 Controller 生成测试包。
- 检查 `analysis/controller_report.json`。
- 执行 `seed.sql`，再运行生成出来的 Postman Collection。
- 查看 `report/run-summary.json`。
- 根据调试需要决定保留数据还是自动清理。

## 仓库结构

- [SKILL.md](./SKILL.md)：Skill 主定义和工作流程
- [assets](./assets)：配置模板和 Collection 骨架
- [scripts](./scripts)：配置初始化、SQL 执行、自动测试、Postman 推送
- [references](./references)：更细的规则和设计说明
- [agents/openai.yaml](./agents/openai.yaml)：技能列表和 UI 元数据

## 为什么值得 Star

- 它把 API 自测从零散手工动作，变成了可复用、可审计、可自动执行的流程。
- 它对安全边界有明确约束，不会为了“自动化”把执行面无限放大。
- 它更贴近真实的 Spring + MyBatis 项目，而不是只适合 Demo。

如果这个项目对你有帮助，欢迎点个 Star，也欢迎分享给有同样痛点的后端团队。
