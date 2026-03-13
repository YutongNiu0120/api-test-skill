## Postman Collection 规范（v2.1）

### 顶层鉴权
在 collection 根节点设置：
- auth.type = bearer
- bearer.token = {{token}}
- collection.info.name 固定取配置 `postman.collection`
- 当前 Controller 产物要包装成一个顶层 folder，folder 名建议使用输出目录名 `<ControllerName>_<YYYYMMDD_HHMMSS>`，并挂到该 collection 下

URL 前缀变量使用规则：
- request 的 `url.raw` 写成 `{{<postman.url_prefix_var>}}/v1/...`
- 若已知 Postman 中存在同名 collection variable 且值非空，更新 collection 时优先保留旧值
- 若不存在旧值，且 `postman.url_prefix_value` 非空，可将其作为首次生成的默认值
- 若两者都没有，可只保留变量占位，不强制写默认值

子级 request 不写 auth/header，默认继承。

### URL 结构必须完整
为了避免“导入后请求行为空”，不要只写 url.raw。建议同时写：
- url.raw
- url.host（可省略，仅 raw 也能用；但建议填充 path + variable）
- url.path（数组）
- url.variable（path 变量）

### Path 变量语法
- Spring：/orders/{orderId}
- Postman：/orders/:orderId

并在 url.variable 里提供默认值，便于直接运行。

### URL 前缀语法
- `url.raw` 应写为 `{{<postman.url_prefix_var>}}/v1/...`
- `<postman.url_prefix_var>` 与其默认值来自配置文件 `api-test.yml`

### 断言脚本
- 每个 request 都应包含 `event.listen = "test"` 的断言脚本
- 断言脚本必须只读，不得修改 environment / collection / globals
- 最少断言：HTTP 状态、响应体结构、业务成功/失败标志、关键字段存在性
- 列表/分页接口额外断言数组与分页结构；错误用例额外断言业务错误码或错误关键词
- 生成断言前，先推断响应契约：
  - 若 controller 显式返回 `ApiResponse<T>` / `Result<T>` / 其他 Result 类，则按显式 wrapper 生成断言
  - 若 controller 返回普通对象，但存在 `ResponseBodyAdvice` / `@ControllerAdvice` 自动包装，则按“wrapper + 原始 data”两层生成断言
  - 若接口返回下载流、二进制、`ResponseEntity<StreamingResponseBody>` 等非 JSON 响应，则只做 HTTP 状态、header、content-type / disposition 等断言，不强行解析 `data`
- `data` 断言可以且应该校验“是否符合预期”，不仅是非空：
  - 与 seed.sql 中准备的 id、单号、状态、时间点、数量、标签做比对
  - 与请求体回显字段做比对
  - 与 service 中可见的转换逻辑、枚举映射、默认值填充逻辑做比对
- `msg` 断言也可以做：
  - 若消息来自 `Assert.pass(..., "固定文案")`、固定异常文案、稳定枚举文案，可精确匹配或高置信度 contains
  - 若消息来自下游透传或动态拼接，则只断言关键词、正则或搭配错误码断言
- 推荐把“强断言”和“弱断言”混合使用：结构和稳定字段精确断言，易变文案做 contains/regex 断言。

推荐断言示例（按实际返回结构调整）：

```javascript
pm.test("HTTP status is expected", function () {
  pm.expect(pm.response.code).to.be.oneOf([200]);
});

const text = pm.response.text();
let body = null;
if (text) {
  try {
    body = pm.response.json();
  } catch (e) {
    pm.test("response is valid JSON", function () {
      throw e;
    });
  }
}

pm.test("business success", function () {
  pm.expect(body).to.be.an("object");
  pm.expect(body.code).to.eql(0);
});

pm.test("data matches seed", function () {
  pm.expect(body.data.orderNo).to.eql("ORD202603130001");
  pm.expect(body.data.relations).to.have.length(2);
  pm.expect(body.data.relations[0].status).to.eql("IN_PROGRESS");
});

pm.test("error message matches expectation", function () {
  pm.expect(body.msg).to.include("业务对象版本号不能为空");
});
```

### 两种文件 + 推送日志
- collection.import.json：顶层为 {info, item, auth}
- collection.api.json：顶层为 {"collection": {...}}（供 API 创建）
- push.log：推送日志（仅当启用 Postman 推送时）
