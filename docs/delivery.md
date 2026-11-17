# Waveform Tutor — 首版交付报告

## 1. 项目完成情况

**离线 MVP 验收通过，已实际启动前后端并用 Chromium 操作，不只是编译通过。**

已实现：

- 真实 VCD 上传/解析：层级、标量、总线、别名、X/Z、timescale、同时间戳记录。
- 深色三栏工作台：信号搜索/选择、时间光标、整数精确定位、物理时间换算、缩放/平移、进制切换。
- 确定性分析：当前值、严格早于/晚于时间点的记录、窗口事件、手动指定时钟边沿、复位状态与类型配置。
- RTL 上传、文件切换、行号、简单语法着色、搜索、名称匹配高亮；明确标注为启发式。
- Counter、FIFO、Ready/Valid 三个真实仿真案例，各有 design、testbench、VCD、教学问题与预期观察。
- 离线 Markdown 事实报告。
- 可替换 AI Provider 接口和 OpenAI-compatible HTTP 适配器：后端环境配置、发送确认、独立 RTL 授权、结构/引用校验、有限重试、超时、取消、调用计数。
- 测试、锁定依赖、双语 README、专题文档、MIT、CI 配置、真实截图。

未完成或未验证：

- **真实第三方 AI 调用尚未验证**：未提供/使用真实密钥，兼容性只经过 MockProvider 和 HTTP MockTransport 测试，不保证任何平台或型号可直接使用。
- **GitHub Actions 尚未远程运行**：配置和相应本地命令已检查，但没有远程通过记录。
- RTL 不做完整 HDL AST、端口/进程/控制流或语义驱动关系分析；不证明因果。
- 没有多信号自动因果/协议诊断器、专家/入门解释模式切换、完整项目持久化、大型波形流式加载或浅色主题切换。
- 教学问题保存在 lesson.json，尚无教学题目交互播放器。
- 没有执行上传 RTL、公开部署、账号系统、FST/FSDB 支持或形式验证。

MVP 边界：8 MiB VCD、512 信号、256 bit、100,000 展开事件、最多 16 可见信号；本地进程保留最近 4 个波形，重启清空。详见 [limitations.md](limitations.md)。

## 2. 技术架构

| 层 | 实现及原因 |
| --- | --- |
| 前端 | React 19 + TypeScript + Vite 8 + Tailwind 4；SVG 窗口裁剪，适合首版小规模波形且易测试 |
| 后端 | FastAPI + Pydantic；边界输入校验，分析与网络调用分离 |
| VCD Parser | PyVCD tokenizer 加结构/资源校验；不自行用正则模拟 VCD 语法 |
| Event Analyzer | 有序记录和二分查询；整数 tick，不用浮点时间查事件 |
| RTL | 文本名称匹配，不宣称完整 Verilog/SystemVerilog parser |
| AI | Provider Protocol + HTTPX；配置与密钥只留后端，不依赖供应商专有能力 |
| 存储 | 有上限的进程内存；案例、配置模板和教学说明保存在本地仓库 |

```text
真实 VCD → PyVCD + 严格校验 → 有序逻辑值记录
                              ↓
                        确定性窗口分析
                              ↓
              波形 / 事件 / RTL 名称关联 / 离线报告
                              ↓ 仅用户明确同意后
                     结构化上下文 → AI Provider
                              ↓
                校验 JSON/引用 + 用真实事实覆盖模型事实
```

模型自由文本仍可能幻觉；它始终是可能解释，不是新的仿真证据。

## 3. 实际目录结构

