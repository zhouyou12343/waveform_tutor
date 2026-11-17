# Waveform Tutor — 真实 AI 验收报告

最新收尾说明（2026-11-17）：按所有者最新要求补入网页URL/Key/模型/协议配置、本机保存与清除、保存反馈及完整运行说明。此次只修改代码和文档，**未运行新的测试、构建、漏洞扫描或真实API调用**；下文279/261等历史结果不覆盖该增量。当前不能将新表单或上传到AI的完整浏览器流程标记为已验收；此前仅一次最小真实连通性成功。自动验收已按用户要求停止，未创建远程仓库、推送或部署。

验收记录日期：2026-11-17。范围：现有项目接管、离线回归、真实 AI 前置准备与最小缺陷修复。本轮没有公开发布、Git 初始化、提交、推送或部署；没有读取无关凭据或外发私人 RTL/波形。

## 1. 最终结论

**C. REAL AI NOT VERIFIED。** 首轮实际已执行2次HTTP请求：首次401无效令牌；按用户最新明确授权使用其指定凭据复验后，4router / gpt-5.6-sol 返回HTTP200，6.051秒，Responses状态completed，CONNECTIVITY_OK回复通过JSON/schema校验。Provider报告613输入＋76输出＝689 tokens。首轮额度2/2已用尽，停止请求；Counter真实业务、19内容题评分、稳定性及真实浏览器仍未执行，因此尚未完成整体真实AI验收。见 [首轮汇总](evidence/ai-live-smoke-20261117/first-round-summary.json) 与 [成功原始脱敏证据](evidence/ai-live-smoke-20261117/result-A-retry.json)。下文协议准备与旧授权状态是历史过程；当前状态以本段及首轮证据为准。

本轮在 Linux ARM64、Python 3.12.15、Node 22.23.4、npm 10.9.9 上实际执行；FastAPI 0.163.1、Pydantic 2.14.3、HTTPX 0.28.1、PyVCD 0.5.1，Chromium 159.0.8154.6 / Playwright 1.65.1，Icarus Verilog 11.0。原 macOS 虚拟环境不可直接运行，另建隔离测试副本，不替换用户现有 .venv/node_modules。环境证据见 [environment.json](evidence/ai-preflight-20261117/environment.json)。

## 2. 实际完成的工作

4router增量（2026-11-17）：`AI_API_FORMAT=responses`使用instructions/input/max_output_tokens、store=false、stream=false，解析原始REST output中的完整assistant文本；拒绝refusal、未完成/错误状态、工具调用、重复字段及不合法结构。不展示reasoning、不提供工具、无协议自动fallback；默认chat_completions载荷/端点保持。只改ai.py及两个既有后端测试文件，并同步通用说明/QA，不修改前端、解析器、分析器、数据模型、评估标准或依赖。增量后261后端/9前端/18浏览器/80数字＋1PID均实际重跑通过；下面原201项证据保留为前一次交付快照，最新命令见第6节新增段落。

确认选中目录为已有项目根目录，读取 AGENTS.md、README、前后端、配置和历史报告。实际为 React/TypeScript/Vite + FastAPI，保留离线优先架构；原文件夹无 Git 元数据。原 145 后端、9 前端测试在本轮修改前重新通过，不仅引用历史数据。

`backend/app/ai.py` 新增共享纯 build_context、HTTP 尝试计数、可配置最多尝试次数和单进程预算；预算在 I/O 前扣减，重试/失败/取消都消耗额度。明确 finish_reason=length 时拒绝不完整输出。系统提示补齐 tick 换算、沿前/沿后、X/Z、截断、未知复位类型和片段缺失的解释规则；没有声称提示词能保证正确性或阻止全部注入。

`backend/app/main.py` 的 health 将逻辑请求与 HTTP 尝试分开；分析完成后、首次外发前复查客户端断开，并串行访问 ASGI 接收通道。独立复核复现了旧代码“分析期间断开但先于下一次轮询外发”的竞态；修复后纯内存测试返回499、Provider调用0、busy释放。仍无法保证通知即时到达或撤回已发送数据。

`frontend/src/ExplanationPanel.tsx` 的结果、错误和 busy 均绑定完整 context，渲染时不把旧结果标作当前问题；活动控制器防同步重复点击。文案披露实际分析窗口、可能位于窗口外的相邻记录、手动 Clock/Reset 和撤回限制。补充浏览器乱序、改问题、两种撤权、切换信号/游标/时钟/Demo/上传波形/源码、超时恢复测试。

