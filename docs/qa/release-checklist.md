# 发布候选检查

## 最终整合更新

**READY WITH LIMITATIONS 仅限本机离线教学候选；外部公开发布尚未获授权，依赖漏洞验证仍是发布门槛。** 下方只读检查是修复前阶段记录，不是最终源码快照。

- [x] 先记录只读问题，再修复；最终源码/证据清单 `evidence/candidate-manifest.json`。
- [x] 后端145 passed、前端9 passed、Playwright7 passed；额外浏览器主流程7组与边界8组通过；独立数字80项加1项PID检查通过。
- [x] Ruff/格式、TypeScript、生产构建、pip check通过；本地CI YAML解析有backend/frontend两个job。**远程CI未执行。**
- [x] delivery绝对本机路径已清理，生成JSON项目路径已脱敏；`.qa-baseline`、sim.out及可重建的性能VCD已ignore。
- [x] 最终候选文本+JSON模式扫描无命中，相对文档链接无缺失；精确文件数/边界见 `evidence/release-final-scan.json`。不是无秘密保证，不含Git历史或图片OCR。
- [x] 真实截图已读取，性能、正确性、功能、代码审查、AI基准、未解决清单均有报告。
- [ ] npm漏洞数据库结果：审计HTTP404，BLOCKED。
- [ ] Python漏洞数据库结果：工具不可用，BLOCKED。
- [ ] 真实AI：未配置、未调用，19题未评分；保持可选实验能力。
- [ ] Git历史与首次远程CI：目录无Git，未创建仓库或推送。
- [ ] 最终实际发布制品的传递许可证/NOTICE核对；安装依赖有元数据不等于法律审计。
- [ ] 提交/推送/远程Release/公开部署：均未执行，必须用户明确授权。

最终功能结果见 [functional-test-report.md](functional-test-report.md)，残余问题见 [unresolved-issues.md](unresolved-issues.md)。没有安装全局审计工具、修改registry配置或更改CI来绕过阻塞。

## 以下为修复前只读阶段记录

日期：2026-11-16。范围：独立 AI 合同、依赖元数据、可用漏洞审计、候选文本敏感扫描。不修改 app/test/CI，不提交、不发布；不是完整安全审计或法律意见。

## 总结

**当前不能签署“全部通过/全面安全/AI实测通过”。** AI真实模型、Python漏洞审计、npm漏洞结果和Git历史/远程CI均有阻塞。下列本地通过项不能替代这些检查。

| 项目 | 状态 | 精确结果 |
| --- | --- | --- |
| AI/API现有Mock与离线测试 | PASS（限定范围） | 64 passed，1 warning，0.82s；UTC 14:50:46–14:50:48；Python 3.14.3 |
| 真实AI能力/准确率/提供商兼容性 | BLOCKED | 已确认3个AI变量未配置，health.ai_configured=false；没有真实模型评分，无密钥搜索 |
| npm audit --json | BLOCKED | exit 1；audit endpoint HTTP **404**，未得到漏洞统计；不是零漏洞。不能简单归因为DNS失败，未观察到ENOTFOUND等诊断码 |
| Python漏洞审计 | BLOCKED | 项目Python无pip_audit/safety模块，PATH无pip-audit/safety；未安装工具，无漏洞数据库结果 |
| 前端直接依赖锁与许可证元数据 | PASS（元数据范围） | lockfileVersion=3；13个直接运行/开发依赖均有锁版本、integrity；根锁声明与package.json相同 |
| 后端requirements版本/许可证元数据 | PASS（元数据范围） | 26项全部==固定版本，安装版本26/26一致；未按运行/开发/传递依赖分组，保守核对全部26项 |
| Python制品哈希锁 | 未满足 | requirements没有--hash；精确版本不等于制品完整性验证 |
| 候选文本敏感扫描 | 有待处理项 | 55文件；1个本机绝对路径命中，未命中所定义的密钥形状/私钥头/凭据字面量模式；不等于没有秘密 |
| ignore | 待主代理处理 | .env/.env.*、.venv、node_modules、dist、.claude等已忽略；本次读取时.qa-baseline尚未忽略 |
| Git历史/remote CI | BLOCKED | 无.git；无历史扫描、远程分支/检查状态或提交版本证据 |
| 最终全套/浏览器/模拟器复验 | 本任务未执行 | 后端由另一代理修复；主代理负责最终候选版本复验 |

## 依赖锁与许可证核查

来源：前端package.json/package-lock.json；Python requirements与本地已安装distribution metadata。安装目录仅用于依赖元数据检查，**不属于敏感扫描范围**。不验证registry制品来源、上游签名或包内容真实性。

| 前端直接依赖 | 锁定版本 | 元数据许可证 |
| --- | --- | --- |
| react / react-dom | 19.3.1 / 19.3.1 | MIT |
| @playwright/test | 1.65.1 | Apache-2.0 |
| @tailwindcss/vite / tailwindcss | 4.3.5 / 4.3.5 | MIT |
| @types/node | 22.20.5 | MIT |
| @types/react / @types/react-dom | 19.3.0 / 19.3.0 | MIT |
| @vitejs/plugin-react | 6.3.0 | MIT |
| prettier | 3.10.1 | MIT |
| tsx | 4.23.15 | MIT |
| typescript | 5.9.3 | Apache-2.0 |
| vite | 8.3.8 | MIT |