```text
waveform_tutor/
├── backend/
│   ├── app/
│   │   ├── main.py          # API、上传边界、内存管理
│   │   ├── models.py        # 请求/数据/解释模型
│   │   ├── parser.py        # VCD 解析与限制
│   │   ├── analyzer.py      # 事件、边沿、RTL 名称关联、报告
│   │   └── ai.py            # Provider、网络调用、证据校验
│   ├── tests/              # parser/analyzer/API/AI 测试
│   └── requirements.txt    # 实际安装版本锁定
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── Explorer.tsx
│   │   ├── Waveform.tsx
│   │   ├── RTLViewer.tsx
│   │   ├── ExplanationPanel.tsx
│   │   ├── api.ts / types.ts / utils.ts
│   │   └── styles.css
│   ├── tests/              # 数值单测、Mock UI 与真实 API 浏览器测试
│   ├── playwright.config.ts
│   └── package.json / package-lock.json
├── examples/{counter,fifo,handshake}/
│   └── design.sv / tb.sv / trace.vcd / lesson.json
├── scripts/generate_examples.py
├── docs/
│   ├── architecture.md / api.md / development.md
│   ├── limitations.md / dependencies.md / delivery.md
│   └── screenshots/home.png / counter.png
├── .github/workflows/ci.yml
├── pyproject.toml
├── .env.example / .gitignore / LICENSE / AGENTS.md
└── README.md / README.zh-CN.md
```

保留了原目录名，没有覆盖原项目或修改 `.claude` 设置；没有初始化远程仓库、提交或推送。

## 4. 运行方式

本次本机依赖已安装。以下启动命令均从项目根目录运行：

`waveform_tutor/`（项目根目录）

**终端 A：启动本地后端**

```sh
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --limit-concurrency 16
```

作用：启动解析与分析 API。预期：显示 `Uvicorn running on http://127.0.0.1:8000`，保持终端运行。

**终端 B：启动前端**

```sh
npm --prefix frontend run dev
```

作用：启动开发界面和本地 API 代理。预期：显示 `http://127.0.0.1:5173`。打开该地址即可使用，无需 AI Key；如果端口已有本项目服务，直接访问，不要重复启动。

**其他机器首次安装**，也在项目根目录逐条运行：

| 命令 | 作用 | 预期 |
| --- | --- | --- |
| `python3 -m venv .venv` | 创建项目隔离 Python 环境 | 出现 `.venv/` |
| `.venv/bin/python -m pip install -r backend/requirements.txt` | 安装后端及测试依赖 | 安装成功，无依赖冲突 |
| `npm --prefix frontend ci` | 严格按 lockfile 安装前端 | 安装成功 |

本机验证环境：macOS / Python 3.14.3 / Node 24.15.0 / npm 11.12.1 / Icarus 12.0。打开内置 VCD 不需要安装 Icarus；首次依赖和浏览器安装需要网络。

## 5. 实际测试结果

所有命令从项目根目录执行，以下为本次实际结果：

| 命令 | 结果 |
| --- | --- |
| `python3 scripts/generate_examples.py` | 三个案例仿真及全部 testbench 断言通过 |
| `.venv/bin/python -m pytest -q` | **107 passed**，1 个依赖弃用警告 |
| `.venv/bin/ruff check backend scripts` | 通过 |
| `.venv/bin/ruff format --check backend scripts` | 10 个 Python 文件格式通过 |
| `.venv/bin/python -m pip check` | 无损坏依赖 |
| `.venv/bin/python -m pip install --dry-run -r backend/requirements.txt` | 锁定依赖与当前环境一致 |
| `npm --prefix frontend ci` | 按锁文件重新安装成功 |
| `npm --prefix frontend run build` | TypeScript + Vite production 构建成功 |
| `npm --prefix frontend run typecheck` | 通过 |
| `npm --prefix frontend run format:check` | 通过 |
| `npm --prefix frontend test` | **7 passed** |
| `CI=1 npm --prefix frontend run test:e2e` | **7 passed**；自动冷启动前后端，4 个真实 API 场景、3 个 Mock UI 场景 |

