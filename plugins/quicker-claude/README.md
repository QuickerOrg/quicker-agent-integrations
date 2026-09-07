# Quicker Claude Code 插件

版本：0.2.1。需要 Windows PowerShell 5.1、Claude Code，以及设置 → Agent 中带「启用 MCP」入口的本机 Quicker。此目录包含完整转接与技能，运行时不依赖开发检出、Git、Python 或 Node。

## 安装和开始编写

```powershell
claude plugin marketplace add QuickerOrg/quicker-agent-integrations
claude plugin install quicker@quicker-agent-integrations --scope user
```

启用 Quicker 设置 → Agent 中的 MCP 与允许写入，然后在 Claude Code 执行 `/reload-plugins` 或新开会话。首次连接时，在 Quicker 中确认 `claude-quicker-plugin` 客户端；安装本身不授予执行或覆盖权限。

分别检查安装、连接和模型登录：

```powershell
claude plugin list --json
claude mcp list
claude auth status
```

插件应为 `quicker@quicker-agent-integrations` 且已启用，MCP 应显示 `plugin:quicker:quicker` 与 `Connected`。这两项成功仍不代表 Claude 已登录；若显示未登录，启动 `claude` 并执行 `/login`，或按组织配置完成[官方认证](https://code.claude.com/docs/en/authentication)。在 `/mcp` 中检查工具后，可直接请求：

> 用 Quicker 写一个动作，显示“来自 Claude Code”，保存到暂存区并打开预览，不运行。

也可以在 Claude 会话执行 `/quicker:write-action` 加上需求。结果默认保存为草稿；正式保留、覆盖原动作或运行由用户要求及 Quicker 审批决定。

## 更新、卸载和诊断

```powershell
claude plugin marketplace update quicker-agent-integrations
claude plugin update quicker@quicker-agent-integrations --scope user
```

更新后执行 `/reload-plugins` 或新开会话。卸载使用 `claude plugin uninstall quicker@quicker-agent-integrations --scope user`。

首次连接超时时，先查看 Quicker 的客户端同意窗口；需要更长启动等待可按[客户端安装与诊断](https://github.com/QuickerOrg/quicker-agent-integrations/blob/main/docs/客户端安装.md#claude-code-安装和诊断)临时设置 `MCP_TIMEOUT`。HTTP 403 表示 Quicker 端同意未完成；Claude 未登录或拒绝工具调用则应在 Claude 端处理。不要修改 Quicker 配置文件来授予权限。

本插件直接向 Claude 提供 Quicker MCP，不依赖 `codex@openai-codex`。可同时安装官方 [codex-plugin-cc](https://github.com/openai/codex-plugin-cc)，按其说明用 `/codex:setup` 检查 Codex；Codex 登录与 Claude 登录互相独立。Quicker 写动作使用 `quicker` 工具，委托 Codex 审查代码使用 `/codex:review`。

各版本真实验收范围见[兼容性说明](https://github.com/QuickerOrg/quicker-agent-integrations/blob/main/docs/兼容性.md)。

传输脚本与技能由 shared/ 生成；维护时运行 scripts/sync-packages.py，不手工修改副本。
