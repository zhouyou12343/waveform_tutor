# Waveform Tutor v0.1.0 Release Candidate 验收结论

## 1. 总体状态

**READY WITH LIMITATIONS — 本机离线教学候选可继续使用与评审。** 核心功能、独立数字正确性、真实浏览器和修复回归已实测通过；这不表示可以跳过发布门槛。真实AI、依赖漏洞数据库检查、Git历史和远程CI仍未验证，公开发布未授权且未执行。

## 2. 已完成工作

- 重新核对环境、服务和依赖，不沿用旧交付的测试数量；保存修改前源码快照与最终文件哈希。
- 三路只读审查后记录问题，小型API输入复现名称膨胀与停录旧值，再修复。
- 重启后端，以真实Chromium验证Counter/FIFO/Handshake、上传、光标、选择、搜索、RTL、报告和失败恢复。
- 用独立人工整数模型/边界表与可信Icarus仿真验证七类数字场景，包含非时钟沿异步复位和沿前/沿后握手差别。
- 测量300/15,000/99,999事件输入的HTTP耗时、RSS采样、浏览器交互；整理19题AI基准。
- 更新双语README、限制/API说明；清理公开文档/生成证据的本机项目路径，忽略基线快照和可重建大文件。

完整分报告：[功能](functional-test-report.md)、[正确性](correctness-report.md)、[AI](ai-provider-report.md)、[代码审查](code-review-report.md)、[性能](performance-report.md)、[发布清单](release-checklist.md)。

## 3. 本次实际测试结果

| 检查 | 结果 | 实际执行 |
| --- | --- | --- |
| 后端pytest | 145通过，0失败，1条依赖弃用警告 | 是 |
| 前端单测 | 9通过，0失败 | 是 |
| Playwright | 7通过，0失败；4真实API+3Mock | 是 |
| 独立数字检查 | 80通过，0失败；另1项PID一致性通过 | 是 |
| 浏览器主流程/边界 | 7/7组及8/8组通过；AI传输明确Mock | 是 |
| Icarus仿真 | 3个内置案例+1个固定自写fixture，退出0 | 是 |
| 构建/类型/格式/lint/pip check | 全通过 | 是 |
| 三档性能 | 测量完成，无SLA达标承诺 | 是 |
| 真实AI | BLOCKED，未调用 | 否 |
| npm/Python漏洞检查 | BLOCKED，未获得数据库结论 | 尝试审计/工具检查，不是完成扫描 |
| GitHub远程CI | 未执行 | 否 |

计数粒度不同，有覆盖重叠，不合并成一个总数。可重放命令及stdout/stderr见 `evidence/automated-final.json`，运行观察见两个browser-final证据。首次额外驱动失败是SVG读取API误用，已保留失败证据并修正重跑；未删断言或伪造通过。

## 4. 发现与修复

- HIGH名称资源膨胀：增加单标识符、完整名、累计名称预算；原小型输入现在被明确拒绝。
- 停录语义：不支持`$dumpoff`时整体拒绝，不继续展示旧确定值。
- RTL：每页200行，全文搜索保留行号；CR分行、特殊名称匹配在前后端对齐。
- 导航：单tick双向平移和MAX_SAFE_INTEGER附近缩放采用整数运算；零时长轴不制造范围外时间。
- 波形：同值绘图段合并，同tick组二分跳过但原始记录不丢；宽总线有省略号及完整值提示。
- AI：问题/授权变化清理旧结果，2000字符限制；4000字符summary前缀预算；busy admission及取消路径加固。
- UI/API：无reset记录明确显示；结构化422保留字段/msg；减少重复完整源码序列化和分行。

## 5. 尚未解决

详见 [unresolved-issues.md](unresolved-issues.md)。主要事项：

- **HIGH验证缺口**：npm审计端点HTTP404、Python审计工具缺失，不能宣称无漏洞；公开发布前补齐。
- **MEDIUM**：真实AI未实测；近上限性能迟滞；持续图不显示零时长脉冲；取消不保证停止CPU或第三方处理；远程CI和Git历史无证据。
- **LOW**：RTL仍启发式、依赖弃用警告、Python制品hash锁缺失、跨平台/全面可访问性/正式安全审计未完成。

性能实测：7,488,965 bytes / 99,999事件，上传p50/p95约4.40/4.63s；analysis p50/p95约19.49/21.92ms；RSS采样最大322,256KiB（非精确峰值）。浏览器单样本上传到事实约5.65s、Zoom约0.61s、cursor到事实约0.74s。保持教学小规模定位，不提高现有限额。

## 6. 真实截图

已打开查看实际截图，不是设计稿：

- [首页](../screenshots/qa-home.png)
- [Counter工作台](../screenshots/qa-counter.png)
- [FIFO](../screenshots/qa-fifo.png) / [Handshake](../screenshots/qa-handshake.png)
- [RTL分页与搜索](../screenshots/qa-rtl-paged.png)
- [宽总线X/Z](../screenshots/qa-wide-bus.png)
- [上传错误](../screenshots/qa-upload-error.png) / [停录拒绝](../screenshots/qa-dump-rejected.png)
- [390px窄屏](../screenshots/qa-mobile.png)

## 7. 发布状态

| 阶段 | 状态 |
| --- | --- |
| 本地实现/修复/验收材料 | 已完成，明确保留限制 |
| Git初始化与提交 | 未执行；当前无.git |
| GitHub仓库创建/推送 | 未执行 |
| 远程GitHub Actions | 未运行；只做本地YAML及对应命令检查 |
| Release/公开部署 | 未执行、未授权 |

本地服务仍可访问 `http://127.0.0.1:5173`，后端 `http://127.0.0.1:8000`。保留loopback，不作为公网服务。

## 8. 真正需要所有者参与的事项

1. 若要验收真实AI，由所有者选择供应商，在后端安全配置并明确授权一次非敏感Counter请求；不在聊天提供密钥，未经批准不批量执行19题或产生费用。
2. 提供可用、受信任的漏洞审计环境或允许隔离安装审计工具；无需任何AI凭证。
3. 需要提交或公开时，明确授权Git初始化/提交、目标仓库与可见性、推送范围；之后才能获得首次真实远程CI结果，再决定Release。

其余本地修改和证据记录已完成，不要求用户手工重做本次测试。