浏览器覆盖：真实 Counter、120 ns 数据、时钟最近边沿、波形点击、搜索、多选、缩放、平移、报告、RTL 上传、FIFO/Handshake、非法 VCD、X/Z、时间越界、空选择和窄屏布局；Mock AI 覆盖同意、输出、失败和取消。已打开实际截图检查，不是仅保存未查看。

后端警告来自 Starlette TestClient 的 HTTPX 适配弃用提示，没有抑制或跳过测试；未来升级可评估 httpx2 或直接使用 ASGITransport。

未执行：真实 AI 服务调用、远程 GitHub CI、Windows/Linux 实机测试、大型设计性能基准、正式安全审计。CI YAML 已经本地 YAML 解析检查，文档相对链接无缺失。

## 6. 功能演示

1. 打开 `http://127.0.0.1:5173`，点击 **Counter**。
2. 左侧搜索并选择 `tb.clk`、`tb.enable`、`tb.reset`、`tb.count[3:0]`；可以移除默认选中的其他信号。
3. Clock 选择 `tb.clk`；Reset 选择 `tb.reset`、Active=1、Reset mode=Synchronous。这是根据示例 RTL 手动配置，不是自动推断。
4. Cursor 输入 `120000`，点击“跳转”。界面显示换算后的 **120 ns**；右侧应显示 `count=1010`、`enable=0`。
5. 展开事件卡，检查前一时钟上升沿 `115000`、后一上升沿 `125000`；再看 `125000/135000/145000` 时 count 保持为 10。
6. 下方查看 `design.sv`；名称匹配高亮不是因果证明。用“下载 Markdown 报告”导出事实。
7. 可选 AI：在后端环境安全设置 `.env.example` 所列变量并重启；应用不会自动读取 `.env`。远程 Base URL 必须 HTTPS。不要在聊天粘贴密钥。
8. 输入问题，勾选发送信号/事件/问题的确认；只有愿意发送相关 RTL 片段时再勾选独立授权，然后生成解释。结果区区分观察事实、可能解释、检查项和限制。

事实样例已经真实验证；第 7–8 步的第三方联网效果需要用户选定供应商后单独验证。

截图：[首页](screenshots/home.png)、[Counter 工作台](screenshots/counter.png)。

## 7. GitHub 发布准备

- [x] 英文 README 与中文 README。
- [x] MIT License，直接依赖许可证说明。
- [x] `.gitignore` 排除 `.env`、虚拟环境、node_modules、构建缓存和本地助手配置；保留 VCD 和截图。
- [x] Python requirements 与 npm lockfile。
- [x] 后端测试、前端单测、真实浏览器测试。
- [x] GitHub Actions：后端测试/静态检查/真实例子生成；前端格式/类型/单测/构建/浏览器测试。
- [x] 三个可复现示例和真实截图。
- [x] API、架构、开发、限制、依赖与维护文档。
- [ ] 真实 AI Provider 兼容性验证。
- [ ] GitHub 上首次 CI 运行。
- [ ] 用户确认后的仓库初始化、首次提交与远程发布。

未创建远程仓库、推送代码或公开部署。CI 是新建待发布配置，没有修改任何已有共享流水线。

## 8. 后续改进路线

1. **P0：选择一个真实 Provider 做小型兼容性验收**，使用非敏感教学波形，检查 JSON 行为、费用、取消与错误提示。
2. **P1：提升源码关联质量**，引入成熟 HDL parser，保留明确证据级别；不能把名称匹配直接升级为因果结论。
3. **P1：增强波形性能**，后端窗口分页/索引、Canvas 或虚拟化，增加大文件真实基准后再提高限制。
4. **P2：增加可配置规则分析**，例如用户声明语义后的 ready/valid 与计数器检查，并验证沿前/沿后差异。
5. **P2：可保存的本地项目**，设计删除、敏感数据留存与跨会话恢复；当前只保留临时内存。
6. **P3：教学与易用性**，lesson.json 交互展示、解释深度选择、主题切换、键盘可访问性和跨平台安装验收。
