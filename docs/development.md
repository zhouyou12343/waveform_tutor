# 开发与验证

## 环境与启动

从项目根目录执行命令。建议 Python 3.11+、Node.js 22.12+ 和 npm；本地记录的实测版本是 Python 3.14.3、Node.js 24.15，不代表完整跨平台支持矩阵。POSIX shell：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
```

首次安装需要联网。后端：

```sh
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --limit-concurrency 16
```

另一终端：

```sh
npm --prefix frontend run dev
```

访问 `http://127.0.0.1:5173`。Vite 配置固定 loopback、5173 和 strictPort；`/api` 转发至 8000。不要依赖自动换端口。build 输出不是 FastAPI 自动托管的完整站点。

不需要AI即可开发核心功能。一般用户可在网页模型配置表单输入URL/Key并保存；配置位于Git忽略的.waveform-tutor/ai-config.json，后端不回传Key。高级环境变量方式见[主README](../README.md#optional-ai)；.env.example仍是模板，不自动加载。后端代码更新后必须重启；前端使用另一个终端启动，访问5173，不是8000根路径。新增网页配置/持久化代码在此次收尾中未运行测试、构建或扫描，以下检查命令仅保留为开发者参考，不代表本轮执行。

## 检查命令

```sh
.venv/bin/python -m pytest -q
.venv/bin/ruff check backend scripts
.venv/bin/ruff format --check backend scripts
npm --prefix frontend run build
npm --prefix frontend run typecheck
npm --prefix frontend run test
```

pytest 的 testpaths 和 pythonpath 来自根目录 `pyproject.toml`；从根目录运行可保持导入行为一致。前端 test 使用 tsx 执行 Node 的 `node:test`，不是浏览器测试。

浏览器测试：

```sh
frontend/node_modules/.bin/playwright install chromium
npm --prefix frontend run test:e2e
```

Playwright 使用根目录 `.venv` 自动启动 FastAPI 和 Vite，非 CI 环境可复用已运行的本地服务。离线集成测试要求未配置 AI 环境变量。Chromium 安装可能需要联网；下载失败不能当作应用行为测试通过。浏览器测试包含真实 API 场景与 mock 场景；mock 不证明真实提供商响应正确。

已有本地验证记录包括后端测试、前端单元测试、真实 API 与 mock 浏览器测试、三个案例再生成及其断言通过。不固定测试数量，也不把这些记录当作未来每次修改自动通过的保证。未验证远程 GitHub CI；只有实际运行日志才能支持远程检查通过的结论。

## 重新生成案例

正常启动直接读取已提交的 `examples/{counter,fifo,handshake}/trace.vcd`，无需仿真工具。维护示例时，可先通过自己系统的可信软件来源安装 **Icarus Verilog**，确保 `iverilog` 和 `vvp` 在 PATH，再运行：

```sh
.venv/bin/python scripts/generate_examples.py
```

脚本只接受仓库中固定的三个案例，没有上传路径或任意源码参数。它校验 `lesson.json` 的结构，复制 `design.sv`/`tb.sv` 到临时工作目录，用 `iverilog -g2012 -Wall -s tb` 编译，再执行 `vvp`，每条子进程命令有 30 秒超时。成功后覆盖对应 `trace.vcd`；仿真 testbench 内断言失败会导致生成失败。

临时目录只隔离产物，**不是恶意源码沙箱**。不要把它扩展成执行用户上传 RTL 的 API。更改示例时同时核对源码、testbench、lesson 问答、实际 trace 与文档检查点：

- Counter：120 ns 禁用；count 为 10；125/135/145 ns 保持；205 ns 回绕；235 ns 同步复位清零。
- FIFO：55 ns 满；满/空状态下的同时读写行为以该示例规则为准，不泛化成所有 FIFO。
- Handshake：55/95/105 ns 三次传输，注意沿前握手与沿后显示值的差异。

## 手动回归清单

- 无 AI 环境启动，确认三个案例都能打开，不触发外部解释请求。
- 上传合法 VCD 和 UTF-8 RTL，检查层级、未知值、总线格式和名称匹配。
- Counter 输入 120000 tick，确认 1 ps/tick 与 120 ns 换算正确。
- 切换信号/时间/源码时，旧分析或 AI 结果不应冒充当前上下文结果。
- 检查缩放、平移、空选择、输入越界、窗口截断提示和 Markdown 下载。
- 连续载入超过四个 trace 或重启后端，确认旧 ID 失效有提示。
- 用 mock 覆盖 AI 无同意、未配置、超时、取消、无效 JSON、未知引用；不要为测试把真实密钥写入 fixtures。

这些是待执行检查步骤，不是本次文档编辑已执行的测试声明。

## 常见问题

| 症状 | 排查 |
| --- | --- |
| Backend not connected | 后端是否从根目录启动，8000 是否可访问；检查 `/api/health` 与终端错误 |
| 前端启动报告端口占用 | 5173 使用 strictPort；确认已有进程，不要静默换端口绕过 Origin 规则 |
| AI 显示 Offline | 三项必填环境变量是否传给后端；仅创建 `.env` 不会生效；变更后重启 |
| 旧 trace 返回 404 | 已重启或加载超过四个；重新加载文件 |
| 事件/波形部分空白 | 可能达到 128 事件或 2000 segments 限制；缩小窗口，不要把省略当成无事件 |
| 浏览器测试失败连接后端 | 检查根目录 `.venv` 及依赖、8000/5173 端口占用；Playwright 自动启动两端服务 |
| 示例生成失败 | 检查 Icarus 的两个可执行文件、断言输出和本地示例；不要跳过断言 |

## AI 验收准备与证据隔离

2026-11-17 在 Linux ARM64、Python 3.12.15、Node 22.23.4 上重新执行的结果见 [AI 验收报告](qa/real-ai-acceptance-report.md)。运行时依赖在隔离副本中安装，未替换原 macOS 虚拟环境；不据此宣称全面跨平台支持。

以下命令只读取固定公开 Demo/合成 fixture，并通过生产 build_context 生成待审查上下文；不读取 Provider 配置或发请求。输出路径必须不存在，防止覆盖已有证据。

```sh
.venv/bin/python scripts/prepare_ai_evaluation.py --output docs/qa/evidence/<new-run>/evaluation-prepared.json
```

题库位于 `docs/qa/ai-evaluation-cases.json`；原 N1 故障合同保持 Mock-only，另加明确标注的 A1 异步题。标准事实和 oracle 只供评审，不进入发送 context。每题 A–E 评分、实际输出、严重错误判定保持 null，直到真实调用和人工审查完成。

独立数字回归需要已启动的离线后端及 PATH 中的 Icarus `iverilog`/`vvp`、lsof、ps：`.venv/bin/python scripts/qa_correctness.py --label <unique-run>`。每次使用新 label，证据和报告保存到同一个独立目录；不再覆盖历史 correctness-report.md。PID 未识别不能算作进程一致性通过。Playwright 截图改为 testInfo.outputPath，不覆盖历史 docs/screenshots；若要长期保留，请复制到新的 QA 证据目录。

真实调用不由离线准备器执行。必须先确认公开文档、准确 Model ID、安全配置和首次最多两次的明确授权，设置 `AI_MAX_ATTEMPTS=1`、`AI_REQUEST_BUDGET=2`，另行记录跨重启请求账本。第二阶段也必须另获授权；不得把重新启动后的预算当成追加授权。

## 贡献原则

以真实代码、trace 和测试为证据，先区分事实、配置、推测。涉及边沿、同时间戳、未知值或限额的修改应补回归测试。保持源码执行禁区和秘密隔离；不要在日志、截图、fixture 或文档中留下用户数据与密钥。更新接口时同步 API/限制文档；运行失败要记录原因，不能删除断言或宣称通过。
