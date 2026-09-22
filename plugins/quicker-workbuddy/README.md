# Quicker WorkBuddy / CodeBuddy 插件

版本：0.2.0。需要 Windows PowerShell 5.1、WorkBuddy 或 CodeBuddy CLI，以及设置 → Agent 中带「启用 MCP」入口的本机 Quicker。此目录包含完整转接与技能，运行时不依赖开发检出、Git、Python 或 Node。

WorkBuddy 桌面与 CodeBuddy CLI 共用同一套插件引擎。安装命令是 `codebuddy`。

## 安装和开始编写

桌面端先设 `CODEBUDDY_CONFIG_DIR` 为 `%USERPROFILE%\.workbuddy`。用 GitHub `owner/repo` 或含市场清单的 zip 添加市场，不要 `marketplace add` 仓库根路径（那会链到检出，不会进 cache）：

```powershell
$env:CODEBUDDY_CONFIG_DIR = "$env:USERPROFILE\.workbuddy"
codebuddy plugin marketplace add QuickerOrg/quicker-agent-integrations
codebuddy plugin install quicker@quicker-agent-integrations --scope user
```

启用 Quicker 设置 → Agent 中的 MCP 与允许写入，然后执行 `/reload-plugins` 或新开会话。首次连接时，在 Quicker 中确认 `workbuddy-quicker-plugin` 客户端；安装本身不授予执行或覆盖权限。

分别检查安装和连接：

```powershell
codebuddy plugin list --json
codebuddy mcp list
```

插件应为 `quicker@quicker-agent-integrations` 且已启用。在 `/mcp` 或 `/plugin` 中确认 quicker 后，可直接请求：

> 用 Quicker 写一个动作，显示“来自 WorkBuddy”，保存到暂存区并打开预览，不运行。

也可以执行 `/quicker:write-action` 加上需求。结果默认保存为草稿；正式保留、覆盖原动作或运行由用户要求及 Quicker 审批决定。

不要在 WorkBuddy 设置 → MCP 里填写 Quicker 的 URL 和 token。token 由包内转接每次从本机读取。

## 更新、卸载和诊断

```powershell
codebuddy plugin marketplace update quicker-agent-integrations
codebuddy plugin update quicker@quicker-agent-integrations --scope user
```

更新后执行 `/reload-plugins` 或新开会话。卸载使用 `codebuddy plugin uninstall quicker@quicker-agent-integrations --scope user`。

首次连接超时时，先查看 Quicker 的客户端同意窗口。HTTP 403 表示 Quicker 端同意未完成。不要修改 Quicker 配置文件来授予权限。

各版本真实验收范围见[兼容性说明](https://github.com/QuickerOrg/quicker-agent-integrations/blob/main/docs/兼容性.md)。

传输脚本与技能由 shared/ 生成；维护时运行 scripts/sync-packages.py，不手工修改副本。
