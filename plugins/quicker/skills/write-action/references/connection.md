# Connection troubleshooting

This plugin runs on Windows with Windows PowerShell 5.1. Its local stdio relay forwards the running Quicker Debug application's existing Streamable HTTP MCP interface. It does not start Quicker or provide an alternate action engine.

Run the bundled diagnostic using the actual installed plugin root:

```powershell
powershell.exe -NoProfile -File "<plugin-root>/scripts/quicker-mcp.ps1" -Check
```

The relay reads `%USERPROFILE%/.quicker/mcp/server.json` for the port and bearer token on each request. It connects only to 127.0.0.1, does not follow redirects or use an HTTP proxy, and never writes the token into plugin files. Do not print the configuration file, token, HTTP authorization header, or clients.json in tool results or the conversation.

- Missing configuration or disabled MCP: use a Debug Quicker build and enable MCP in Quicker settings. Current Release builds have no MCP listener.
- Cannot connect: ensure that the Debug application is running and its configured MCP port is listening.
- HTTP 401: authentication was rejected. Retry a read after checking the currently running Quicker instance; token rotation is picked up on the next request.
- HTTP 403: Quicker denied client consent. The user must approve the intended client through Quicker's own UI.
- Read tools present, write tools absent: enable 允许 MCP 写入 in Quicker settings, then start a new Codex task to rediscover tools. Keep the existing Quicker approval mode.
- First connection waiting: check for Quicker's local client consent window. The plugin allows a bounded wait for consent; it does not auto-approve.

After installing or updating this plugin, start a new Codex task to load its skills and tools. A task that started before installation may not have them.
