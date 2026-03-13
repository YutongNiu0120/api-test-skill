# API Test

[![Stars](https://img.shields.io/github/stars/YutongNiu0120/api-test-skill?style=social)](https://github.com/YutongNiu0120/api-test-skill/stargazers)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/codex-skill-green)](./SKILL.md)

English | [简体中文](./README.zh-CN.md)

`api-test` is a Codex skill for generating Spring Controller API test packs and optionally running them end to end.

It can generate:
- `seed.sql` and `cleanup.sql`
- Postman collections with read-only assertions
- coverage and evidence reports
- optional Postman Workspace push payloads
- optional autotest execution reports with Python + MySQL + Postman CLI

## Why This Project

Most backend teams can generate Postman collections. Fewer can generate collections that are:
- traceable back to Controller, Service, Mapper, XML, and table evidence
- designed for realistic business-branch coverage instead of shallow happy paths
- safe enough to run with automated SQL and cleanup boundaries
- ready for both manual debugging in Postman UI and scripted execution in CI-like flows

This project focuses on those gaps.

## Key Features

- Generate controller-scoped API test packs from source code instead of hand-written request lists.
- Infer response wrappers such as `ApiResponse<T>` and generate assertions accordingly.
- Build seed and cleanup SQL with deterministic negative IDs for safer test data isolation.
- Push generated controller folders into a named Postman collection instead of overwriting the whole collection.
- Support optional autotest flow: `seed.sql -> Postman CLI -> report -> cleanup.sql`.
- Auto-bootstrap `api-test.yml` into the target repo root and append it to `.gitignore`.

## Security Advantages

- No arbitrary SQL execution. Autotest only allows `sql/seed.sql` and `sql/cleanup.sql`.
- No reading from existing database rows to synthesize test data.
- Configuration files are automatically added to `.gitignore` when bootstrapped.
- Tokens for CLI execution can come from environment variables instead of being committed.
- Generated Postman assertions are read-only and do not mutate Postman variables.
- Cleanup is policy-controlled through `autotest.always_cleanup`, which helps balance safety and debugging convenience.

## Dependencies

Runtime dependencies:
- Python 3.10+
- `PyYAML`
- `PyMySQL`
- Postman CLI
- MySQL

Bundled Python dependencies are listed in [requirements.txt](./requirements.txt).

Optional external tools:
- GitHub CLI, if you want to create/push the public repo from the terminal

## Quick Start

1. Install Python dependencies:

```bash
pip install -r requirements.txt
```

2. Put the skill under your local Codex skills directory, or copy this repo as a reusable template.

3. Let the skill bootstrap `api-test.yml` in your target project root.

4. Generate the test pack for a target Spring Controller.

5. Optionally run autotest:

```bash
python scripts/autotest_runner.py --config api-test.yml --out .api-test/<ControllerName>_<timestamp>
```

## Default Workflow

- Generate the test pack from the target controller.
- Review `analysis/controller_report.json`.
- Execute `seed.sql` and run the generated Postman collection.
- Read `report/run-summary.json`.
- Decide whether to keep data for debugging or cleanup automatically.

## Repository Structure

- [SKILL.md](./SKILL.md): the actual skill definition and workflow
- [assets](./assets): config templates and collection skeletons
- [scripts](./scripts): config bootstrap, SQL runner, autotest runner, Postman push
- [references](./references): deeper rules and design notes
- [agents/openai.yaml](./agents/openai.yaml): UI-facing skill metadata

## Why Star This Repo

- It turns API self-testing from ad hoc manual work into a reusable, auditable workflow.
- It is opinionated about safety without becoming heavy or slow.
- It is practical for real Spring + MyBatis codebases, not just toy demos.

If this helps your team ship safer backend changes faster, star the repo and share it.
