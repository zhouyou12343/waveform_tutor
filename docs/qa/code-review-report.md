# v0.1.0 RC 代码审查

## 方法与基线

本次检查日期：2026-11-16。目录没有 `.git`，无法检查提交历史或基于提交生成 diff；修改前源码保存在不用于发布的 `.qa-baseline/`，附 SHA-256 manifest。三个只读审查分别覆盖复用、质量/安全、效率；其结论是静态线索，不冒充运行结果。随后通过实际 HTTP/Chromium 复现。历史交付中的 107/7/7 不作为本次执行结果。

浏览器初始基线：`node scripts/qa_browser.mjs baseline`，7 个场景组通过，证据 `evidence/browser-baseline.json`。包括 Counter、FIFO、Handshake、报告、搜索/缩放、非法上传及网络检查。

## 修复前发现（先记录，后修复）

| ID | 级别 | 发现与证据 | 初始状态 |
| --- | --- | --- | --- |
| QA-01 | HIGH | 标识符/完整名称无长度上限。实际 HTTP 上传 4,580 bytes（4096 字符 scope，16 signals）返回 JSON 132,797 bytes。未尝试危险的大内存载荷。 | 已小规模复现 |
| QA-02 | MEDIUM | `$dumpoff` 缺少未知值快照时仍显示先前确定值。实际上传 t0=1、t10 停录、t20 恢复，分析 t15 返回 value=1，仅附停录警告。 | 已复现 |
| QA-03 | MEDIUM | RTL 仅限制 128 KiB 字节，未限制行数；逐行生成 DOM。 | 静态确认，待运行验证 |
| QA-04 | MEDIUM | AI context 不包含问题/两项授权；编辑后可能保留旧请求结果。 | 静态确认，待 Mock 浏览器验证 |
| QA-05 | MEDIUM | 后端 regex/splitlines 与前端 token/split("\n") 不一致，特殊标识符及 CR 换行关联可能不一致。 | 静态确认 |
| QA-06 | MEDIUM | 总线标签直接 slice(0,24)，没有省略标记/完整 tooltip；可覆盖邻段。 | 静态确认 |
| QA-07 | MEDIUM | 1 tick 窗口向前平移半 tick 后 round 回原处；极大 tick 半整数缩放不可靠。 | 静态确认，待浏览器验证 |
| QA-08 | MEDIUM | 重复同值记录消耗绘图段预算；同时间戳记录扫描量不由段预算约束。 | 静态确认，待性能测量 |
| QA-09 | MEDIUM | 同时间戳零时长变化及窗口最右端变化不形成可见持续段；零长度 trace 轴可能显示范围外 tick。 | 静态确认；事件清单/当前值仍保留原始记录 |
| QA-10 | MEDIUM | 每次 cursor 更新重复序列化完整 RTL，重算名称匹配和语法着色。 | 静态确认，待测量 |
| QA-11 | MEDIUM | 取消上传不能保证终止后台解析；完成后仍可加入缓存并驱逐旧 trace。AI busy 检查前同步分析。 | 静态线索 |
| QA-12 | LOW | reset.value 类型缺少 null，未记录值展示不明确。 | 静态确认 |
| QA-13 | LOW | 提问没有 2000 字符限制；结构化 422 被简化为通用错误。 | 静态确认 |
| QA-14 | LOW | AI summary 恰为4000字符，添加推测前缀后会超长。 | 静态确认 |
| QA-15 | LOW | AI Mock 关联代码 fixture 字段与真实返回结构不一致。 | 静态确认 |

已有防护：严格输入 schema、上传/事件/位宽上限、Origin/Host 限制、React 文本渲染、AI 密钥仅后端、独立 RTL 授权、事实覆盖与引用白名单。它们不等于公开部署安全审计或模型语义可靠性证明。

## 修复与复验

本次修改后实际执行：后端 145 passed（1 条依赖弃用警告）、前端 9 passed、Playwright 7 passed；额外真实浏览器主流程 7/7、边界检查 8/8，详见 `evidence/automated-final.json` 和 `evidence/browser-boundaries-final.json`。

| ID | 最终处理 | 复验与残余边界 |
| --- | --- | --- |
| QA-01 | 已修复 | scope/ref/id_code 256字符，完整名1024，累计名称128 Ki字符；小型原攻击形状通过真实UI上传收到明确拒绝，后端另有累计/边界回归 |
| QA-02 | 已修复（收紧支持范围） | 含dumpoff整体422拒绝；真实浏览器已验证。不虚构未知事件，也不沿用旧值声称确定 |
| QA-03/05 | 已修复 | RTL每页200行，全文过滤搜索保留原行号；10,001行CR输入定位10001行；前后端ASCII边界及splitlines语义对齐，escaped identifier由后端回归覆盖 |
| QA-04/13 | 已修复 | 问题/两项授权均参与上下文，变更取消等待并清除旧结果；textarea限制2000；验证错误保留字段/msg但不回显input；浏览器Mock验证问题修改和撤销同意，未调用第三方 |
| QA-06 | 已修复 | 按段宽显式省略号、限制文本长度、SVG title保留完整值；256bit尾部xz在bin/hex/dec仍完整保留，浏览器实测 |
| QA-07 | 已修复 | 整数步长至少1，缩放先定安全整数宽度再夹紧；UI实测1tick左右平移及MAX_SAFE_INTEGER |
| QA-08 | 部分优化，剩余性能限制 | 绘图合并同值段、二分跳过同tick组，并memoize可见段；不修改原始事件。仍可能线性扫描100k不同时间的同值记录，受解析事件上限约束 |
| QA-09 | 明示限制，修复零长度轴 | 零长度trace轴全部0；右端当前值和同tick原始记录经UI确认；持续图仍不提供delta-cycle/瞬时事件专用标记，不宣称平线无变化 |
| QA-10 | 部分优化 | App/AI context不再序列化完整源码，仅不可变trace ID+追加源码数量；所选signal数组memoize；每source每分析只split一次。仍无持久源码索引/Canvas，性能限制保留 |
| QA-11 | 已加固，有取消限制 | 上传解析后检查断开再remember；AI先busy admission，再线程分析，finally释放。后台CPU线程无法强制中止，取消等待不保证远端停止；相关后端回归通过 |
| QA-12/14/15 | 已修复 | reset值类型允许null并显示尚无记录；summary前缀纳入4000字符预算；AI关联fixture使用真实字段；后端测试通过 |

未做大型架构重写，未改CI配置，未提交或发布。Explorer最多512项的分组拷贝、源码匹配扫描与SVG较大输入延迟记录为低/中优先级改进，不以新增抽象掩盖性能边界。依赖漏洞审计没有得到有效结果，见 release-checklist.md。

首次边界驱动对SVG title误用innerText导致1项驱动失败，记录保存在 `browser-boundaries-driver-error.json`；改用textContent后8项通过。没有削弱产品断言或删除失败记录。
