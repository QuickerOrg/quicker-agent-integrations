# Quicker DeepSeek Harness 插件

版本：0.2.0。需要 Windows PowerShell 5.1、已安装的 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（`dsh` CLI 或桌面端），以及设置 → Agent 中带「启用 MCP」入口的本机 Quicker。此目录是完整 DSH bundle：写动作引导、stdio 转接，以及把 `@deepseek-ai/dsh-mcp-client` 接到本机 Quicker 的入口。运行时不依赖开发检出。

## 安装

在 Windows PowerShell 中执行（需要 Git）：

```powershell
$quickerInstall = Join-Path $env:TEMP ("quicker-agent-" + [guid]::NewGuid().ToString("N"))
git clone --depth 1 https://github.com/QuickerOrg/quicker-agent-integrations.git $quickerInstall
if ($LASTEXITCODE -eq 0) {
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $quickerInstall "scripts/install-client.ps1") -Client dsh
}
```

安装器把自包含包复制到 `%USERPROFILE%/.quicker/agent-integrations/dsh`。若 PATH 中有 `dsh`，会再执行：

```powershell
dsh plugin --profile web add link:$env:USERPROFILE\.quicker\agent-integrations\dsh
```

没有 CLI 时，把上面的 `add` 命令复制到已初始化的 profile（`web` 或 `desktop`）后执行。开发检出可直接：

```powershell
dsh plugin --profile web add link:<本仓库>/plugins/quicker-dsh
```

启用 Quicker 设置 → Agent 中的 MCP 与允许写入，然后重启 `dsh web` 或 DSH 桌面端。首次连接在 Quicker 中确认 `dsh-quicker-plugin` 客户端。安装本身不授予执行或覆盖权限。

可以这样开始：

> 用 Quicker 写一个动作，显示“来自 DeepSeek Harness”，保存到暂存区并打开预览，不运行。

Quicker 工具在 DSH 中的名称带命名空间，例如 `mcp__quicker__skill_load`、`mcp__quicker__quicker_create`。默认保存到暂存区；正式保留、覆盖或运行由用户要求和 Quicker 审批决定。

## 更新、卸载和诊断

重新下载仓库并再次运行安装器即可更新。卸载：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/install-client.ps1 -Client dsh -Uninstall
```

若曾手动 `dsh plugin add`，卸载时也会尝试 `dsh plugin --profile web remove dsh-plugin-quicker`。

```powershell
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$env:USERPROFILE\.quicker\agent-integrations\dsh\scripts\quicker-mcp.ps1" -Check
```

`-Check` 只说明开关、端口和 TCP 可达，不代表已授权或能够写动作。不要修改 Quicker 的 `server.json` / `clients.json` 来授予权限。

传输脚本与技能由 shared/ 生成；维护时运行 `python scripts/sync-packages.py`，不手工修改副本。
