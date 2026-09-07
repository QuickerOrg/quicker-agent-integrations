[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('cursor', 'vscode', 'gemini')]
    [string]$Client,
    [string]$UserRoot = [Environment]::GetFolderPath('UserProfile'),
    [switch]$Uninstall
)

# Install only our package and MCP entry; credentials stay in Quicker.
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$userPath = [IO.Path]::GetFullPath($UserRoot)
$utf8 = New-Object Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Web.Extensions
$json = New-Object Web.Script.Serialization.JavaScriptSerializer
$json.MaxJsonLength = [int]::MaxValue
$json.RecursionLimit = 256

function Get-PackageHash([string]$Path) {
    $algorithm = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '') }
    finally { $stream.Dispose(); $algorithm.Dispose() }
}

function Assert-UserPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($userPath.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Install path escaped the selected user directory.'
    }
    $probe = $full
    while ($probe -and $probe.Length -ge $userPath.Length) {
        if (Test-Path -LiteralPath $probe) {
            if ((Get-Item -LiteralPath $probe -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Installation through a symlink or junction is not supported.'
            }
        }
        $probe = Split-Path -Parent $probe
    }
    return $full
}

function Read-Json([string]$Path) {
    $value = $json.DeserializeObject([IO.File]::ReadAllText($Path))
    if ($value -isnot [System.Collections.IDictionary]) { throw "Expected JSON object: $Path" }
    return ,$value
}

function Write-Json([string]$Path, $Value) {
    [void](Assert-UserPath $Path)
    [void][IO.Directory]::CreateDirectory((Split-Path -Parent $Path))
    $temporary = $Path + '.' + [Guid]::NewGuid().ToString('N') + '.tmp'
    [IO.File]::WriteAllText($temporary, (ConvertTo-Json -InputObject $Value -Depth 100 -Compress), $utf8)
    if (Test-Path -LiteralPath $Path) {
        [IO.File]::Replace($temporary, $Path, [NullString]::Value)
    } else { [IO.File]::Move($temporary, $Path) }
}

