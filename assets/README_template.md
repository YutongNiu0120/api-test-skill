# 后端自测包

本目录由 `api-test` skill 生成（默认输出在仓库根目录的 `.api-test/` 下）。

## 目录结构

- analysis/
  - index.json：项目索引（类/表/Mapper/XML 关系）
  - controller_report.json：接口清单与表依赖证据链
- sql/
  - seed.sql：合成插入脚本（best-effort，不读取现有 DB）
  - cleanup.sql：清理脚本（幂等）
- postman/
  - collection.import.json：导入 Postman 客户端用
  - collection.api.json：通过 Postman API 创建/更新目标 Collection 用（外层包 `collection`）
  - push.log：推送日志（启用推送时记录完整 HTTP 请求/响应，未脱敏，便于排查）
- report/
  - seed.log：自动执行 seed 日志
  - postman-run.log：Postman CLI 执行日志
  - postman-run.json / junit.xml / html：自动执行报告
  - run-summary.json：自动执行汇总结果
- 请求体中的日期时间字段示例值统一为 `yyyy-MM-dd HH:mm:ss` 格式（例如 `2026-01-02 09:00:00`），不要用带 `T` 的 ISO 格式。

## 使用步骤（建议）

1. （可选）执行 `sql/cleanup.sql` 清理旧数据
2. 执行 `sql/seed.sql` 插入合成数据
3. 在 Postman 导入 `postman/collection.import.json`
4. （可选）启用推送后查看 `postman/push.log`
5. （可选）开启 `autotest.enabled=true` 后运行 `scripts/autotest_runner.py --out <输出目录>`，查看 `report/` 下的执行结果
6. 在 Postman 确认目标 Collection 与变量：
   - Collection 名称：`{{配置中的 postman.collection}}`
   - 当前 Controller 会作为一个 folder 挂在该 Collection 下
   - `{{token}}`：鉴权 token
   - `{{配置中的 postman.url_prefix_var}}`：请求前缀。若当前 Workspace/Environment 已有同名变量，优先沿用已有值；`postman.url_prefix_value` 仅作为首次生成时的兜底默认值

> URL 规则：`{{配置中的 postman.url_prefix_var}} + Controller mapping`。若 `postman.url_prefix_value` 为空，请使用现有 environment/global variable，或在导入后手工补 collection variable。

## 说明

- 若 `seed.sql` 为空或不完整：请参考 `analysis/controller_report.json` 的证据链，手工补充数据或完善索引策略。
- `analysis/index.json` 不是必产物；只有在符号解析困难、证据链不稳定、或你明确要求排障索引时才会生成。
- Collection 中的 request 应包含只读断言脚本，用于校验 HTTP 状态、业务成功/失败结果和关键响应结构。
- 自动执行模式只允许执行 `sql/seed.sql` 和 `sql/cleanup.sql`，不会执行其它 SQL 文件。
- 自动执行时会优先读取环境变量 `API_TEST_TOKEN`，其次读取 `POSTMAN_TOKEN`，并作为 `{{token}}` 注入 Postman CLI；若未提供，鉴权接口可能失败。

## 生成前置条件

- 如果仓库根目录没有 `api-test.yml`，skill 会先复制模板并把 `api-test.yml` 追加到仓库根目录 `.gitignore`；
  请按需要填写 `autotest`、`database`、`postman` 等字段后再次执行。
