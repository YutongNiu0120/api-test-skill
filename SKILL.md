---
name: api-test
description: 为指定 Spring Controller 生成后端 API 自测包（seed.sql、cleanup.sql、带只读断言的 Postman Collection、覆盖/证据报告），并可选通过 MCP 推送到 Postman Workspace，或通过 Python + MySQL + Postman CLI 执行自动测试。支持推断统一返回包装（如 ApiResponse）、按真实业务分支提升覆盖率、保留已有 URL 前缀变量值，并把当前 Controller 结果作为 folder 挂到指定 Collection 下。适用于“生成 XxxController 接口测试用例 / 自测包 / Postman 用例 / seed.sql / 断言脚本 / 覆盖报告 / 自动测试”的需求。
---

## 你要完成什么

当用户要求“为某个 Controller 生成测试用例/自测用例/Postman 用例（并尽可能生成 seed.sql）”时，执行本 skill。

输出一个新目录：`<ControllerName>_<YYYYMMDD_HHMMSS>/`，其中包含：

- `analysis/controller_report.json`：接口清单、每个接口的表依赖、证据链、已覆盖分支/未覆盖分支与原因
- `analysis/index.json`：可选调试产物。仅当跨模块符号解析困难、证据链不稳定、或用户明确要求排障索引时再生成
- `sql/seed.sql`、`sql/cleanup.sql`：不读取现有 DB 的合成数据（best-effort）
- `postman/collection.import.json`：用于客户端“导入”，且每个 request 都要带只读断言脚本
- `postman/collection.api.json`：用于 Postman API “创建/更新 Collection”（外层包一层 `{collection: ...}`）
- `postman/push.log`：推送日志（仅当启用 Postman 推送时）
- `README.md`：执行说明与变量清单

> 重要：充分发挥 Codex 的代码理解与生成能力。优先直接阅读项目结构、注解、XML、DDL 进行推导；脚本仅是辅助手段。

## 设计原则

- 友好：缺配置时自动初始化模板并用清晰中文提示用户该填哪些字段。
- 极简：配置字段保持最小化；Postman API key 仅支持明文配置（不再分 env/file）。
- 能力优先：不要给 Codex 额外限制，直接基于项目源代码推导数据模型、接口入参和造数策略；索引不全时也要给出 best-effort 产物与证据。
- 覆盖优先：生成用例时优先覆盖真实业务分支与校验分支，而不是满足最低数量。
- 保守覆写：允许给出 `url_prefix_value` 作为首次导入/首次推送的默认值，但若 Postman 里已存在同名变量值，优先保留已有值，不用本地配置覆盖。
- 透明：所有推送调用记录到 `postman/push.log`，包含完整未脱敏的请求与响应，便于排查。
- 交互：与用户的所有对话与提示统一使用中文。

### 性能优化（加速分析）
- 优先用 `rg`/`fd`/`dir` 限定目录扫描 Controller 所在模块，跳过 `node_modules`、`build`、`target`、`dist`、`.git` 等大目录。
- 先解析 Controller/Service/Mapper 的注解与方法签名，再按依赖关系定向打开少量 PO/XML/DDL，避免全仓递归。
- 遇到超大 XML 或 DDL 时，按 statement/表名关键字 `SELECT|UPDATE|INSERT INTO <table>` 定位，再局部截取。
- 在生成索引时做去重缓存：同一文件只解析一次；跨 endpoint 重用解析结果。
- 如果仓库包含现成的接口文档/Swagger 定义，先读取它们快速获取路径，再反查实现，减少盲扫。
- **可达优先探索（默认）**：默认从目标 Controller 出发，优先解析“可达子图”，但 **BFS 只是推荐启发式，不再是硬约束**。允许根据代码形态混用 BFS / DFS / 关键字反查 / 符号跳转 / XML namespace 反查 / DDL 反查等策略，只要遵守“先局部、后扩圈”的原则。只有当局部探索无法解释接口依赖、真实分支或数据来源时，才扩大到模块级甚至项目级扫描。

