# Install directly from the published Git marketplace. No Python or build step.
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Get-Command codex -ErrorAction Stop | Out-Null
& codex plugin marketplace add 'QuickerOrg/quicker-agent-integrations'
if ($LASTEXITCODE -ne 0) { throw 'Could not add the Quicker plugin marketplace.' }
& codex plugin add 'quicker@quicker-agent-integrations'
if ($LASTEXITCODE -ne 0) { throw 'Could not install the Quicker plugin.' }
Write-Host 'Quicker is installed. Start a new Codex task to load its skills and MCP tools.'
