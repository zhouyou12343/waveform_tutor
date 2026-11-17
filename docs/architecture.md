# 架构与信任边界

## 组件

| 位置 | 职责 |
| --- | --- |
| `frontend/src/App.tsx` | trace、选中信号、光标与时序配置；请求取消与过期分析结果隔离 |
| `frontend/src/Explorer.tsx` | 层级信号选择 |
| `frontend/src/Waveform.tsx`、`utils.ts` | SVG 绘制、整数 tick 定位、格式化、窗口裁剪 |
| `frontend/src/RTLViewer.tsx` | 上传源码、文本查看与名称关联展示 |
| `frontend/src/ExplanationPanel.tsx` | 显式同意、独立 RTL 授权、AI 请求与取消 |
| `frontend/src/api.ts` | 本地 `/api` 请求 |
| `backend/app/main.py` | FastAPI 路由、请求边界、内存 trace 生命周期 |
| `backend/app/parser.py` | 使用 PyVCD 解析受限数字 VCD、校验大小和结构 |
| `backend/app/models.py` | Pydantic 数据模型与请求/解释约束 |
| `backend/app/analyzer.py` | 确定性事实、事件查询、边沿、复位上下文、名称匹配、Markdown |
| `backend/app/ai.py` | 环境配置、HTTPX 提供商适配、同意检查、响应校验 |
| `scripts/generate_examples.py` | 仅重新仿真三个固定受信任示例 |

```text
浏览器 127.0.0.1:5173
  -> Vite /api 代理
  -> FastAPI 127.0.0.1:8000
       -> 有界 VCD 解析 -> OrderedDict 中最多 4 个 trace
       -> 确定性分析 -> JSON / Markdown
       -> 用户授权 -> 可选 AI 提供商
```

Vite 开发服务器不是生产部署方案。FastAPI 没有托管前端 dist 的路由；build 成功也不意味着已部署完整应用。

## 数据模型与生命周期

一个 Trace 包含随机 ID、文件名、timescale、每 tick 的飞秒数 `tick_fs`、起止 tick、Signal 列表、Source 文本列表和 warnings。每个 Signal 有独立 ID、完整层级名称、位宽、声明类型与有序 Event 列表。事件值统一为保留 X/Z 的二进制字符串。

VCD 同一标识符的别名展开为各个 Signal 的事件，并计入 100,000 事件上限。同时间戳的记录顺序保留；当前值取该时间戳最后一条记录。绘图没有完整仿真调度语义。

`remember()` 按加载顺序淘汰最旧 trace，不是基于访问热度的缓存。最多保留四个；重启清空。源码附属于 trace，未持久化为上传文件；没有数据库、项目保存、恢复会话或 trace 列表接口。前端在内存中维护工作区，不提供刷新恢复。不要使用多个独立 worker 来假定共享 trace。

## 确定性分析

分析使用客户端选择的整数 tick、信号 ID、窗口半径及可选时钟/复位配置。二分查询返回当前值、严格早于/晚于光标的记录；窗口包含端点，每信号最多前 128 条事件。时钟只接受单比特确定的 0→1/1→0；复位模式来自用户配置，不是推断。

RTL 关联使用信号叶名称进行文本边界匹配，最多 32 个结果，每行文本最多 300 字符。它可能匹配注释或不同模块中的同名变量；不是 AST、数据流或驱动关系分析。Markdown 报告来源于相同确定性分析，不包含 AI 回答。

## AI 边界

AIService首次需要时读取Git忽略的本机 `.waveform-tutor/ai-config.json`，若无本地文件才读取环境。网页ModelSettings通过本机GET/PUT/DELETE /api/ai/config管理配置，保存后即时替换实例、更新revision；Key只上传，不回传，页面不持久保存。清除用disabled标记阻止环境回退。环境变更仍须重启；不自动加载.env。配置明文存本机，仅面向单用户，不是密钥管理服务。没有配置也能解析、查看、分析与导出。新增网页配置路径本轮未运行验证。

显式 explain 请求且 `consent=true` 后，发送问题和分析上下文。默认删除 `related_code`；仅 `include_rtl=true` 才包含匹配的源码片段。提供商收到的是上下文而非完整上传文件。用户问题、信号名称、注释与源码都按不可信数据处理，但提示词不能保证彻底防止提示注入。

HTTPX 调用显式配置的非流式 OpenAI-compatible协议：`AI_API_FORMAT=chat_completions`（默认）追加 `/chat/completions`，`responses`追加 `/responses`。Responses使用instructions/input/max_output_tokens、store=false，提取已完成assistant文本，忽略reasoning、拒绝工具/拒答/不完整输出；仍走同一应用schema与事实覆盖。不使用官方SDK、不请求JSON mode、不自动换端点。不跟随重定向，trust_env=false，不继承HTTPX环境代理。响应限256KiB；`AI_MAX_ATTEMPTS`默认2、可设1，超时及429/502/503最多再尝试一次。默认单次HTTP超时30秒，总截止为超时×尝试次数＋0.1秒。`AI_REQUEST_BUDGET`可限制单实例HTTP尝试，失败/取消仍计数，重启清零，不替代跨进程账本或授权。远程必须HTTPS，仅loopback可HTTP；store=false不是第三方无日志保证。

结构校验拒绝额外字段、重复 JSON 字段及不合要求的数据类型；related signals/code 必须属于上下文白名单。后端覆盖 `observed_facts` 并标记推测。这限制了结构和引用，不保证自由文本真实或推理正确。

同一进程一次只处理一个 AI 请求，忙时返回 429。前端上下文改变或用户取消时中止请求，后端尝试取消任务；不能保证提供商已停止计算、计费或留存数据。

## 本地安全模型

- 默认仅 loopback。TrustedHost 允许 localhost、127.0.0.1 和测试用 testserver。
- 提供 Origin 时，仅接受 localhost/127.0.0.1 的 5173/8000 端口来源；这不是身份认证，也不阻止无 Origin 的本机客户端。
- POST/PUT/PATCH 请求体有上限：multipart 为 8 MiB + 64 KiB，其他为 32 KiB；文件还有独立类型、大小和内容检查。
- 上传内容不由应用作为项目文件保存，上传的 RTL 不执行。底层 multipart 解析可能使用临时缓冲/临时文件，不应宣称“整个网络栈绝不触碰磁盘”。
- Icarus 只由离线生成脚本对仓库三个固定示例调用。临时目录不是任意恶意 HDL 的安全沙箱。
- 不提供账号隔离、持久配额、多租户或公网部署保障。不要把本地防护等同于完整安全审计。

参见 [API](api.md)、[限制](limitations.md)与[开发指南](development.md)。