## 关键约束（必须遵守）

1) **禁止读取现有数据库数据**：不得通过 SELECT 等方式窥探已有数据。只能基于代码可见结构（PO/注解/XML/DDL）推导并合成 INSERT。
2) **禁止执行白名单之外的 SQL**：自动执行模式下只允许执行当前输出目录里的 `sql/seed.sql` 和 `sql/cleanup.sql`，禁止执行任何其它 SQL 文件。
3) **敏感信息保护**：除调试用的 `postman/push.log` 外，其它输出/日志不要回显 Postman API key；配置文件如含密钥，提醒加入 `.gitignore`。`postman/push.log` 用于排障，可记录未脱敏的完整 HTTP 请求与响应（含 headers/body），便于复现。
4) **Postman 推送按 Collection + Controller Folder 管理**：`postman.collection` 为必填，表示目标 Collection 名称；当前生成结果目录名作为一个 controller folder 挂到该 Collection 下。若 workspace 已有该 Collection，优先读取旧集合，保留同名 URL 前缀变量已有值，并只替换/新增当前 controller folder，保留其它 folder。若目标 Collection 不存在，再创建新 Collection。

## 配置文件

在仓库根目录查找 `api-test.yml`：

- 不存在：自动从 `assets/api-test.template.yml` 复制一份到仓库根目录，并把 `api-test.yml` 追加到仓库根目录 `.gitignore`；随后停止执行，提示用户补齐配置后重试。
- 存在但字段缺失：先按模板自动补全缺失字段写回同一文件；随后按当前执行场景做必填校验：
  - 生成/导出：至少要求 `generation.output_dir`、`postman.collection`、`postman.url_prefix_var`
  - 推送 Postman：额外要求 `postman.push_enabled=true` 且 `postman.workspace_id`、`postman.api_key`
  - 自动执行：额外要求 `autotest.enabled=true` 且 `database.*`、`postman.url_prefix_value`
- 每次生成前都要重新读取 `api-test.yml` 的当前内容，不得继续使用内存缓存或旧模板默认值；补全后的新值应立即参与本次执行。

配置项用于控制：是否自动执行、造数策略、数据库连接、是否推送 Postman、目标 Collection 名称、workspace、API key、URL 前缀变量名，以及可选的默认 URL 前缀值。

最小配置示例：

```yaml
autotest:
  enabled: false
  always_cleanup: false

generation:
  sql_dialect: mysql
  output_dir: .api-test
  seed_id_base: -9000000
  seed_id_step: 1
  customer: demo-customer
  current_user: SYSTEM

database:
  type: mysql
  host: 127.0.0.1
  port: 3306
  database: app_db
  username: root
  password: your-password
  charset: utf8mb4

postman:
  push_enabled: false
  collection: api-test-collection
  workspace_id: xxxxx
  api_key: xxxxx
  url_prefix_var: api-base-url
  url_prefix_value: ""
```

## 生成规则（对齐需求）

### 1) URL 规则

- **URL 前缀**：请求 URL 固定写成 `{{<postman.url_prefix_var>}} + Controller mapping`。`postman.url_prefix_var` 必填；`postman.url_prefix_value` 仅是可选的默认基地址（可含 context-path，且**不要带结尾 `/`**），用于“首次导入/首次推送且 Postman 中尚无同名变量值”的场景。
- **路径部分**：仅拼接 Controller 可见 mapping（class-level + method-level），不考虑 context-path。
- **Path 参数**：将 Spring 的 `{orderId}` 形式统一转换为 Postman 的 `:orderId` 形式。
- 必须同时填充 `url.raw` 与结构化字段 `url.path`/`url.variable`（避免导入后请求行为空）。
- 变量使用约束：`url.raw` 只允许配置中的 URL 前缀变量与 `:path` 形式占位；`url.variable` 的 value 必须写真实值（来自 seed 数据），禁止再套二次变量如 `{{orderId_seed}}`。
- Collection 顶层对 URL 前缀变量采用“**保留旧值优先，配置值兜底**”：
  1. 若推送目标中已存在同名 collection variable 且值非空，优先保留该值；
  2. 否则若 `postman.url_prefix_value` 非空，则可将其写入生成后的 collection variable；
  3. 否则允许不写该 variable 的 value，只保留 `{{<postman.url_prefix_var>}}` 占位，并在 README 提示用户使用现有 environment/global variable 或手工补值。