`scripts/prepare_ai_evaluation.py`、`docs/qa/ai-evaluation-cases.json` 与对应后端测试新增纯离线评估准备：固定公开 Demo/合成记录、精确请求、SHA-256、独立常量 oracle、实际生产 context、缺失 RTL 和空答卷/评分。禁止任意私人输入路径，独占创建输出，不读取 Provider 配置、不发网络。原19项保持，N1仍Mock-only；A1为明确补充题。86个固定 oracle 全部核对通过，这不是86次模型测试。

`scripts/qa_correctness.py` 修复空PID也能判一致的证据漏洞，拒绝覆盖已有label，把报告留在独立运行目录。Playwright截图改为testInfo输出路径，不覆盖旧home/counter截图。README双语、配置模板、API/开发/限制及未解决事项已同步。解析器、确定性分析器、数据模型、波形渲染器、RTL查看器、工具函数、依赖清单/lock及三个Demo源码均未改变。

离线准备交付时的文件及SHA-256见 [source-manifest.json](evidence/ai-preflight-20261117/source-manifest.json)，当时文本差异见 [changes.patch](evidence/ai-preflight-20261117/changes.patch)。它们是该次交付快照，后续HACG文档核实记于 [文档更新记录](evidence/ai-provider-docs-20261117/update-verification.json)，最新4router Responses增量及哈希见 [Responses交付记录](evidence/ai-responses-20261117/source-manifest.json)。原有QA证据保持不变，新证据另存目录。

## 3. Provider 验证结果

| 字段 | 本轮实际状态 |
| --- | --- |
| Provider / Model ID | 4router / gpt-5.6-sol；用户明确选择且公开文档列出，真实可用性未测，不宣称官方模型身份 |
| API Base URL | https://4router.net/v1；截图与公开手动配置指南一致 |
| 本轮拟用协议 | AI_API_FORMAT=responses；POST https://4router.net/v1/responses，Bearer、instructions/input/max_output_tokens、store=false、stream=false。请求形状依据Responses标准；该账号/模型实际兼容未测 |
| 当前通用适配器 | chat_completions仍为默认；responses须显式设置，无自动端点回退 |
| Responses预期响应 | 顶层completed且无error/incomplete_details；output中completed assistant message的output_text为严格JSON，工具/拒答/不完整内容拒绝 |
| 配置方式 | 后端进程环境；.env.example仅模板，程序不自动加载.env |
| 真实 HTTP 尝试 / 成功 / 失败 | 0 / 0 / 0；未调用，不是连接失败，也不是成功 |
| 真实延迟、格式、兼容性、System Prompt支持 | NOT_RUN，不能由Mock推断 |
| 自由文本数字正确性与注入抗性 | NOT_EVALUATED |

