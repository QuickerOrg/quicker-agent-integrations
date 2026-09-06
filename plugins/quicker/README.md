# Quicker 动作助手

让 Codex 通过本机 Quicker 编写、保存并预览自动化动作。版本 0.1.1，MIT 许可证。

安装：

```powershell
codex plugin marketplace add QuickerOrg/quicker-agent-integrations
codex plugin add quicker@quicker-agent-integrations
```

需要已有带 MCP 设置入口的 Quicker Debug 构建。在设置中启用 MCP 和「允许 MCP 写入」，然后新建 Codex 任务。首次连接在 Quicker 的客户端同意窗口确认所显示的客户端。当前 Quicker Release 尚不提供 MCP。

示例：用 Quicker 写一个动作，显示“来自 Codex”，保存到暂存区并打开预览，不运行。

本包自包含，运行时依赖 Windows PowerShell 5.1。脚本只从本机读取 MCP 配置，不携带 token，也不修改授权设置。

[源码、更新与排错](https://github.com/QuickerOrg/quicker-agent-integrations)