示例：

- 原始：`/v1/orders/{orderId}/tasks/{taskId}`
- Postman：`{{api-base-url}}/v1/orders/:orderId/tasks/:taskId`
- `url.variable`: `[{key:"orderId", value:"1"}, {key:"taskId", value:"1"}]`

### 2) 鉴权、变量与断言

- 在 **Collection 顶层**设置 bearer token：变量 `{{token}}`。
- Collection 名称固定取配置 `postman.collection`。
- 允许在 **Collection 顶层**写入 URL 前缀变量：变量名来自 `postman.url_prefix_var`；变量值遵循“保留旧值优先，配置值兜底”的规则。
- 子 folder / request **不写 Authorization header，也不写 auth**（继承父级即可）。
- 生成断言前，必须先推断接口的**响应契约**（response contract），至少判断：
  - 是否存在统一返回包装（如 `ApiResponse<T>` / `Result<T>` / 其他项目自定义 Result）；
  - 该包装是 controller 显式返回的，还是由 `ResponseBodyAdvice` / `@ControllerAdvice` / 统一响应处理器隐式包裹的；
  - 成功体和错误体的关键字段名（如 `code` / `msg` / `message` / `success` / `data`）；
  - 是否属于非 JSON 响应（下载流、二进制、文件、纯文本），这类接口不要套用普通 JSON 断言模板。
- 响应契约的推断顺序建议为：
  1. 读取 controller 方法返回类型；
  2. 检查 `ResponseBodyAdvice`、`@ControllerAdvice`、统一异常处理；
  3. 检查常见 Result 类的字段与工厂方法；
  4. 检查 Swagger/OpenAPI/已有测试或客户端代码中的返回样例；
  5. 若仍不确定，在 `controller_report.json` 标记低置信度并采用保守断言。
- 每个 request **必须带 post-response 断言脚本**，且断言脚本必须是只读的。最少包含：
  - HTTP 状态码断言；
  - 响应体可解析性断言（JSON / 文本 / 空体按接口实际返回判断）；
  - 成功用例的业务成功断言（如统一 `code` / `success` / `message` / 关键字段存在性）；
  - 失败用例的业务失败断言（如 HTTP 状态、业务 code、错误信息关键词、冲突/不存在/校验失败等）；
- 列表/分页接口的结构断言（数组、分页字段、total/page/pageSize/data/list 等实际结构）；
- 创建/更新类接口的结果断言（返回 id、状态变化、关键字段回显等，按接口真实返回推导）。
- 若接口存在统一包装（例如 `ApiResponse<T>`），成功用例的断言应同时覆盖“wrapper + data”两层：
  - wrapper 层：例如 `code == successCode`、`msg` 为成功语义、`data` 字段存在；
  - data 层：根据返回 VO、分页对象、列表元素、seed 数据、service 内部转换逻辑，校验关键字段、关键枚举值、关键 id、列表长度、分页元信息、状态流转结果是否符合预期。
- 成功用例的 `data` 断言不应只判断“非空”。应尽量做到：
  - 创建接口：断言返回 id / 单号 / 关系数量 / 关键状态与 seed、请求体、领域规则一致；
  - 详情接口：断言关键业务字段与 seed 一致；
  - 列表接口：断言总数、分页参数、首条或指定记录的关键字段；
  - 下拉/枚举接口：断言候选值集合或标签映射；
  - 无返回体或 `data = null` 的成功接口：明确断言 `data` 为空或不存在，而不是跳过。
