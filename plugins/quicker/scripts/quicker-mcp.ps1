[CmdletBinding()]
param(
    [string]$SettingsPath = '',
    [ValidateRange(1, 600)]
    [int]$RequestTimeoutSeconds = 180,
    [switch]$Check
)

# A transport adapter only: Quicker owns tools, authoring state and approval policy.
# Keep JSON payloads as text so Windows PowerShell never rewrites schemas or numbers.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::InputEncoding = $utf8
[Console]::OutputEncoding = $utf8
$OutputEncoding = $utf8
Add-Type -AssemblyName System.Web.Extensions
$jsonReader = New-Object System.Web.Script.Serialization.JavaScriptSerializer
$jsonReader.MaxJsonLength = [int]::MaxValue
$jsonReader.RecursionLimit = 256
if ([string]::IsNullOrWhiteSpace($SettingsPath)) {
    $SettingsPath = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.quicker\mcp\server.json'
}

function Write-ProtocolLine([string]$Text) {
    [Console]::Out.WriteLine($Text)
    [Console]::Out.Flush()
}

function Compress-JsonText([string]$Text) {
    $builder = New-Object System.Text.StringBuilder
    $inString = $false
    $escaped = $false
    foreach ($character in $Text.ToCharArray()) {
        if ($inString) {
            [void]$builder.Append($character)
            if ($escaped) { $escaped = $false }
            elseif ($character -eq '\') { $escaped = $true }
            elseif ($character -eq '"') { $inString = $false }
        }
        elseif ($character -eq '"') {
            $inString = $true
            [void]$builder.Append($character)
        }
        elseif (-not [char]::IsWhiteSpace($character)) { [void]$builder.Append($character) }
    }
    return $builder.ToString()
}

function Get-RpcIdText([string]$Text) {
    # Read only the top-level id token, preserving a numeric id's exact spelling.
    $depth = 0
    for ($index = 0; $index -lt $Text.Length; $index++) {
        $character = $Text[$index]
        if ($character -eq '{' -or $character -eq '[') { $depth++; continue }
        if ($character -eq '}' -or $character -eq ']') { $depth--; continue }
        if ($character -ne '"') { continue }
        $start = $index
        $index++
        for (; $index -lt $Text.Length; $index++) {
            if ($Text[$index] -eq '\') { $index++; continue }
            if ($Text[$index] -eq '"') { break }
        }
        if ($depth -ne 1) { continue }
        $after = $index + 1
        while ($after -lt $Text.Length -and [char]::IsWhiteSpace($Text[$after])) { $after++ }
        if ($after -ge $Text.Length -or $Text[$after] -ne ':') { continue }
        $keyToken = $Text.Substring($start, $index - $start + 1)
        $key = $jsonReader.DeserializeObject('{"key":' + $keyToken + '}')
        if ($key.key -cne 'id') { continue }
        $valueStart = $after + 1
        while ($valueStart -lt $Text.Length -and [char]::IsWhiteSpace($Text[$valueStart])) { $valueStart++ }
        $valueEnd = $valueStart
        if ($Text[$valueStart] -eq '"') {
            $valueEnd++
            for (; $valueEnd -lt $Text.Length; $valueEnd++) {
                if ($Text[$valueEnd] -eq '\') { $valueEnd++; continue }
                if ($Text[$valueEnd] -eq '"') { $valueEnd++; break }
            }
        }
        else {
            while ($valueEnd -lt $Text.Length -and $Text[$valueEnd] -ne ',' -and $Text[$valueEnd] -ne '}') { $valueEnd++ }
        }
        return $Text.Substring($valueStart, $valueEnd - $valueStart).Trim()
    }
    return $null
}

function Write-RpcFailure {
    param([string]$IdText, [int]$Code, [string]$FailureCode, [string]$Message,
        [bool]$StateUnknown = $false, [int]$HttpStatus = 0)
    if ([string]::IsNullOrEmpty($IdText)) {
        # Notifications must not receive JSON-RPC replies. Diagnostics never contain input data.
        [Console]::Error.WriteLine('Quicker MCP: ' + $FailureCode + '. ' + $Message)
        return
    }
    $data = [ordered]@{ code = $FailureCode; stateUnknown = $StateUnknown }
    if ($HttpStatus -ne 0) { $data.httpStatus = $HttpStatus }
    $errorBody = [ordered]@{ code = $Code; message = $Message; data = $data } | ConvertTo-Json -Depth 8 -Compress
    Write-ProtocolLine ('{"jsonrpc":"2.0","id":' + $IdText + ',"error":' + $errorBody + '}')
}

function Read-McpSettings {
    if (-not [System.IO.File]::Exists($SettingsPath)) {
        return @{ Code = 'settings_missing'; Message = 'Enable MCP Server in a Debug build of Quicker first.' }
    }
    try {
        $settings = $jsonReader.DeserializeObject([System.IO.File]::ReadAllText($SettingsPath, $utf8))
        if ($null -eq $settings -or $settings -is [array]) { throw 'invalid' }
        $port = 0
        if (-not [int]::TryParse([string]$settings.Port, [ref]$port) -or $port -lt 1024 -or $port -gt 65535) {
            throw 'invalid'
        }
        $tokenPresent = $settings.Token -is [string] -and -not [string]::IsNullOrWhiteSpace($settings.Token)
        if ($tokenPresent -and $settings.Token -match '\s') { throw 'invalid' }
        $enabled = $settings.Enabled -is [bool] -and $settings.Enabled
        $allowWrites = $settings.AllowWrites -is [bool] -and $settings.AllowWrites
        return @{ Enabled = $enabled; AllowWrites = $allowWrites; Port = $port;
            TokenPresent = $tokenPresent; Token = $settings.Token }
    }
    catch {
        return @{ Code = 'settings_invalid'; Message = 'Quicker MCP settings could not be read. Check them in Quicker.' }
    }
}

if ($Check) {
    $settings = Read-McpSettings
    if ($settings.Code) {
        Write-ProtocolLine (([ordered]@{ ok = $false; code = $settings.Code; message = $settings.Message }) | ConvertTo-Json -Compress)
        exit 1
    }
    $reachable = $false
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $pending = $client.BeginConnect('127.0.0.1', $settings.Port, $null, $null)
        if ($pending.AsyncWaitHandle.WaitOne(2000)) {
            $client.EndConnect($pending)
            $reachable = $client.Connected
        }
        $pending.AsyncWaitHandle.Close()
    }
    catch { $reachable = $false }
    finally { $client.Close() }
    $ready = $settings.Enabled -and $settings.TokenPresent -and $reachable
    Write-ProtocolLine (([ordered]@{ ok = [bool]$ready; enabled = [bool]$settings.Enabled;
        allowWrites = [bool]$settings.AllowWrites; port = $settings.Port;
        tokenPresent = [bool]$settings.TokenPresent; portReachable = $reachable }) | ConvertTo-Json -Compress)
    if ($ready) { exit 0 }
    exit 1
}

$protocolVersion = $null
while ($null -ne ($line = [Console]::In.ReadLine())) {
    if ([string]::IsNullOrWhiteSpace($line)) { continue }
    $idText = $null
    try {
        $rpc = $jsonReader.DeserializeObject($line)
        $idText = Get-RpcIdText $line
        if ($null -eq $rpc -or $rpc -is [array] -or $rpc.jsonrpc -cne '2.0' -or
            $rpc.method -isnot [string] -or [string]::IsNullOrWhiteSpace($rpc.method)) {
            throw 'invalid request'
        }
        if ($null -ne $rpc.id -and ($rpc.id -is [bool] -or ($rpc.id -isnot [string] -and $rpc.id -isnot [ValueType]))) { throw 'invalid id' }
    }
    catch {
        Write-RpcFailure -IdText 'null' -Code -32600 -FailureCode 'invalid_request' -Message 'Expected one JSON-RPC 2.0 request or notification per line.'
        continue
    }

    $settings = Read-McpSettings
    if ($settings.Code) {
        Write-RpcFailure -IdText $idText -Code -32001 -FailureCode $settings.Code -Message $settings.Message
        continue
    }
    if (-not $settings.Enabled) {
        Write-RpcFailure -IdText $idText -Code -32001 -FailureCode 'server_disabled' -Message 'Enable MCP Server in Quicker settings.'
        continue
    }
    if (-not $settings.TokenPresent) {
        Write-RpcFailure -IdText $idText -Code -32001 -FailureCode 'token_missing' -Message 'Quicker MCP has no token. Check MCP Server settings in Quicker.'
        continue
    }

    $request = $null
    $response = $null
    $mayHaveSent = $false
    $forwardedResponse = $false
    try {
        # Only the persisted port is configurable. Never send the token to another host,
        # an HTTP proxy, or a redirect target.
        $request = [System.Net.HttpWebRequest]::Create('http://127.0.0.1:' + $settings.Port + '/mcp')
        $request.Method = 'POST'
        $request.Proxy = $null
        $request.AllowAutoRedirect = $false
        # Avoid automatic replay when a reused keep-alive socket is closed by the server.
        $request.KeepAlive = $false
        $request.Timeout = $RequestTimeoutSeconds * 1000
        $request.ReadWriteTimeout = $RequestTimeoutSeconds * 1000
        $request.ContentType = 'application/json; charset=utf-8'
        $request.Accept = 'application/json, text/event-stream'
        $request.Headers['Authorization'] = 'Bearer ' + $settings.Token
        $request.Headers['Mcp-Client-Info'] = 'codex-quicker-plugin'
        if ($protocolVersion) { $request.Headers['MCP-Protocol-Version'] = $protocolVersion }
        $request.ServicePoint.Expect100Continue = $false
        $bytes = $utf8.GetBytes($line)
        $request.ContentLength = $bytes.Length
        $mayHaveSent = $true
        $stream = $request.GetRequestStream()
        try { $stream.Write($bytes, 0, $bytes.Length) }
        finally { $stream.Dispose() }
        try { $response = $request.GetResponse() }
        catch [System.Net.WebException] {
            if ($null -eq $_.Exception.Response) { throw }
            $response = $_.Exception.Response
        }
        $status = [int]$response.StatusCode
        if ($status -lt 200 -or $status -ge 300) {
            $failureCode = 'http_error'
            $message = 'Quicker MCP rejected the HTTP request. Check Quicker before retrying.'
            $stateUnknown = $status -ge 500
            if ($status -eq 401) { $failureCode = 'unauthorized'; $message = 'Quicker rejected the MCP token. Check MCP settings in Quicker.' }
            elseif ($status -eq 403) { $failureCode = 'client_not_approved'; $message = 'Approve the Codex MCP client in Quicker, then reconnect.' }
            elseif ($status -ge 300 -and $status -lt 400) { $failureCode = 'redirect_refused'; $message = 'Quicker MCP returned a redirect. Redirects are refused; check the local endpoint.' }
            Write-RpcFailure -IdText $idText -Code -32003 -FailureCode $failureCode -Message $message -StateUnknown $stateUnknown -HttpStatus $status
            continue
        }
        if ($status -eq 202) {
            if ($idText) { throw 'missing response' }
            continue
        }
        $reader = New-Object System.IO.StreamReader($response.GetResponseStream(), $utf8)
        try { $body = $reader.ReadToEnd() }
        finally { $reader.Dispose() }
        if ([string]::IsNullOrWhiteSpace($body)) {
            if ($idText) { throw 'missing response' }
            continue
        }
        $payloads = New-Object 'System.Collections.Generic.List[string]'
        if ($response.ContentType -match '^text/event-stream(?:;|$)') {
            $eventData = New-Object 'System.Collections.Generic.List[string]'
            foreach ($eventLine in ($body -split '\r\n|\n|\r')) {
                if ($eventLine.Length -eq 0) {
                    if ($eventData.Count -gt 0) { $payloads.Add(($eventData -join "`n")); $eventData.Clear() }
                }
                elseif ($eventLine.StartsWith('data:')) {
                    $value = $eventLine.Substring(5)
                    if ($value.StartsWith(' ')) { $value = $value.Substring(1) }
                    $eventData.Add($value)
                }
            }
            if ($eventData.Count -gt 0) { $payloads.Add(($eventData -join "`n")) }
        }
        elseif ($response.ContentType -match '^application/json(?:;|$)') { $payloads.Add($body) }
        else { throw 'unsupported response' }

        foreach ($payload in $payloads) {
            $parsed = $jsonReader.DeserializeObject($payload)
            if ($null -eq $parsed -or $parsed -is [array] -or $parsed.jsonrpc -cne '2.0') { throw 'invalid response' }
            $responseId = Get-RpcIdText $payload
            if ($null -ne $responseId) {
                if (-not $idText -or $forwardedResponse -or $parsed.id -cne $rpc.id) { throw 'unexpected response id' }
                if ($rpc.method -ceq 'initialize' -and $parsed.result.protocolVersion -is [string]) {
                    $version = $parsed.result.protocolVersion
                    if ($version -match '^\d{4}-\d{2}-\d{2}$') { $protocolVersion = $version }
                }
                $forwardedResponse = $true
            }
            elseif ($parsed.method -isnot [string]) { throw 'invalid notification' }
            Write-ProtocolLine (Compress-JsonText $payload)
        }
        if ($idText -and -not $forwardedResponse) { throw 'missing response' }
    }
    catch {
        if (-not $forwardedResponse) {
            Write-RpcFailure -IdText $idText -Code -32002 -FailureCode 'transport_failed' -StateUnknown $mayHaveSent -Message 'The Quicker MCP request did not produce a complete response. Its outcome may be unknown; inspect Quicker and reopen or reread the action before retrying a write.'
        }
        else { [Console]::Error.WriteLine('Quicker MCP: invalid data after the completed response.') }
    }
    finally {
        if ($null -ne $response) { $response.Dispose() }
        if ($null -ne $request) { $request.Abort() }
    }
}
