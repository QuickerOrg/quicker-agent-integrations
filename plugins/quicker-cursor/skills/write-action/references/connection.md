# Connection troubleshooting

Requires Windows PowerShell 5.1 and a Quicker build with Settings → Agent → Enable MCP. Both supported Debug and Release builds work; older releases without that setting do not.

Run powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<installed-package>/scripts/quicker-mcp.ps1" -Check for a redacted configuration/TCP check. This does not prove client consent or write access.

The relay reads the current port and token from the local Quicker configuration for each request. Keep the token out of commands, client configuration, logs and conversation. It uses only loopback and does not follow proxies or redirects.

- Missing/disabled MCP: open Quicker Settings → Agent and enable MCP.
- Connection refused: start the supported Quicker build and check the configured port.
- HTTP 401: check the running instance; token rotation is picked up on the next read.
- HTTP 403 or a first connection waiting: complete Quicker's consent UI for the actual connecting client. The relay never grants itself access.
- Write tools absent: enable 允许 MCP 写入 in Quicker, keep the existing approval mode, then reconnect or start a new agent task.
- A write timeout can leave an unknown outcome: inspect the slot before retrying.

After installation/update, reload the client and create a new task. Cursor IDE: Developer: Reload Window; Cursor CLI: restart agent. Claude Code: /reload-plugins or restart. VS Code: MCP: List Servers → Quicker → Restart. Gemini CLI: restart.

Plugins ship their own relay. Cursor and Claude expand their respective plugin-root variables; Codex uses package-relative cwd. Generic MCP configuration points at the installed copy, never the development checkout. Do not edit server.json or clients.json to grant access.