- 失败用例的 `msg` 断言可以做，而且应该做，但要区分强弱：
  - **强断言**：若错误消息来自代码中的字面量字符串、`Assert.pass(..., "xxx")`、固定枚举文案、固定 `String.format` 模板，可断言精确值或高置信度的 contains；
  - **弱断言**：若错误消息来自下游透传、国际化、动态拼接、异常包装链，优先断言关键词/正则/错误码，不要求整句精确匹配；
  - 若能确定错误码稳定，优先同时断言 `code` 与 `msg`。
- 当项目通过 `ResponseBodyAdvice` 自动把普通对象包装成 `ApiResponse.ok(body)` 时，skill 应把 controller 的原始返回类型视为 `data` 契约，把 `ApiResponse` 视为外层 wrapper 契约。
- 断言要尽量稳健，优先校验“结构、状态、业务码、关键字段”，避免对易变的整句文案做脆弱的全量精确匹配。
- 禁止在任何请求/测试脚本中写入或清理 Postman 变量：不得使用 `pm.environment.set` / `pm.collectionVariables.set` / `pm.globals.set` / unset / clear 等修改变量的 API。允许只读取 `pm.response.*`、`pm.request.*`、`pm.variables.get(...)` 等，不得产生任何变量写入副作用。除配置中的 URL 前缀变量与 `{{token}}` 外，请求路径参数与请求体字段一律使用真实值（来自 seed 数据）。
- 请求体中所有日期时间字段的示例值统一使用字符串格式 `yyyy-MM-dd HH:mm:ss`，例如 `2026-01-02 09:00:00`，不要输出 `2026-01-02T09:00:00` 这种 ISO 带 T 格式。

### 3) Folder 命名规则

当前 Controller 的全部测试用例要先包成一个 controller folder，folder 名默认使用本次输出目录名 `<ControllerName>_<YYYYMMDD_HHMMSS>`，并挂在配置指定的 `postman.collection` 下面。

每个 endpoint 生成一个文件夹（folder/item group），**统一使用方法名**（create/update/...），避免中文或特殊字符导入 Postman 出现问号。

请求（request item）的用例设计要由 Codex 依据 Controller/Service/Validator/Assert/Enum/状态机代码的真实分支自动推导，而不是固定写 `happy`/`invalid`/`forbidden`。**目标不是“凑最少几条用例”，而是尽量覆盖接口的可观察分支。**

至少覆盖：
- 正常通过路径（至少 1 条），命名可用 `happy` 或更具语义的业务名。
- 输入校验/缺字段/格式错误分支：针对真实校验规则逐条枚举，命名包含 `invalid` 但补充具体缺陷点。
- 资源不存在/状态不符/业务冲突等业务错误分支：按代码条件生成，命名例如 `not_found`、`conflict_<rule>`。
- 若接口内部根据枚举、状态、类型、开关、角色、来源系统、布尔标志等存在分支，优先做到“**每个可观察分支至少 1 条用例**”；若分支过多无法完全穷举，要在 `analysis/controller_report.json` 中列出未覆盖分支及原因。
> 鉴权失败用例不自动生成；若需要 forbidden/unauthorized 场景，请手动将 Authorization 的 Bearer 换成 `token_outsider`。
针对查询/筛选/分页类接口，要在“覆盖度”和“性能”间取平衡：**枚举值必须全覆盖**，组合场景用代表性覆盖避免爆炸。
- 枚举字段（如 `filterField` 等）：为每个枚举值至少生成 1 条请求，保证枚举全覆盖；多枚举组合用“单维轮换+少量代表性交叉”，不做全笛卡尔。
- 列表筛选字段（如 `time`、`products`、`abnormalLevels`、`createUsers`、`statusList` 等）：每个字段至少生成 “空列表” 和 “单值” 两档；对主要字段再给一条“多值”用例（覆盖所有可选值或典型多值）。跨字段组合给出 2~3 条代表性场景：①全部为空；②单字段有值；③多字段同时有值（可含分页）；保证所有可选值在这些用例中至少出现一次。
- 时间列表字段：使用两个时间点组成区间，格式 `yyyy-MM-dd HH:mm:ss`（如 `2026-01-02 09:00:00`,`2026-01-03 18:00:00`），并提供空列表/单点/区间三档。
- 分页字段：覆盖首页、后续页、最大页大小各 1 条；与筛选条件交叉挑选 1~2 条代表性组合。
所有生成的用例都要与 `seed.sql` 中的数据一一对应：测试用例引用的 id/状态/时间等必须在 SQL 里准备好，避免“用例找不到数据”。
`analysis/controller_report.json` 中必须给出每个 endpoint 的覆盖摘要：至少包含 `response_contract`、`covered_branches`、`uncovered_branches`、`coverage_notes` 四类信息。

