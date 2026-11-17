# 依赖、工具与许可证

项目自身采用根目录 [MIT License](../LICENSE)，Copyright (c) 2026 Waveform Tutor contributors。第三方依赖不会因本项目使用 MIT 而自动改为 MIT；各自的版权声明和许可证仍适用。

以下是已核对的依赖元数据摘要，不是对所有传递依赖的穷尽清单，也不是法律意见。具体版本以实际 Python 依赖文件、前端 package.json/package-lock.json 和安装产物为准；升级后需要重新核对。

| 依赖/工具 | 主要用途 | 元数据许可证 |
| --- | --- | --- |
| React / React DOM | 前端组件与渲染 | MIT |
| Vite | 前端开发服务器与构建 | MIT |
| Tailwind CSS | 前端样式构建 | MIT |
| TypeScript | 类型检查与编译 | Apache-2.0 |
| Playwright | 浏览器端到端测试 | Apache-2.0 |
| tsx | TypeScript 的 Node 测试执行 | MIT |
| Prettier | 格式化工具 | MIT |
| FastAPI | 本地 HTTP API | MIT |
| Pydantic | 请求与解释结构校验 | MIT |
| PyVCD | VCD token 解析 | MIT |
| python-multipart | 文件上传解析 | Apache-2.0 |
| HTTPX | 可选 AI HTTP 调用 | BSD-3-Clause |
| Uvicorn | ASGI 服务器 | BSD-3-Clause |
| Icarus Verilog | 固定示例的离线编译/仿真 | GPL-2.0-or-later |

## Icarus 的边界

Icarus Verilog 是用户可选安装的**外部开发工具**。本应用不把其可执行文件打包或链接进运行时；正常打开随仓库提供的 VCD 不需要它。只有维护者运行 `scripts/generate_examples.py` 重新生成三个固定案例时才调用 `iverilog` 和 `vvp`。不得把这个脚本当作执行用户上传源码的服务。

“外部工具”描述的是当前集成方式，不构成任何发行安排的法律兼容性保证。若以后打包工具链、容器、浏览器运行时或其他依赖，应重新检查对应许可证和分发义务。

## 维护与分发检查

- 保留项目及所分发第三方组件要求的版权、许可证和 NOTICE 文本。
- 将直接依赖、传递依赖、构建产物和随包附带的运行时分别核对；开发工具不等于浏览器运行时代码。
- 安装包的元数据是线索，具体义务以组件随附许可证及实际分发方式为准。
- AI 提供商是可选外部服务，不是本项目捆绑的 SDK；使用服务另受提供商条款和数据处理政策约束。
- 不宣称已完成法律审查、所有传递依赖审计或无条件许可证兼容保证。
