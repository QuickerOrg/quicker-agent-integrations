# Quicker Agent Integrations

让 Codex、Cursor 等外部 Agent 调用本机 Quicker，编写和使用自动化动作。

这个仓库集中维护各平台插件、安装与更新工具、MCP 接入约定、开发指南和契约测试。插件通过 Quicker 的公开接口工作，步骤知识由运行中的 Quicker 实时提供。

Codex 插件 `quicker` 已提供 GitHub 市场安装入口，采用 [MIT 许可证](LICENSE)。Cursor 接入列入后续工作。

## 支持情况

| 平台 | 状态 | 使用范围 |
| --- | --- | --- |
| Codex | 已实现，v0.1.1 | Windows；读取知识、编写/保存草稿、预览 |
| Cursor | 计划接入 | 待开发和实机验证 |
| 其他 Agent | 按需求扩展 | 先确认其 MCP 和插件机制 |

当前 Quicker 只有 Debug 版开放 MCP；Release 没有入口，也不监听。完整状态及验收标准见[兼容性说明](docs/兼容性.md)。

## 安装 Codex 插件

在 Windows 上执行以下两条 Codex CLI 命令，无需克隆本仓库或安装 Python：

```powershell
codex plugin marketplace add QuickerOrg/quicker-agent-integrations
codex plugin add quicker@quicker-agent-integrations
```

第一条添加公开 GitHub 市场，第二条安装插件。也可在添加市场后，打开 Codex 插件页面，从 Quicker Agent Integrations 来源安装「Quicker 动作助手」。已经检出源码的开发者可以运行 `.\scripts\install-codex.ps1`，它封装相同两条命令。

插件运行时需要 Windows PowerShell 5.1 和 Quicker。它不依赖 Python、Node 或 `plugin-creator`。

需要已有带 MCP 设置入口的 Quicker Debug 构建；公开正式版目前不提供此入口。安装后，在 Quicker Debug 设置中启用 MCP 和「允许 MCP 写入」，然后新建 Codex 任务。首次连接时，在 Quicker 的客户端同意窗口确认所显示的客户端。

可以这样开始：

> 用 Quicker 写一个动作，显示“来自 Codex”，保存到暂存区并打开预览，不运行。

动作默认保存到暂存区。正式保留到场景、覆盖原动作或执行动作，由用户要求和 Quicker 的审批机制决定。

## 连接方式

```text
Agent 平台插件
    → 本地 MCP 转接
    → Quicker MCP：127.0.0.1 + Bearer
    → 查询知识 / 编辑动作草稿 / 保存 / 预览
```

当前 Codex 包内的 PowerShell 脚本在每次请求时读取本机 Quicker 的端口和 token，不把 token 写入插件、命令行或 Codex 配置；只请求 loopback，不使用代理或跟随重定向。它不修改 Quicker 的授权设置。

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
docs/
  接入约定.md             跨平台协议、权限、错误及动作编写约定
  新增平台.md             新平台开发和验收流程
  兼容性.md               已实现能力、限制及验证状态
scripts/
  install-codex.ps1       GitHub 市场安装助手
tests/
  test_quicker_mcp.py     独立的传输契约测试
```

后续平台在 `plugins/` 下增加安装单元，由对应平台的市场清单声明路径。每个安装包自包含；当第二个平台需要复用传输代码时，再抽取共享源码并在打包时放入各安装单元。

## 开发与验证

```powershell
python -m unittest discover -s tests -v
```

测试读取安装包的实际 MCP 启动配置，在 Windows 上启动真实 PowerShell 5.1 与隔离 loopback HTTP fixture，并覆盖 Codex 缓存路径以及中文、空格目录。无需运行 Quicker，也无需访问用户配置或主产品仓库。非 Windows 环境会跳过当前传输测试；不能把跳过视为验证成功。

新增平台先读[接入约定](docs/接入约定.md)和[新增平台](docs/新增平台.md)。贡献者与 Agent 的仓库工作规则见 [AGENTS.md](AGENTS.md)。

参考：[OpenAI 插件打包规范](https://developers.openai.com/plugins/build/plugins)、[Cursor 插件规范](https://cursor.com/docs/reference/plugins)。