### 4) “自由探索 + 证据链”表发现策略（不依赖 DDD）

不要假设严格 DDD。以项目结构探索为准，并用“可达优先 + 证据链”驱动：

- 可达优先探索：先从目标 Controller 出发，按实际需要解析其依赖的 Service/Repo/Mapper、XML、PO/Entity、Enum、Validator、AOP、配置类等。允许从“正向调用链”与“反向证据定位”两侧夹逼，不要求必须按 BFS 实现。
- 索引产物最小化：默认只输出足够支撑证据链和覆盖说明的 `controller_report.json`；`analysis/index.json` 仅在需要调试或不确定性较高时输出，避免为了中间文件而中间文件。
- 证据链生成：沿 “Controller → Service → Mapper → XML(statement) → SQL(table)” 形成证据链。`tables_required`：能落到具体 SQL statement 并明确引用该表（强证据）；`tables_possible`：只能在 Java 侧看到潜在依赖但无法落到具体 SQL / 或分支不确定（弱证据），必须附“为什么只能是 possible”的理由。

### 5) seed.sql 的生成原则（best-effort）

- 以“覆盖所有生成的用例”为目标生成最小合成数据集：哪条用例用到哪个数据点必须在 SQL 中体现（id、状态、日期等），并在 README 的专门小节写明“本次 seed 覆盖哪些用例/关键 id/状态/时间点列表”。
- 为每条合成数据覆盖 PO/实体定义的**全部字段**：结合注解、DDL 默认值、业务语义推导取值，特别是 `NOT NULL`/有默认值的字段不能留空或写成 `NULL`，必要时使用合理默认（0/false/空串/当前时间等），避免插入失败。
- 若 PO/实体存在 `customer` 字段：统一按配置 `generation.customer` 赋值（没有配置时提醒补充，临时可用 `demo-customer`），并保持 SQL 与 Postman 请求体中的该字段一致。
- 若 PO/实体存在用户名/用户 ID/创建人/修改人等字段（如 `userId`、`createdBy`、`updatedBy`、`operator` 等）：优先按配置 `generation.current_user` 填充，保持 SQL 与 Postman 请求体一致。
- 日期时间字段（Java `LocalDateTime`/`Date` 等）统一用字符串格式 `yyyy-MM-dd HH:mm:ss` 生成，避免 Jackson 解析失败；`url.variable`、请求体、seed.sql 中保持一致。
- 若只能确定“可能表”但缺关键字段/约束：可以生成空壳或跳过，并在 README 说明原因。
- 同时生成 `cleanup.sql`（建议按主键或统一前缀精确清理，保证幂等）。

### 6) 输出两份 Postman JSON（必须）

- `postman/collection.import.json`：顶层是 `{ info, item, auth? }`，用于客户端导入。
- `postman/collection.api.json`：顶层是 `{ "collection": { ... } }`，用于 Postman API 创建集合。
- 两份 JSON 中的每个 request 都必须包含请求级断言脚本（`event.listen = "test"`），且断言脚本不得修改变量。
- Postman 请求体里所有时间字段也必须使用 `yyyy-MM-dd HH:mm:ss` 格式，示例值与 seed 数据保持一致。