$packageName = if ($Client -eq 'cursor') { 'quicker-cursor' } else { 'quicker-mcp' }
$relativeTarget = if ($Client -eq 'cursor') { '.cursor/plugins/local/quicker' } else { '.quicker/agent-integrations/' + $Client }
$target = Assert-UserPath (Join-Path $userPath $relativeTarget)
$markerPath = Join-Path $target '.quicker-managed.json'
$marker = $null
if (Test-Path -LiteralPath $target) {
    if (-not (Test-Path -LiteralPath $markerPath)) { throw 'An unmanaged package already exists. It was not changed.' }
    $marker = Read-Json $markerPath
    if ($marker['owner'] -ne 'QuickerOrg/quicker-agent-integrations' -or $marker['client'] -ne $Client) { throw 'Package ownership does not match.' }
    foreach ($directory in Get-ChildItem -LiteralPath $target -Recurse -Directory -Force) {
        [void](Assert-UserPath $directory.FullName)
    }
    # Preserve local edits and reject unexpected files before replacing/removing a package.
    foreach ($file in Get-ChildItem -LiteralPath $target -Recurse -File -Force) {
        [void](Assert-UserPath $file.FullName)
        $relative = $file.FullName.Substring($target.Length + 1).Replace('\', '/')
        if ($relative -eq '.quicker-managed.json') { continue }
        if (-not $marker['files'].ContainsKey($relative) -or (Get-PackageHash $file.FullName) -ne $marker['files'][$relative]) {
            throw 'The installed package contains local changes. It was not changed.'
        }
    }
}

$configPath = $null
$config = $null
$section = 'mcpServers'
$server = $null
if ($Client -ne 'cursor') {
    $relativeConfig = if ($Client -eq 'vscode') { 'AppData/Roaming/Code/User/mcp.json' } else { '.gemini/settings.json' }
    $configPath = Assert-UserPath (Join-Path $userPath $relativeConfig)
    if ($Client -eq 'vscode') { $section = 'servers' }
    $config = if (Test-Path -LiteralPath $configPath) { Read-Json $configPath } else { @{} }
    if (-not $config.ContainsKey($section)) { $config[$section] = @{} }
    if ($config[$section] -isnot [System.Collections.IDictionary]) { throw 'MCP server configuration must be an object.' }
    $server = @{
        command = 'powershell.exe'
        args = @('-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', (Join-Path $target 'scripts/quicker-mcp.ps1'), '-Client', $Client)
    }
    if ($Client -eq 'vscode') { $server['type'] = 'stdio' }
    if ($config[$section].ContainsKey('quicker')) {
        $existing = $config[$section]['quicker']
        if (-not $marker -or (ConvertTo-Json -InputObject $existing -Depth 100 -Compress) -ne (ConvertTo-Json -InputObject $marker['server'] -Depth 100 -Compress)) {
            throw 'The quicker MCP entry is not owned by this installer or was edited. It was not changed.'
        }
    }
}

if ($Uninstall) {
    if (-not $marker) { Write-Output 'Nothing installed by this installer.'; exit 0 }
    if ($configPath) {
        [void]$config[$section].Remove('quicker')
        Write-Json $configPath $config
    }
    [void](Assert-UserPath $target)
    Remove-Item -LiteralPath $target -Recurse -Force
    Write-Output "Removed Quicker integration for $Client. Reload the client."
    exit 0
}

$source = Join-Path $repo ('plugins/' + $packageName)
if (-not (Test-Path -LiteralPath (Join-Path $source 'scripts/quicker-mcp.ps1'))) { throw 'Incomplete source package.' }
foreach ($entry in Get-ChildItem -LiteralPath $source -Recurse -Force) {
    if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Source package must be self-contained.' }
}
$staging = Assert-UserPath (Join-Path $userPath ('.quicker/agent-integrations/staging/' + [Guid]::NewGuid().ToString('N')))
[void][IO.Directory]::CreateDirectory($staging)
Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $staging -Recurse -Force
$files = @{}
foreach ($file in Get-ChildItem -LiteralPath $staging -Recurse -File -Force) {
    $files[$file.FullName.Substring($staging.Length + 1).Replace('\', '/')] = Get-PackageHash $file.FullName
}
$newMarker = @{ owner = 'QuickerOrg/quicker-agent-integrations'; client = $Client; version = '0.2.0'; files = $files }
if ($server) { $newMarker['server'] = $server }
Write-Json (Join-Path $staging '.quicker-managed.json') $newMarker
$backup = $null
if (Test-Path -LiteralPath $target) {
    $backup = Assert-UserPath (Join-Path $userPath ('.quicker/agent-integrations/backups/' + $Client + '-' + [Guid]::NewGuid().ToString('N')))
    [void][IO.Directory]::CreateDirectory((Split-Path -Parent $backup))
    Move-Item -LiteralPath $target -Destination $backup
}
try {
    [void][IO.Directory]::CreateDirectory((Split-Path -Parent $target))
    Move-Item -LiteralPath $staging -Destination $target
    if ($configPath) {
        if (Test-Path -LiteralPath $configPath) {
            $configBackup = Assert-UserPath ($configPath + '.quicker-' + [Guid]::NewGuid().ToString('N') + '.bak')
            Copy-Item -LiteralPath $configPath -Destination $configBackup
        }
        $config[$section]['quicker'] = $server
        Write-Json $configPath $config
    }
} catch {
    [void](Assert-UserPath $target)
    if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
    if ($backup) { Move-Item -LiteralPath $backup -Destination $target }
    throw
}
Write-Output "Installed Quicker for $Client at $target"
if ($Client -eq 'cursor') { Write-Output 'Cursor IDE: Developer: Reload Window. Cursor CLI: start a new task; use --plugin-dir with the installed directory if local plugins are not discovered.' }
else { Write-Output 'Restart the MCP server or start a new client task.' }
Write-Output 'Enable MCP and allow writes in Quicker Settings > Agent; complete Quicker client consent when prompted.'
