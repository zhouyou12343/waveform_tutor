# 本地 HTTP API

开发后端为 `http://127.0.0.1:8000`；浏览器通常通过 Vite 的同源 `/api` 代理访问。FastAPI 交互文档位于 `/docs`，OpenAPI 位于 `/openapi.json`。接口无账号认证，仅用于本机开发；不要暴露公网。

## 路由

| 方法与路径 | 请求 | 成功响应 |
| --- | --- | --- |
| `GET /api/health` | 无 | `status`、`ai_configured`、`requests`、`provider_http_attempts`、`ai_config_revision` |
| `GET /api/ai/config` | 无 | 脱敏模型配置，不含Key |
| `PUT /api/ai/config` | JSON：url、api_key必填，model、api_format可配置 | 脱敏配置与保存反馈；不会调用Provider |
| `DELETE /api/ai/config` | 无 | 清除网页保存的Key、关闭AI；返回脱敏状态 |
| `POST /api/demos/{name}` | 无 | Trace；name 仅 counter/fifo/handshake |
| `POST /api/traces` | multipart 字段 `file`，`.vcd` | Trace |
| `POST /api/traces/{trace_id}/sources` | multipart 字段 `file`，UTF-8 `.v`/`.sv` | Source |
| `POST /api/traces/{trace_id}/analysis` | AnalysisRequest JSON | 确定性分析 JSON |
| `POST /api/traces/{trace_id}/report` | AnalysisRequest JSON | `text/markdown`，附件名 `waveform-report.md` |
| `POST /api/traces/{trace_id}/explain` | ExplainRequest JSON | 经过校验的 Explanation |

这些成功响应默认状态码为 200。没有持久项目、查询全部 trace、单独 GET trace、删除 trace 或执行上传 RTL 的接口。trace ID 来自载入响应，最多保留四个，重启或淘汰后失效。

`requests` 是 AIService 逻辑调用计数，包含进入服务后被拒绝的调用；不是成功次数或提供商计费次数，内部重试不递增。`provider_http_attempts` 是内置适配器在 I/O 前预占的 HTTP 尝试次数，包括重试、超时、网络失败与取消；不保证 Provider 已收到或计费，不含无授权拒绝。两个计数均随实例/进程重启清零；测试替身的 HTTP 计数为 0。配置缺失或无效时 `ai_configured=false`，不影响离线服务；解释请求返回 503。health 不能替代真实提供商连通性检查。

## 网页模型配置（本机单用户）

PUT要求Content-Type: application/json。url是HTTPS Base URL（loopback可HTTP），也可为完整/responses或/chat/completions端点；完整端点优先决定api_format。api_key为必填秘密字符串，不在任何返回体中回显。model默认gpt-5.6-sol，api_format默认responses，另支持chat_completions。修改配置须重新提交Key，不支持读取旧Key。校验失败返回通用422，不把请求输入或Pydantic错误详情里的密钥回传。

GET/PUT/DELETE响应包含configured、base_url、model、api_format、has_key、source、saved_locally、revision、error及可选message；Cache-Control为no-store。保存只做配置格式处理和本地写入，不验证Provider身份、余额、模型可用性。请求中AI正在忙时，PUT/DELETE返回409；写入失败500，内容类型不符415。

`.waveform-tutor/ai-config.json`为Git忽略的本机明文配置，优先于环境；清除写disabled标记并关闭AI，不回退环境旧密钥。页面更新revision后重挂AI面板，旧回答和授权被清除。此接口无多用户隔离，不应公开部署。网页配置固定单次HTTP尝试，仍尊重AI_REQUEST_BUDGET/AI_TIMEOUT_SECONDS/AI_MAX_OUTPUT_TOKENS环境限制；重新保存重置实例计数。本增量按用户要求未执行新的测试/构建/扫描。

## Trace 与 Source

Trace 字段：`id`、`name`、`timescale`、`tick_fs`、`start`、`end`、`signals`、`sources`、`warnings`。

Signal 字段：`id`、`name`（完整层级名）、`scope`、`width`、`kind`、`events`。每条事件是 `{"time": 整数tick, "value": "01xz二进制字符串"}`。同时间戳可以有多条记录，文件记录顺序保留。

Source 为 `{"name": "文件名.sv", "content": "源码文本"}`。源文件每个最多 128 KiB，每个 trace 最多八个（含案例自带源码），拒绝同名文件。VCD 及其他约束见[限制](limitations.md)。

VCD scope/ref/id_code 各最多256字符，完整名称1024字符，累计name+scope最多128 Ki字符；超限或含`$dumpoff`返回422。上传解析完成后若检测到客户端断开，不加入trace缓存；不能保证中止已经运行的解析线程。

## AnalysisRequest

请求禁止额外字段。以下是请求结构示例；**`s0`/`s1` 仅演示格式，必须替换为加载响应中的实际信号 ID，并确保 time 在 trace 范围内**。

```json
{
  "time": 120000,
  "signals": ["s0", "s1"],
  "window": 20000,
  "clock": null,
  "edge": "rising",
  "reset": null,
  "reset_active": "1",
  "reset_mode": "unknown"
}
```

| 字段 | 约束与默认值 |
| --- | --- |
| `time` | 必填整数，0 至 `2^53 - 1`，且必须在 trace 起止范围内 |
| `signals` | 必填 ID 数组，1–16 项；分析时去重；所有 ID 必须存在 |
| `window` | 非负整数半径，默认 20000，最大 `2^53 - 1` |
| `clock` | 单比特信号 ID 或 null，默认 null |
| `edge` | rising/falling，默认 rising |
| `reset` | 单比特信号 ID 或 null，默认 null |
| `reset_active` | 字符串 0/1，默认 1 |
| `reset_mode` | unknown/synchronous/asynchronous，默认 unknown；用户配置而非推断 |