## 自动执行（可选）

- 当 `autotest.enabled=true` 时，允许使用 `scripts/autotest_runner.py` 执行自动测试闭环。
- 自动执行顺序固定为：`seed.sql -> Postman CLI -> 报告 -> cleanup.sql(按策略)`。
- 自动执行时：
  - 只允许执行输出目录中的 `sql/seed.sql` 和 `sql/cleanup.sql`
  - `seed.sql` 失败则立即停止，Postman CLI 与 cleanup 都不执行
  - `autotest.always_cleanup=true` 时，无论 Postman CLI 成功还是失败，都会尝试执行 `cleanup.sql`
  - `autotest.always_cleanup=false` 时，只有整批 Postman CLI 执行成功才执行 `cleanup.sql`
- 自动执行的数据库连接由 `database.*` 提供，当前仅支持 MySQL，使用 Python 脚本通过 `PyMySQL` 直连执行。
- 自动执行的 Postman 命令固定为 `postman collection run`，并生成 `report/postman-run.json`、`report/postman-run.junit.xml`、`report/postman-run.html`、`report/run-summary.json`。
- 自动执行时，skill 会把 `postman.url_prefix_value` 作为 CLI 变量写入 `{{postman.url_prefix_var}}`。若需要鉴权 token，优先读取环境变量 `API_TEST_TOKEN`，其次读取 `POSTMAN_TOKEN`，并注入到 `{{token}}`；若都不存在，不阻止执行，但鉴权接口可能失败。
- 若缺少 `pyyaml` 或 `PyMySQL`，允许脚本自动执行 `pip install` 安装最小依赖。

## 推送 Postman（可选，通过 MCP）

- 当 `postman.push_enabled=true` 且配置齐全时：通过 MCP 执行推送。
- 目标 Collection 名固定取 `postman.collection`。当前输出目录名作为 controller folder，若 workspace 已有该 collection，则优先原地更新其内容，只替换同名 controller folder，并保留其它 folder。
- 更新前读取旧 collection，若其中已存在 `postman.url_prefix_var` 对应的非空值，则保留该值，不用本地 `postman.url_prefix_value` 覆盖。
- 若目标 collection 不存在，则创建一个新 collection，并把当前 controller folder 挂进去。
- `postman/push.log` 需记录本次推送的原始 HTTP 请求与响应（含 headers/body，包含敏感信息），不做脱敏，方便 debug。

你可以：
- 直接用 Codex（或 MCP）的 HTTP 能力调用 Postman API；或
- 运行 `scripts/postman_push.py`（示例脚本）完成推送。

详见 `references/04_MCP_推送_Postman_示例.md`。

## 失败兜底

若无法生成 seed.sql：仍必须生成 Postman Collection，并在 README 说明“需要手工准备数据”与“表推导失败的证据链”。

## 执行流程（必须按顺序）

1) **先检查配置文件**：在仓库根目录查找 `api-test.yml`  
   - 如果不存在：自动复制模板到该路径、把 `api-test.yml` 追加到仓库根目录 `.gitignore`，并停止执行，提示用户补齐配置后重试。
   - 如果存在：自动补全缺失字段写回；随后做必填字段校验，缺少必填或仍为占位默认值则列出并停止；仅缺可选字段可继续并提示使用了默认值。

2) **只有在配置文件存在且必填校验通过后，才开始生成产物**。

3) **输出目录固定在 `.api-test/` 下**：创建 `.api-test/<ControllerName>_<YYYYMMDD_HHMMSS>/`，不要把输出直接落在仓库根目录（除非用户在配置里显式改动）。

4) **自动执行仅使用白名单 SQL**：如果进入自动执行模式，只允许运行当前输出目录下的 `sql/seed.sql` 与 `sql/cleanup.sql`。

5) **合成数据 ID 避免碰撞**：默认使用“负数 ID”或足够大的 ID（推荐负数），并在 README 中记录 ID 策略与取值范围。
