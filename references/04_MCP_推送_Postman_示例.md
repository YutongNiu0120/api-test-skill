## MCP 推送 Postman 示例（可选）

本 skill 建议通过 MCP 执行推送，以保证“所有动作由 Codex 执行”。实现方式不强制。若缺少配置文件，先由 skill 自动生成模板（字段含 `postman.collection`、`postman.api_key`、`postman.workspace_id`、`postman.url_prefix_var`；`postman.url_prefix_value` 可选）。

### 方式 A：MCP 直接 HTTP 调用（推荐）
- 若目标 collection 不存在：POST `{api_base}/collections?workspace={workspace_id}` 创建配置指定的 collection
- 若目标 collection 已存在：优先 GET 旧 collection，保留已有 URL 前缀变量值，并将当前 Controller 对应 folder 合并到该 collection 后再 PUT `{api_base}/collections/{collection_uid}`
- Header: X-API-Key: (从环境变量读取，不回显)
- Body: postman/collection.api.json

### 方式 B：运行脚本（示例）
`scripts/postman_push.py` 提供一个最小推送器：
- 读取 `api-test.yml`
- 读取输出目录下的 `postman/collection.api.json`
- 调用 Postman API 创建目标 collection，或在已有 collection 下替换/新增当前 Controller folder
- 若已有同名 collection 且旧 collection 中存在与 `postman.url_prefix_var` 同名的非空变量值，则保留旧值
- 将返回的 uid/链接写入 README（如可得）

注意：`postman/push.log` 用于排障，允许记录完整请求与响应（含 API key）；其它产物不要回显 API key。