时间均为 **tick**，不是固定 ns。窗口为 `[max(0, time-window), min(trace.end, time+window)]`，包含两端。`window=0` 可查看同时间戳记录。

响应包含：

- `time`、`timescale`、`window: {start, end}`。
- `signals`：每项有 id/name/width/value/previous/next/events/truncated。value 为光标时刻最后记录值或 null；previous 严格早于光标，next 严格晚于光标，各为事件或 null；窗口最多前 128 条事件。
- `clock`：null，或 name/edge/previous/next/at_time；只检测确定的 0→1、1→0。
- `reset`：null，或 name/value/active/mode；active 在值未知时为 null。
- `observed_facts`、`limitations`：字符串数组。
- `related_code`：file/line/text/signal/match；行号从 1 开始，match 为 `name-only`，最多 32 个结果。

report 使用相同请求与分析校验，输出事实、窗口事件与限制，不输出 AI 内容。

## ExplainRequest 与响应

继承 AnalysisRequest，并增加：

| 字段 | 约束 |
| --- | --- |
| `question` | 必填，1–2000 字符 |
| `consent` | 默认 false；必须 true 才能调用提供商 |
| `include_rtl` | 默认 false；独立授权发送名称匹配源码片段 |

后端重新计算确定性分析，再向服务端配置的提供商发送上下文。调用者不能在请求中选择任意 provider URL 或传 API key。

Explanation 包含 `summary` 字符串以及 `observed_facts`、`possible_explanations`、`related_signals`、`related_code`、`suggested_checks`、`limitations` 字符串数组。模型输出严格校验，信号名和 `file:line` 引用必须来自允许集合。后端以确定性分析覆盖 observed_facts，并给解释加推测标识。自由文本仍不保证正确。

## 错误与取消

通常错误体为 `{"detail": "说明"}`；FastAPI 请求模型校验失败的 detail 是结构化错误数组。主机校验或服务器并发限制等中间件错误不一定具有同一 JSON 格式。

| 状态 | 常见情况 |
| --- | --- |
| 403 | 不允许的 Origin；未同意发送 AI 请求 |
| 404 | 未知案例，或 trace 不存在/已淘汰 |
| 409 | 已存在同名源码 |
| 413 | 请求体、VCD 或 RTL 超限 |
| 422 | 格式/模型/ID/范围/类型校验失败 |
| 429 | 本进程已有 AI 请求进行中，或已配置的 HTTP 尝试预算用尽 |
| 499 | 客户端断开后的取消路径，断开客户端未必收到响应 |
| 502 | 提供商失败、响应无效/过大、引用不在白名单 |
| 503 | AI 未配置、无效配置、网络错误、暂不可用；服务器并发上限也可能返回 503 |
| 504 | AI 重试后仍超时 |

前端取消不会保证远端服务停止处理或免于计费。后端在分析完成、首次 Provider 调用前重新检查可观察到的客户端断开；这是尽力取消，不是即时撤回协议。默认单次 HTTP 超时 30 秒，`AI_MAX_ATTEMPTS` 只接受 1 或 2（默认 2）；总截止为配置超时 × 尝试次数 + 0.1 秒。`AI_REQUEST_BUDGET` 可设正整数，对当前实例的所有 HTTP 尝试设上限；在 I/O 前扣额，不能靠取消退额。重启重置预算，验收须单独跨进程记账并逐阶段授权。远程提供商 URL 必须 HTTPS，本机 loopback 允许 HTTP。

共享 `build_context` 仅复制 analysis 的 time/timescale/window/signals/clock/reset/observed_facts/limitations，并仅在 include_rtl=true 时添加 related_code；不发送原始 VCD、整个工程或配置。previous/next 可能在窗口外；clock/reset 可以是未选中的手动配置信号。

后端环境 `AI_API_FORMAT` 只接受 `chat_completions`（默认）或 `responses`，不会按域名猜测或自动切换协议。两种格式都使用后端 Bearer 认证、非流式请求、相同的响应大小限制和HTTP预算，不假定 JSON mode。

`chat_completions` 追加 `/chat/completions`，发送 system/user messages、model、max_tokens、stream=false；解析 choices[0].message.content 字符串。明确 finish_reason=length 时即使JSON完整也拒绝作为完整解释接受。

`responses` 追加 `/responses`，发送 model、instructions（相同SYSTEM_PROMPT）、input数组（user/input_text，文本为相同context JSON）、max_output_tokens、store=false、stream=false。不发送 tools、会话ID或 previous_response_id。仅接受顶层 status=completed 且 error/incomplete_details 为空的响应；从 output 数组提取 completed assistant message 的 output_text，跳过 reasoning，不依赖SDK顶层 output_text 便利字段。工具、拒答、不完整消息、空/畸形输出及多份独立JSON被拒绝；随后仍执行应用schema、引用及确定性事实覆盖。协议不匹配不会触发另一个端点的尝试。store=false不是第三方无日志的承诺；max_output_tokens对推理模型可能包含推理token，实际支持和用量需真实验证。

## 手动检查（无秘密）

后端运行时可执行：

```sh
curl http://127.0.0.1:8000/api/health
curl -X POST http://127.0.0.1:8000/api/demos/counter
curl -F 'file=@examples/counter/trace.vcd' http://127.0.0.1:8000/api/traces
```

后两个命令各加载一个新的 trace，计入四个 trace 的容量。分析请求应从其响应选取实际 ID，不能把不同 trace 的 signal ID 当作全局标识。
