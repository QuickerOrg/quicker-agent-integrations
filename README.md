# Quicker Agent Integrations

让 Codex、Cursor、DeepSeek Harness 等外部 Agent 调用本机 Quicker，编写和使用自动化动作。

这个仓库集中维护各平台插件、安装与更新工具、MCP 接入约定、开发指南和契约测试。插件通过 Quicker 的公开接口工作，步骤知识由运行中的 Quicker 实时提供。

提供 Codex、Cursor、Claude Code、DeepSeek Harness 插件及 VS Code / Gemini CLI 的 MCP 配置安装器，采用 [MIT 许可证](LICENSE)。

## 支持情况

| 平台 | 状态 | 使用范围 |
| --- | --- | --- |
| Codex | 已实现，v0.2.0 | Windows；读取知识、编写/保存草稿、预览 |
| Cursor | 本地插件；CLI 真实写动作通过 | Windows；技能、草稿创建/保存/预览 |
| Claude Code | 原生插件，v0.2.1 | v0.2.0 公开市场安装和真实 MCP 连接通过；模型写动作待验收 |
| VS Code / Copilot、Gemini CLI | 配置安装器 | 默认 Windows 用户配置；尚未完成各客户端写动作验收 |
| DeepSeek Harness | DSH bundle 插件 | Windows；安装包与转接已实现，真实 DSH 会话写动作待验收 |

需要使用设置 → Agent 中带「启用 MCP」入口、并包含默认技能包发现修复的 Quicker 新构建。Release 支持已实现，待包含这些变更的正式版发布；已发布旧版没有该入口时仍不可用。本次已验证 Debug 的草稿编写与预览，Release 配置内核测试和正式前端构建通过，正式安装包端到端仍待验收，详见[兼容性说明](docs/兼容性.md)。

## 安装 Cursor 插件

在 Windows PowerShell 中执行（需要 Git）：

```powershell
$quickerInstall = Join-Path $env:TEMP ("quicker-agent-" + [guid]::NewGuid().ToString("N"))
git clone --depth 1 https://github.com/QuickerOrg/quicker-agent-integrations.git $quickerInstall
if ($LASTEXITCODE -eq 0) {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $quickerInstall "scripts/install-client.ps1") -Client cursor
}
```

安装器把自包含插件复制到 `%USERPROFILE%/.cursor/plugins/local/quicker`，运行时不依赖临时检出。执行 **Developer: Reload Window**，再新建对话，在 Cursor 插件设置确认 Quicker 的技能及 MCP 已加载。团队策略须允许本地插件导入；同名市场插件可能优先于本地版本。本项目尚未在 Cursor 官方市场上架。

Cursor CLI 可显式加载已安装的插件：

```powershell
cursor-agent --plugin-dir "$env:USERPROFILE/.cursor/plugins/local/quicker"
```

若 PATH 中没有 `cursor-agent`，使用 Cursor CLI 安装时提供的完整命令路径。先启用 Quicker 设置 → Agent 中的 MCP 与允许写入，再让 Cursor 创建、保存并预览一个测试草稿。CLI 非交互测试还有独立的工具调用授权要求，见[各平台安装与诊断](docs/客户端安装.md)。

## 安装 Claude Code 插件

```powershell
claude plugin marketplace add QuickerOrg/quicker-agent-integrations
claude plugin install quicker@quicker-agent-integrations --scope user
```

启用 Quicker 设置 → Agent 中的 MCP 与允许写入，在 Claude Code 执行 `/reload-plugins` 或新开会话，再用 `/mcp` 检查 Quicker。首次连接需要在 Quicker 中确认 `claude-quicker-plugin` 客户端。

安装、MCP 连接和模型登录需要分别检查：

```powershell
claude plugin list --json
claude mcp list
claude auth status
```

已通过 Claude Code 2.1.263 官方清单校验、v0.2.0 公开市场安装和真实 MCP 连接检查。`Connected` 不表示模型已登录；若尚未登录，启动 `claude` 并执行 `/login`，或按组织配置完成认证，然后请求：

> 用 Quicker 写一个动作，显示“来自 Claude Code”，保存到暂存区并打开预览，不运行。

