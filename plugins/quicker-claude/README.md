# Quicker claude 接入包

Windows PowerShell 5.1 + 支持 MCP 的本机 Quicker。此目录是完整运行单元，不依赖开发检出。

安装、更新、卸载和实测兼容状态见 [公开仓库](https://github.com/QuickerOrg/quicker-agent-integrations#readme) 与 [客户端安装](https://github.com/QuickerOrg/quicker-agent-integrations/blob/main/docs/客户端安装.md)。

启用 Quicker 设置 → Agent 中的 MCP 与允许写入，然后重新加载客户端并完成 Quicker 客户端授权。插件读取实时动作知识，默认把结果保存到暂存区；安装本身不授予执行或覆盖权限。运行时不需要 Git、Python 或 Node。

传输脚本与技能由 shared/ 生成；维护时运行 scripts/sync-packages.py，不手工修改副本。