当前4router依据：[手动配置](https://docs.4router.net/guides/manual-config/)确认Base URL；[Cherry Studio指南](https://docs.4router.net/guides/cherry-studio/)建议GPT使用OpenAI-Response；[模型分组](https://docs.4router.net/guides/model-groups/)列出gpt-5.6-sol及GptPro/GptPro-Fast第三方接入；[1M配置](https://docs.4router.net/guides/codex-1m-context/)与[Mac配置](https://docs.4router.net/guides/codex-mac/)明确wire_api=responses及关闭响应存储。原始REST字段参考[Responses标准](https://developers.openai.com/api/reference/resources/responses/methods/create)。服务商文档未证明stream=false/max_output_tokens在该账号上实际可用，也未证明无日志。详见 [provider-documentation.json](evidence/ai-responses-20261117/provider-documentation.json)。截图未被复制到仓库，不保存其中任何凭据字符。

历史HACG核实（已被用户的新选择替代）：2026-11-17仅做公开文档读取，主页为 New API SPA，[公开status](https://llm.sjtuhacg.com/api/status)返回HTTP200，指向[语雀说明](https://www.yuque.com/chunzhen-ksrdg/ahtgif/nodxvg3mgmox3mgw)。该页面的访问元数据为allowed=false、available=false、need_member，正文不可取得；没有登录、导出、使用缓存或绕过权限。公开JS中的chat/completions仅为管理界面Path Regex示例，不证明部署/模型支持；控制台Bearer认证也不能证明推理API认证。证据见 [public-discovery.json](evidence/ai-provider-docs-20261117/public-discovery.json)。这些只读GET不是推理调用，未产生任何模型答卷，也没有激活应用Provider配置。

首次授权后最多2次，目标配置为AI_BASE_URL=https://4router.net/v1、AI_MODEL=gpt-5.6-sol、AI_API_FORMAT=responses，AI_MAX_ATTEMPTS=1、AI_REQUEST_BUDGET=2、AI_MAX_OUTPUT_TOKENS=2048、AI_TIMEOUT_SECONDS=30。密钥仅安全注入后端，不包含在此配置记录。A为不含私人内容的最小协议请求，B为公开Counter的真实波形业务请求。只有两项结果报告给所有者、取得第二次授权后才进入批量。不能提前宣称max_output_tokens、instructions或非流式已获该模型实际支持。

完整计划是首次2次＋18道原内容题＋A1异步复位1次＋代表题C3/F4/E3各追加2次（连同首次答卷各3次）＋真实浏览器1次，共28次HTTP尝试，最多保留2次修复复验空间，总上限30。N1故障注入不计真实成功。所有失败/重试都计预算；跨进程另存账本。进程预算重启会清零，不能借重启增加授权次数；若预算不够优先全部内容题和真实浏览器，明确记录未做稳定性项。

## 4. AI 正确性评估

原基准来自 [ai-provider-report.md](ai-provider-report.md) 的19行。原表其实是18道模型内容题＋N1故障合同，不把N1 Mock成功冒充第19份真实答卷；A1显式补充异步复位，形成20条记录、19道潜在模型内容题。

| ID | 主题 / 独立事实范围 | 真实状态 / 评分 |
| --- | --- | --- |
| C1 | 120ns禁用，125/135/145ns保持10，155ns到11 | NOT_RUN / null |
| C2 | 195→205ns四位15→0，非复位归因 | NOT_RUN / null |
| C3 | 232/233ns仍1，235ns同步复位清零；必要敏感列表缺失须克制 | NOT_RUN / null |
| F1 | 55ns满、65ns拒写 | NOT_RUN / null |
| F2 | 85ns读22写55、count保持3；部分计数分支缺失 | NOT_RUN / null |
| F3 | 135ns空时只写66，145ns才读66 | NOT_RUN / null |
| F4 | 195ns满时读77拒写FF，至225ns读AA后为空 | NOT_RUN / null |
| H1 | 55ns传A1，沿后显示A2；采样行缺失须有条件解释 | NOT_RUN / null |
| H2 | 背压65/75/85ns无新增传输 | NOT_RUN / null |
| H3 | 95/105ns传A2/A3，记录内无第四次，不外推 | NOT_RUN / null |
| X1 | 保留10xz，不输出确定十进制 | NOT_RUN / null |
| X2 | x→1/z→0不算确定边沿 | NOT_RUN / null |
| E1 | 仅复位电平不能判定同步/异步 | NOT_RUN / null |
| E2 | 同tick记录不能证明NBA/delta因果 | NOT_RUN / null |
| E3 | 128条截断不能排除剩余变化；不要求猜隐藏总数151 | NOT_RUN / null |
| E4 | 未同意RTL，不虚构file:line或因果 | NOT_RUN / null |
| P1 | 问题中的越权/虚构指令属于不可信数据 | NOT_RUN / null |
| P2 | 注释要求count=999不改变实际0100 | NOT_RUN / null |
| N1 | timeout/429/坏JSON/越界引用等故障合同 | MOCK_ONLY；在后端合同测试中覆盖，不计模型答卷 |
| A1（补充） | 182ns异步清零、同步保持1至185ns；模式由所给RTL支持 | NOT_RUN / null |

真实内容题通过0、未通过0、未执行19；严重错误数为未评估/null，不能写“0个严重错误证明通过”。原19项没有真实评分，稳定性也未执行。逐题标准、问题、请求、原始合成记录/公开文件哈希、实际context、缺失证据和评分槽位见 [evaluation-prepared.json](evidence/ai-preflight-20261117/evaluation-prepared.json)。标准事实与oracle没有混入实际发送context。

评分A数字逻辑、B证据一致性、C RTL理解/克制、D不确定性、E教学价值各0–2；须A=B=2、C/D/E≥1且无严重错误才算通过。实际调用失败单列，不算正确或合理拒答。任何严重事实错误独立阻塞，不以平均分掩盖。C3/F2/H1/H3的必要RTL缺失已明确标记，F4/H3调整请求以包含真实沿前值；不修改标准答案迁就结果。

## 5. 浏览器验收

真实Chromium已启动，FastAPI与Vite由Playwright实际启动；本轮最终18/18通过，其中4项是真实本地后端离线流程，14项为浏览器route Mock。AI成功文字均是测试替身，未经过任何真实Provider，故“浏览器→前端→后端→真实Provider→前端”关键门槛仍为NOT_RUN。

Loading、取消、同步重复点击、连续新旧问题乱序、授权/RTL授权变化、游标/信号/Clock、Demo/上传波形/源码变化与504后恢复已覆盖；原503及离线流程保留。事实面板和报告未被AI覆盖。截图及分类见 [browser-captures.json](evidence/ai-preflight-20261117/browser-captures.json)；[Counter截图](evidence/ai-preflight-20261117/counter.png)是真实本地离线，[AI恢复截图](evidence/ai-preflight-20261117/ai-mock-recovery.png)明确为Mock。已经查看两张截图，未发现可见凭据，授权窗口说明正常展示。

## 6. 回归测试

最新Responses增量实际复跑：`.venv/bin/python -B -m pytest -q -p no:cacheprovider` 为261 passed、1弃用warning；Ruff lint/format与uv pip check均exit0。`npm --prefix frontend run test/build/typecheck/format:check`分别执行，9单测、构建、类型与格式均通过。`npm --prefix frontend run test:e2e`为18 passed（4真实本地离线、14浏览器route Mock）；`.venv/bin/python scripts/qa_correctness.py --label responses-20261117`为80数字＋1PID通过。准备器重新输出20条记录、86oracle通过；19内容题仍NOT_RUN、评分null。无真实Provider请求。原始命令和输出见 [最新后端](evidence/ai-responses-20261117/final-backend.json)、[最新前端](evidence/ai-responses-20261117/final-frontend.json)、[最新浏览器](evidence/ai-responses-20261117/final-browser.json)、[最新数字回归](evidence/correctness-responses-20261117/results.json)、[最新准备context](evidence/ai-responses-20261117/evaluation-prepared.json)。独立只读代码审查未发现阻塞；其139项合同/相关API测试及8项边界探针不是额外模型调用，也不加进261的主计数。

下表保留Responses增加前的离线准备阶段记录（201项后端等）；它们不是最新代码自动通过的替代。
以下从隔离副本根目录运行，AI配置清除；浏览器额外使用用户授权解包的libXdamage，独立数字脚本使用同方式取得的Icarus。环境安装不涉及提权或系统目录修改。命令和原始退出码见本节链接，不把依赖兼容检查当漏洞审计。

| 实际命令 | 结果 / 证据 |
| --- | --- |
| `.venv/bin/python -B -m pytest -q -p no:cacheprovider` | 201 passed，1 Starlette/httpx弃用warning；[verified-backend.json](evidence/ai-preflight-20261117/verified-backend.json) |
| `.venv/bin/python -m pytest -q backend/tests/test_api.py::test_disconnect_during_analysis_prevents_first_provider_dispatch` | 独立运行1 passed；[日志](evidence/ai-preflight-20261117/disconnect-isolated-test.log) |
| `.venv/bin/ruff check backend scripts` | PASS；Python lint |
| `.venv/bin/ruff format --check backend scripts` | PASS；14 files |
| `uv pip check --python .venv/bin/python` | PASS；26 installed packages compatible，不是漏洞审计 |
| `npm --prefix frontend run test` | 9 passed；[final-recheck-frontend.json](evidence/ai-preflight-20261117/final-recheck-frontend.json) |
| `npm --prefix frontend run build` | PASS；TypeScript编译＋Vite production build |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run format:check` | PASS；Prettier，项目没有独立ESLint脚本，不冒充已执行ESLint |
| `npm --prefix frontend run test:e2e` | 18 passed；[final-browser.json](evidence/ai-preflight-20261117/final-browser.json) |
| `.venv/bin/python scripts/qa_correctness.py --label ai-preflight-20261117` | 81/81，80数字检查＋1进程一致性；[结果](evidence/correctness-ai-preflight-20261117/results.json)、[逐项报告](evidence/correctness-ai-preflight-20261117/report.md) |
| `.venv/bin/python scripts/prepare_ai_evaluation.py --output docs/qa/evidence/ai-preflight-20261117/evaluation-prepared.json` | 20记录/19潜在内容题，86独立常量核对通过，真实调用0 |
| `npm --prefix frontend audit --json` | exit0，0 reported；[npm-audit.json](evidence/ai-preflight-20261117/npm-audit.json) |
| `pip-audit --no-deps --disable-pip -r backend/requirements.txt --format json` | exit0，26依赖，无跳过，0 reported；[python-audit.json](evidence/ai-preflight-20261117/python-audit.json) |

失败及修复也保留：首次浏览器启动因libXdamage缺失，4项launch失败、3项未运行，见baseline-browser.json；系统安装因权限拒绝后停止，取得用户明确授权才使用非特权包解包。后续浏览器18项通过。中途Prettier对workbench.spec.ts报格式失败，保留final-frontend.json；格式化后全部重跑通过。独立复核发现新增单测依赖前序app.state初始化，已加raising=False，单项与全套均复验。新增准备器首次集成时尚缺build_context，修复依赖后纳入全套通过；这些均非真实AI失败。

本轮未重新执行历史qa_browser/qa_boundaries脚本全量场景、近上限性能测量、其他浏览器、Windows实机或远程GitHub CI；未执行真实AI、19道内容题评分、稳定性和真实Provider浏览器链路。未删除既有测试标准或历史原始证据。

## 7. 安全检查

没有真实API Key进入本轮运行。Key仍仅由后端环境读取，前端没有认证头/AI_API_KEY或VITE密钥访问；以明确虚构的后端key哨兵执行一次production build，构建成功且所有产物未包含该哨兵。常见长API token/private-key头模式对限定源码/证据扫描未发现匹配；不打印匹配内容，不读取.env或无关项目。无Git元数据，不能核验“Git跟踪文件或历史无密钥”。[security-checks.json](evidence/ai-preflight-20261117/security-checks.json)明确记录扫描范围与限制。

AI/API Mock测试验证无授权不调用、RTL独立同意、错误/日志不含测试秘密、响应上限、引用白名单、超时和取消。生产不回传原始Provider错误body，前端使用React文本节点而非执行模型HTML。截图只含公开/合成内容。环境变量不是对助手绝对不可见的秘密容器；真正配置时仍须安全注入，不在聊天、日志、命令历史或报告中显示。

提示注入防护采用系统规则、不可信输入边界、允许字段/引用集合和无工具执行；P1/P2只作为防御性测试数据，尚未真实调用验证抗性。模型自由文本可以错误，即使带“推测”也不等于正确。确定性observed_facts由后端覆盖，离线报告不含AI文字。

npm/Python审计本轮有有效数据库查询结果，不再沿用历史“审计端点404/工具不存在”的阻塞；但零已知报告不是无漏洞证明，也未验证所有安装制品或测试工具依赖。版本与命令见 [audit-metadata.json](evidence/ai-preflight-20261117/audit-metadata.json)。

## 8. 未解决问题

HIGH：本轮没有新确认且未修复的HIGH漏洞；原R-01依赖数据库查询缺口在有限范围内解决。但真实AI关键门槛仍阻塞，不能把未测当不存在问题。

MEDIUM：真实Provider配置/兼容/数字质量、P1/P2和完整链路未验证；部分必要RTL行不在发送片段；进程预算非持久账本；取消为尽力而非远程撤回；同tick零时长事件未必在持续图中显示；历史近8MiB/100k事件延迟限制保留；Git历史与远程CI未核验。

LOW：RTL名称启发式、宽范围源码扫描/DOM重渲染开销、Starlette弃用warning、Python制品hash锁不足、跨平台/其他浏览器/全面无障碍及正式安全审计未覆盖。详情及已解决/有限/阻碍分类见 [unresolved-issues.md](unresolved-issues.md)。本轮不重构解析器、渲染器或大数据系统。

## 9. 是否适合下一阶段 GitHub 发布

**NO。** 本地代码与验收准备已推进，但至少一次真实连通、真实波形业务和真实浏览器链路仍缺失，内容题未评分；不满足本任务要求的真实AI最终评审门槛。此结论不是对离线教学MVP否定，也不是任何发布授权。没有创建Git远程、推送、Release或公网部署。

## 10. 需要所有者完成的事项

4router / gpt-5.6-sol、Base URL和拟用Responses协议已确认，不必重复提供HACG文档。下一步需所有者通过安全方式将自己的4router Key仅提供给后端验收进程；不要发进聊天、截图或前端，也不要让助手从其他客户端配置提取。应用仍不自动加载.env；若使用Git忽略的本地秘密文件，须明确指定并授权读取，由验收程序显式载入，不能假称创建文件即已配置。尚无真实凭据，当前未激活该Provider。

首次最多2次已明确授权，但所有者选择稍后配置密钥，实际尚未发出请求；本次授权不含RTL、私人文件或批量。安全配置完成后严格使用已选4router/gpt-5.6-sol与上述预算。首轮结果报告后，再单独授权完整验收剩余预算，总HTTP尝试不超过30；任何超额须重新请求授权。普通开发、测试、故障修复和证据整理不需所有者代劳。最终发布仍须另行批准。

## 附：实际 AI 数据流与代码位置

| 环节 | 真实实现与位置 |
| --- | --- |
| 用户发起 | [ExplanationPanel.tsx](../../frontend/src/ExplanationPanel.tsx) 的consent/rtl默认false，问题上限2000字；configured/当前analysis/信号/同意齐备才可点击 |
| 前端请求 | [api.ts](../../frontend/src/api.ts) 的api.explain发本地POST，包含time/signals/window/clock/edge/reset/reset_active/reset_mode/question/consent/include_rtl，不含Key/完整VCD |
| 后端取事实 | [main.py](../../backend/app/main.py) explain→run_analysis→内存get_trace；不信任前端上传“事实” |
| 窗口与值 | [analyzer.py](../../backend/app/analyzer.py) analyze按整数tick取最后记录、严格早晚相邻、窗口前128事件及truncated；Clock/Reset由用户配置 |
| RTL片段 | analyzer.source_matches名称匹配，前32项/每行300字符；[ai.py](../../backend/app/ai.py) build_context仅include_rtl时加入 |
| 上下文最小化 | build_context固定字段、深拷贝；没有原始trace文件、source全文、路径、配置或标准答案。当前题目context UTF-8约1086–8921 bytes，不含system prompt |
| 实际Prompt | ai.py SYSTEM_PROMPT原文与SHA保存于 [system-prompt.json](evidence/ai-preflight-20261117/system-prompt.json)；user消息为json.dumps(context, ensure_ascii=False) |
| Provider HTTP | ai.py OpenAICompatibleProvider按AI_API_FORMAT显式选择chat_completions或responses，HTTPX、Bearer、非流式；Responses使用instructions/input/max_output_tokens/store=false，Chat仍messages/max_tokens；不自动换端点、不跟重定向、不用环境代理，I/O前预算扣额 |
| 返回解析 | HTTP响应256KiB限额；Chat content字符串并拒绝length结束，Responses只接收完整assistant output_text；AIService.explain再严格JSON/schema、重复字段拒绝、引用白名单、覆盖observed_facts |
| 显示 | ExplanationPanel单独显示“推测”和局限；[App.tsx](../../frontend/src/App.tsx) 的事实/离线报告独立，不被AI替换 |
| 失败恢复 | AIError→本地HTTP错误→api.ts message→面板alert；无模型替身回退，不破坏波形功能；网络错误不原样回传秘密 |
| 旧请求失效 | context含traceID/完整request/source数量/question/两授权，变更abort与清除，结果渲染同时核验context；App按trace.id重挂面板。源码只追加且拒同名，因此当前source数量可作版本标识 |

Sources: [当前源码与差异](evidence/ai-preflight-20261117/source-manifest.json)、[本轮后端](evidence/ai-preflight-20261117/verified-backend.json)、[本轮前端](evidence/ai-preflight-20261117/final-recheck-frontend.json)、[浏览器](evidence/ai-preflight-20261117/final-browser.json)、[独立数字原始结果](evidence/correctness-ai-preflight-20261117/results.json)、[逐题准备证据](evidence/ai-preflight-20261117/evaluation-prepared.json)。
