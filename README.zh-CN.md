# API Test

[![Stars](https://img.shields.io/github/stars/YutongNiu0120/api-test-skill?style=social)](https://github.com/YutongNiu0120/api-test-skill/stargazers)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Skill](https://img.shields.io/badge/codex-skill-green)](./SKILL.md)

[English](./README.md) | 简体中文

`api-test` 是一个面向 Spring Boot 项目的 API 自测生成器。

它可以直接读取 Controller 源码，自动产出一整套可复用的 API 测试包，并支持按需执行自动测试闭环。

生成内容包括：
- Postman API 测试集合
- `seed.sql` 和 `cleanup.sql`
- 覆盖率与证据链报告
- 自动测试执行报告

这个项目的目标很直接：

源码 -> 自动生成 API 测试 -> 自动执行 -> 输出报告

## 解决什么问题

大部分后端团队的 API 测试都会遇到这些问题：

| 问题 | 结果 |
| --- | --- |
| Postman 请求手工维护 | 很快失效 |
| 只测 happy path | 业务分支覆盖不足 |
| 测试 SQL 不安全或太随意 | 不敢真正自动化 |
| 测试结果和源码脱节 | 问题定位很慢 |

这个项目希望把流程改造成：

写 Controller -> 生成 API 自测包 -> 执行测试 -> 查看报告

## 核心功能

### 1. 自动生成 API 自测包

从 Spring Controller 源码直接生成：
- `seed.sql`
- `cleanup.sql`
- Postman Collection
- 请求断言脚本

不需要再手工维护越来越多的 Postman 请求。

### 2. 覆盖真实业务分支

生成的测试用例不是只覆盖成功路径，而是尽量根据源码逻辑覆盖真实分支。

包括：
- 参数校验
- 资源不存在
- 业务冲突
- 分支条件路径

### 3. 自动执行完整测试链路

支持可选自动测试流程：

`seed.sql`
-> `postman collection run`
-> 测试报告
-> `cleanup.sql`

既可以本地运行，也适合接入类 CI 的自动执行流程。

### 4. 生成 API 测试证据链

生成的分析结果可以追溯到：

Controller
-> Service
-> Mapper
-> SQL
-> table

便于确认测试是否真的覆盖到了关键逻辑。

### 5. 更安全的测试数据策略

默认使用固定负数 ID 生成测试数据，例如：
- `-10001`
- `-10002`

这样更不容易和现有数据冲突。

## 工作流程

典型使用方式如下：

写 Controller
-> 运行 `api-test`
-> 生成 API 测试包
-> 执行自动测试
-> 查看报告

如果某个接口失败，生成出来的测试包也可以直接在 Postman UI 里继续手工排查。

## 安全设计

这个项目对执行边界是保守设计的。

- 自动执行只允许运行 `sql/seed.sql` 和 `sql/cleanup.sql`
- 不允许执行其它任意 SQL 文件
- 不读取现有数据库数据来合成测试数据
- token 可以通过环境变量提供，不要求写入仓库
- 生成的 Postman 断言是只读的，不会修改 Postman 变量
- cleanup 是否执行由 `autotest.always_cleanup` 控制

目标不是“为了自动化什么都能跑”，而是在可用的前提下尽量保证安全边界清晰。

## 技术实现

实现组成：
- [SKILL.md](./SKILL.md) 定义 Skill 工作流
- Python 脚本负责配置初始化、SQL 执行、自动测试编排、Postman 推送
- Postman CLI 负责执行生成出的 Collection
- MySQL 负责 seed 和 cleanup 执行

运行依赖：
- Python 3.10+
- `PyYAML`
- `PyMySQL`
- Postman CLI
- MySQL

Python 依赖见 [requirements.txt](./requirements.txt)。
缺失的 Python 依赖（如 `PyYAML`、`PyMySQL`）可在执行时按需自动安装。

仓库主要结构：
- [SKILL.md](./SKILL.md)：Skill 规则与流程
- [scripts](./scripts)：初始化、SQL 执行、自动测试、Postman 推送
- [assets](./assets)：配置模板和 Postman 骨架文件
- [references](./references)：详细规则与设计说明

## 快速开始

把 skill 放到 Codex skills 目录：

- `~/.codex/skills/api-test`

推荐流程：

1. 用 Codex 打开目标 Spring Boot 仓库
2. 让 Codex 用 `$api-test` 为某个 Controller 生成 API 自测包
3. 让 skill 在仓库根目录自动创建 `api-test.yml`
4. 补齐数据库、Postman、URL 前缀等配置
5. 再次执行生成，优先检查这些产物：
   - `analysis/controller_report.json`
   - `postman/collection.import.json`
   - `sql/seed.sql`
   - `sql/cleanup.sql`
6. 确认生成结果符合预期后，再把 `autotest.enabled` 改成 `true`
7. 如果接口依赖鉴权 token，通过环境变量 `API_TEST_TOKEN` 或 `POSTMAN_TOKEN` 提供
8. 如果某次执行失败，保留生成出来的测试包，用 Postman UI 继续复现和排查失败接口
9. 当流程稳定后，可以把这套生成物作为本地或类 CI 的可重复回归入口

如果这个项目正好解决了你的 API 自测问题，欢迎点个 Star，也欢迎分享给还在手工维护 Postman 的后端团队。