Quicker 原生插件可与官方 [codex-plugin-cc](https://github.com/openai/codex-plugin-cc) 同时安装，前者直接提供 Quicker 工具，后者从 Claude Code 委托 Codex 审查或处理代码。两者不互为依赖，Codex 登录不能代替 Claude 登录。更新、连接超时处理及验收范围见[Claude Code 安装和诊断](docs/客户端安装.md#claude-code-安装和诊断)。

## 安装 DeepSeek Harness 插件

在 Windows PowerShell 中执行（需要 Git）：

```powershell
$quickerInstall = Join-Path $env:TEMP ("quicker-agent-" + [guid]::NewGuid().ToString("N"))
git clone --depth 1 https://github.com/QuickerOrg/quicker-agent-integrations.git $quickerInstall
if ($LASTEXITCODE -eq 0) {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $quickerInstall "scripts/install-client.ps1") -Client dsh
}
```

安装器把自包含 bundle 复制到 `%USERPROFILE%/.quicker/agent-integrations/dsh`。PATH 中有 `dsh` 时会再执行 `dsh plugin --profile web add link:<该目录>`；否则把打印出的命令贴到目标 profile。开发检出可直接 `dsh plugin --profile web add link:<仓库>/plugins/quicker-dsh`。

启用 Quicker 设置 → Agent 中的 MCP 与允许写入，重启 `dsh web` 或 DSH 桌面端。首次连接确认 `dsh-quicker-plugin`。工具名为 `mcp__quicker__skill_load` 这类带命名空间的名称。可以这样开始：

> 用 Quicker 写一个动作，显示“来自 DeepSeek Harness”，保存到暂存区并打开预览，不运行。

更新、卸载和诊断见[客户端安装](docs/客户端安装.md)。本轮完成安装包、转接和隔离测试，尚未声称真实 DSH 会话已经写过动作。

## VS Code / Copilot 与 Gemini CLI

使用上述下载步骤，将安装器参数分别改为 `-Client vscode` 或 `-Client gemini`。安装器只合并自己的 MCP 项，保留其他服务与设置，token 始终由本地转接读取。

VS Code：执行 **MCP: List Servers**，启动或重启 quicker，然后在 Copilot Agent 模式试写。Gemini CLI：重启后用 `/mcp` 检查。默认配置路径、JSONC / 自定义配置的替代方式、更新与卸载见[客户端安装](docs/客户端安装.md)。本轮只验证安装与转接，未声称这些客户端已通过真实动作编写。

## 安装 Codex 插件

在 Windows 上执行以下两条 Codex CLI 命令，无需克隆本仓库或安装 Python：

```powershell
codex plugin marketplace add QuickerOrg/quicker-agent-integrations
codex plugin add quicker@quicker-agent-integrations
```

第一条添加公开 GitHub 市场，第二条安装插件。也可在添加市场后，打开 Codex 插件页面，从 Quicker Agent Integrations 来源安装「Quicker 动作助手」。已经检出源码的开发者可以运行 `.\scripts\install-codex.ps1`，它封装相同两条命令。

插件运行时需要 Windows PowerShell 5.1 和 Quicker。它不依赖 Python、Node 或 `plugin-creator`。

安装并运行受支持的 Quicker 构建，在设置 → Agent 中启用 MCP 和「允许 MCP 写入」，然后新建 Codex 任务。MCP 默认关闭，安装插件不会自动开启服务或写入权限。首次连接时，在 Quicker 的客户端同意窗口确认所显示的客户端。

可以这样开始：

> 用 Quicker 写一个动作，显示“来自 Codex”，保存到暂存区并打开预览，不运行。

动作默认保存到暂存区。支持 MCP 的 Release 构建在 Quicker 内嵌设计器中预览，不返回 HTTP URL；只有 Debug + Vite 时才可能返回浏览器 URL。正式保留到场景、覆盖原动作或执行动作，由用户要求和 Quicker 的审批机制决定。

## 连接方式

```text
Agent 平台插件
    → 本地 MCP 转接
    → Quicker MCP：127.0.0.1 + Bearer
    → 查询知识 / 编辑动作草稿 / 保存 / 预览
```

各安装包内的 PowerShell 脚本在每次请求时读取本机 Quicker 的端口和 token，不把 token 写入插件、命令行或 Codex 配置；只请求 loopback，不使用代理或跟随重定向。它不修改 Quicker 的授权设置。

查看安装状态：

```powershell
codex plugin list --marketplace quicker-agent-integrations --json
```

需要连接诊断时，将下方占位符换成安装命令返回的实际插件目录：

```powershell
Push-Location -LiteralPath "<实际插件安装目录>"
try {
    powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\scripts\quicker-mcp.ps1 -Check
} finally {
    Pop-Location
}
```

它只显示开关、端口、token 是否存在和端口可达性；`ok=true` 仅说明配置与 TCP 可达，不代表客户端已授权或能够写动作。

## 更新和卸载

更新市场快照后重新安装插件：

```powershell
codex plugin marketplace upgrade quicker-agent-integrations
codex plugin add quicker@quicker-agent-integrations
```

更新后新建 Codex 任务。卸载命令：

```powershell
codex plugin remove quicker@quicker-agent-integrations
```

如果曾安装早期的 `quicker@personal` 原型，在新版本安装成功后移除旧原型，避免重复加载：`codex plugin remove quicker@personal`。

## 仓库结构

```text
.agents/plugins/
  marketplace.json       Codex Git 市场入口
plugins/
  quicker/               Codex 完整安装单元
  quicker-dsh/           DeepSeek Harness bundle
docs/
  接入约定.md             跨平台协议、权限、错误及动作编写约定
  新增平台.md             新平台开发和验收流程
  兼容性.md               已实现能力、限制及验证状态
scripts/
  install-codex.ps1       GitHub 市场安装助手
tests/
  test_quicker_mcp.py     独立的传输契约测试
```

Cursor、Claude 和 Codex 分别由自己的 marketplace 清单声明包路径。DeepSeek Harness 使用 `plugins/quicker-dsh` 的 `dsh.bundle` 清单，不走那些市场。`shared/` 是传输与写动作技能的唯一源码，`python scripts/sync-packages.py` 同步到各自包含安装包，`--check` 在 CI 验证无漂移。

## 开发与验证

```powershell
python -m unittest discover -s tests -v
```

测试读取安装包的实际 MCP 启动配置，在 Windows 上启动真实 PowerShell 5.1 与隔离 loopback HTTP fixture，并覆盖 Codex 缓存路径以及中文、空格目录。无需运行 Quicker，也无需访问用户配置或主产品仓库。非 Windows 环境会跳过当前传输测试；不能把跳过视为验证成功。

新增平台先读[接入约定](docs/接入约定.md)和[新增平台](docs/新增平台.md)。贡献者与 Agent 的仓库工作规则见 [AGENTS.md](AGENTS.md)。

每次 Release 提供所有平台的独立 ZIP、完整安装包、发布清单和校验和；即使只更新一个插件也不省略其他平台。发布维护者使用[统一打包与验证流程](docs/发布.md)，从指定 tag 生成并校验全部附件。

参考：[OpenAI 插件打包规范](https://developers.openai.com/plugins/build/plugins)、[Cursor 插件规范](https://cursor.com/docs/reference/plugins)。
