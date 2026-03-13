# API Test

[![Stars](https://img.shields.io/github/stars/YutongNiu0120/api-test-skill?style=social)](https://github.com/YutongNiu0120/api-test-skill/stargazers)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/codex-skill-green)](./SKILL.md)

English | [简体中文](./README.zh-CN.md)

`api-test` is an API self-test generator for Spring Boot projects.

It reads Controller source code and produces a reusable API test pack, with optional end-to-end execution.

Generated outputs include:
- Postman API test collections
- `seed.sql` and `cleanup.sql`
- coverage and evidence reports
- autotest execution reports

The goal is simple:

source code -> generated API tests -> automated execution -> readable report

## What Problem It Solves

Most backend API testing breaks down in predictable ways:

| Problem | Result |
| --- | --- |
| Postman requests are maintained by hand | They drift quickly |
| Only happy paths are tested | Business branch coverage stays weak |
| Test SQL is unsafe or ad hoc | Teams hesitate to automate |
| Test output is disconnected from source code | Root cause analysis is slow |

This project is designed to change that workflow into:

write controller -> generate API test pack -> run tests -> review report

## Core Features

### 1. Generate API test packs automatically

Generate from Spring Controller source:
- `seed.sql`
- `cleanup.sql`
- Postman collections
- request assertions

You do not need to manually maintain a growing list of Postman requests.

### 2. Cover real business branches

Generated cases are driven by source code logic, not only success paths.

They can target:
- parameter validation
- not found cases
- business conflicts
- branch-specific behavior

### 3. Run the full autotest flow

Optional autotest flow:

`seed.sql`
-> `postman collection run`
-> test report
-> `cleanup.sql`

This is usable both for local verification and CI-like execution.

### 4. Build API test evidence chains

The generated analysis can trace:

Controller
-> Service
-> Mapper
-> SQL
-> table

This makes it easier to see whether important logic is actually covered.

### 5. Use safer test data defaults

Generated test data uses deterministic negative IDs such as:
- `-10001`
- `-10002`

That reduces the chance of colliding with existing data.

## Workflow

Typical usage looks like this:

write controller
-> run `api-test`
-> generate API test pack
-> run autotest
-> read report

The generated package is also usable manually in Postman UI when you want to debug a failing API by hand.

## Security Design

This project is intentionally conservative about execution boundaries.

- Autotest only allows `sql/seed.sql` and `sql/cleanup.sql`.
- It does not execute arbitrary SQL files.
- It does not read existing database rows to synthesize test data.
- Tokens can be provided through environment variables instead of committed config.
- Generated Postman assertions are read-only and do not mutate Postman variables.
- Cleanup behavior is controlled by `autotest.always_cleanup`.

The point is to make automation usable without turning it into an unsafe shell around your database.

## Technical Implementation

Implementation stack:
- Codex skill definition in [SKILL.md](./SKILL.md)
- Python scripts for config bootstrap, SQL execution, autotest orchestration, and Postman push
- Postman CLI for collection execution
- MySQL for seed and cleanup execution

Runtime dependencies:
- Python 3.10+
- `PyYAML`
- `PyMySQL`
- Postman CLI
- MySQL

Python dependencies are listed in [requirements.txt](./requirements.txt).
Missing Python packages such as `PyYAML` and `PyMySQL` can be installed automatically when needed.

Main repository structure:
- [SKILL.md](./SKILL.md): skill workflow and rules
- [scripts](./scripts): bootstrap, SQL runner, autotest runner, Postman push
- [assets](./assets): config template and Postman skeleton files
- [references](./references): detailed rules and design notes

## Quick Start

Put the skill under your local Codex skills directory:

- `~/.codex/skills/api-test`

Recommended usage:

- When using it in a repo for the first time, invoke `api-test` on a target Spring Controller and let it bootstrap `api-test.yml` in the repo root.
- Review `api-test.yml` before running anything that touches MySQL or Postman CLI.
- For manual API verification, generate the test pack first and inspect:
  - `analysis/controller_report.json`
  - `postman/collection.import.json`
  - `sql/seed.sql`
  - `sql/cleanup.sql`
- For automated execution, enable `autotest.enabled=true` after the generated SQL and collection look correct.
- If the target APIs require authentication, provide the token through `API_TEST_TOKEN` or `POSTMAN_TOKEN`.
- When a run fails, keep the generated package and use Postman UI to reproduce and debug the failing request.
- When the workflow becomes stable, use the generated package as a repeatable local or CI-like regression entry point.

Typical first-run flow:

- Place the skill in `~/.codex/skills/api-test`
- Open your target Spring Boot repository with Codex
- Ask Codex to generate an API test pack for a specific controller with `$api-test`
- Let the skill create `api-test.yml`
- Fill in the database and Postman-related configuration
- Run generation again, then optionally enable autotest

If this project matches your workflow, star the repo and share it with backend teams that still rely on fragile manual API testing.