@types/*、tsx、typescript的package.json采用范围，发布复现应使用npm ci及现有lock，不应只按范围重新解析。其他直接声明为精确版本。未把“有integrity字段”误报为实际下载校验通过。

后端主要直接使用项：FastAPI 0.163.1 MIT、Pydantic 2.14.3 MIT、PyVCD 0.5.1 MIT、python-multipart 0.0.34 Apache-2.0、HTTPX 0.28.1 BSD-3-Clause、Uvicorn 0.54.0 BSD-3-Clause；开发工具pytest 9.2.0 MIT、pytest-asyncio 1.5.0 Apache-2.0、ruff 0.17.5 MIT。完整26项逐条版本和许可证见JSON。

分发时特别注意元数据中的 **certifi MPL-2.0**、typing_extensions PSF-2.0、packaging Apache-2.0 OR BSD-2-Clause，不能统一标成项目MIT。docs/dependencies.md说明其清单不穷尽，方向正确。Icarus是可选外部工具，文档标注GPL-2.0-or-later，本次没有核验其安装制品或分发安排。此核查不覆盖全部npm传递依赖许可证、浏览器运行时和构建产物NOTICE义务，也不是法律兼容性保证。

## 敏感扫描边界与结果

- 使用显式扩展名/顶层文件白名单，对候选文本源码、配置、文档、例子共55文件扫描，并记录路径和SHA-256清单；无.git，因此此清单不是Git tracked清单或最终发布归档清单。
- 排除.env*（连.env.example也未打开）、.venv/venv、node_modules、.claude、.qa-baseline、.git、dist、Python/tool缓存、浏览器测试产物、二进制图片、生成的docs/qa证据；不追随符号链接。
- 规则：常见token形状、私钥头、带引号的凭据赋值、本机绝对路径。输出只含文件位置/行号/类别/分诊，不输出匹配内容或可能secret值。
- 唯一命中：`docs/delivery.md:99`，类别`local_absolute_path`，**主代理需清理**。
- 测试代码中人工Mock凭据和README中的配置占位说明不是已确认泄露；本次静态阅读已区分测试/示例用途，没有将其列为真实密钥。扫描不会覆盖所有构造函数位置参数或所有凭据编码，零token命中不是无秘密证明。
- README明确.env.example只是模板、不自动加载；由于.env*按要求完全排除，本次不声称已验证模板实际内容安全。
- JSON测试输出/命令含本地运行路径，用于受限QA证据，不包含secret值；若把QA证据公开分发，主代理应另行脱敏路径。证据目录本身未纳入此次候选源码扫描。
- 未扫描历史、被忽略的用户文件、图片OCR、全熵值或最终打包归档。扫描后发生的变更不在本次清单保证范围内。

## 执行命令与证据

工作目录为项目根；绝对命令、测试输出、前后SHA-256、元数据写入 `evidence/ai-release-checks.json`。只创建本报告、AI报告和JSON证据，未修改应用、测试、CI或ignore。

```sh
.venv/bin/python -B -m pytest -q -p no:cacheprovider backend/tests/test_ai.py backend/tests/test_api.py
npm --prefix frontend audit --json --fetch-retries=0 --fetch-timeout=20000
```

npm审计为辨别错误做了重复诊断；只保留HTTP状态、固定诊断词、退出码和结构化结果，不保留可能含内部registry信息的原始headers/body。404说明审计端点不可用，不能报告数据库检查已完成；后续需在可用的受信任registry/网络环境重跑，本次没有更改npm配置。

Python可用性检查通过importlib.util.find_spec('pip_audit'/'safety')和shutil.which('pip-audit'/'safety')；全为false。许可证/版本通过importlib.metadata.distribution读取；前端通过JSON解析锁文件。敏感扫描通过Python os.walk在进入目录前剪枝，逐行re匹配，只输出位置与类别，完整清单见 `evidence/release-source-scan.json`。没有请求密钥或安装全局工具。

## 主代理 / 所有者待处理

- [ ] 主代理清理docs/delivery.md的绝对本机路径；将.qa-baseline加入ignore（本任务未代改）。
- [ ] 主代理完成后端修复后，重新跑全套pytest、lint/format、前端build/typecheck/test、浏览器验收和相关仿真；更新候选哈希及报告，不能仅引用本次64项结果。
- [ ] 在可用审计端点重跑npm audit；本次HTTP404不允许替换成“0 vulnerabilities”。
- [ ] 经批准在隔离环境提供Python漏洞审计工具，对固定requirements审计；无需在聊天中提供任何密钥。
- [ ] 如要求AI发布验收，由所有者自行安全配置provider并授权数据共享，再执行AI报告19题基准；目前没有模型得分。
- [ ] 有Git仓库后检查最终tracked文件、历史秘密扫描和真实远程CI；当前无.git不能作任何通过声明。
- [ ] 对最终实际分发的依赖/运行时/制品补许可证与NOTICE核对；公开QA证据前脱敏本机路径并重扫最终发布归档。

没有提交、推送、发布或修改CI；以上不承诺全面安全。
