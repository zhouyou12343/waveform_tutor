# Waveform Tutor v0.1.0 RC — 功能复验

日期：2026-11-16。**离线教学范围：PASS；发布候选：READY WITH LIMITATIONS。** 这不是对真实AI、依赖无漏洞、远程CI或公开部署安全的认可。外部发布仍受 `release-checklist.md` 的门槛约束。

## 环境与可复现入口

macOS，Python 3.14.3，Node 24.15.0，npm 11.12.1，Chromium 159.0.8154.6，Icarus 12.0。目录无Git元数据，使用修改前源码快照及最终SHA-256清单对照，不声称有commit或Git历史审计。服务在127.0.0.1:8000/5173；修复后明确重启后端，最终验证为PID 12757，前端Vite加载当前源码。

```sh
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --limit-concurrency 16
npm --prefix frontend run dev
```

分终端运行；已有本项目服务则无需重复启动。无AI变量也可使用全部离线能力。本次未提供、读取或发送真实密钥。

## 本次实际执行结果

| 检查 | 通过 | 失败 | 实际执行/证据 |
| --- | ---: | ---: | --- |
| 后端pytest | 145 | 0 | `evidence/automated-final.json`；1条Starlette/httpx弃用警告 |
| 前端node:test | 9 | 0 | 同上；含最大整数导航和重复记录绘图回归 |
| Playwright测试 | 7 | 0 | 同上；4个真实API场景、3个Mock场景；复用已运行服务，不是CI冷启动 |
| 主流程浏览器驱动 | 7组 | 0 | `evidence/browser-final.json` |
| 额外边界浏览器驱动 | 8组 | 0 | `evidence/browser-boundaries-final.json`；其中AI传输为明确Mock |
| 独立数字oracle | 80 | 0 | `evidence/correctness-final/results.json`；另1项PID一致性通过 |
| 可信SV仿真 | 4套 | 0 | Counter/FIFO/Handshake及自写同步/异步/XZ fixture；Icarus退出0，日志留存 |
| 类型检查、生产构建、Prettier、Ruff、Python格式、pip check | 6项 | 0 | `evidence/automated-final.json` |
| 三档性能 | 完成 | 无执行错误 | API各5次、浏览器各1次；没有预设SLA，不计为性能达标 |
| 真实第三方AI | 0 | — | BLOCKED：未配置/未调用；19题基准未评分 |
| npm/Python漏洞审计 | — | — | BLOCKED：npm审计HTTP404；Python审计工具缺失，不是零漏洞 |
| 远程GitHub CI | — | — | 未运行；未创建远程仓库、推送、发布 |

不相加上述计数作为“总测试数”：独立检查、场景组、单测和仿真具有不同粒度，且有覆盖重叠。之前交付的107/7/7仅为历史记录，不作为本次结果。

## 浏览器观察（真实产品表面）

1. 无key首页正常；Counter实际VCD层级与1ps时标正确。120000tick显示count=1010/enable=0；125000保持、205000回绕、232000复位尚未清零、235000清零。下载的真实Markdown包含选定时间/值和限制。
2. Zoom/pan真正改变窗口，搜索信号及RTL改变可见内容；RTL文件切换、名称高亮及上传通过实际浏览器验证，不是仅检查按钮存在。
3. FIFO满/拒写/空边界及Handshake背压、沿前数据和沿后sent均与独立预期一致。
4. 非法上传出现错误，下一次合法demo恢复；异常名称和dumpoff明确拒绝，不冻结页面或显示旧事实。
5. 1tick窗口可向前/向后各移动1tick；MAX_SAFE_INTEGER缩放到最后1tick并回移保持精确；零时长轴不制造tick1。
6. 同一tick两条事件均留在事件列表；右端当前值正确。持续区间图仍不会展示零时长脉冲，新增明确提示，不能用平线证明没有瞬时变化。
7. 10,001行CR源文件每页最多200行，全局搜索定位原10001行，关联高亮正确。图上256bit标签显示省略号，title保留完整含xz值，bin/hex/dec不把未知位转成数字。
8. Mock AI完成结果后修改问题会清除旧结果；在途撤销同意取消等待，旧响应不显示。输入上限2000；已发送数据不可撤回，取消不保证提供商停止。
9. 390px窄屏页面宽度仍为390px，没有整页横向溢出；长工作区需纵向滚动。未把这个结果外推为所有移动设备兼容。
10. 主流程没有JS异常或意外HTTP失败；仅非法上传预期422。边界驱动无JS异常。

首次额外浏览器驱动7/8通过，唯一失败是对SVG title使用innerText的驱动API错误；保留 `browser-boundaries-driver-error.json` 与截图，改为textContent重跑后8/8通过。曾有一处新增Python测试格式检查失败，格式化后最终检查通过。没有删测试、跳过核心断言或把首次失败抹掉。

## 截图与视觉复核

以下是真实Chromium截图，已读取查看，不是设计稿：

- [首页](../screenshots/qa-home.png)
- [Counter工作台](../screenshots/qa-counter.png)
- [Handshake](../screenshots/qa-handshake.png)
- [RTL跨页搜索](../screenshots/qa-rtl-paged.png)
- [256bit与X/Z](../screenshots/qa-wide-bus.png)
- [非法上传](../screenshots/qa-upload-error.png)
- [停录拒绝](../screenshots/qa-dump-rejected.png)
- [390px窄屏](../screenshots/qa-mobile.png)

视觉观察：深色三栏布局及信号/事实区可读；宽总线尾部不再静默丢失。窄屏是长页面，不是紧凑触屏专用波形浏览器。近上限SVG交互迟滞见性能报告。

## 复跑

从项目根目录，保持前后端运行，依次执行（勿并行这些有4-trace缓存的验收驱动）：

```sh
node scripts/qa_browser.mjs final
python3 scripts/qa_correctness.py --label final
python3 scripts/qa_performance.py --label final --samples 5
node scripts/qa_boundaries.mjs
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run test:e2e
```

独立脚本保留请求、expected/actual、输入SV/VCD、仿真日志和测量原始值。performance脚本生成的近上限VCD及sim.out不进入发布候选；源码可重建它们。`.qa-baseline`也已加入ignore。
