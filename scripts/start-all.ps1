param(
    [switch]$SkipInfra,
    [switch]$KeepExistingAi,
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$NoBrowser,
    [switch]$Elevated,
    [int]$AiPort = 8003,
    [int]$BackendPort = 8080,
    [int]$FrontendPort = 5173,
    [string]$NetworkProbeUrl = "https://api.siliconflow.cn/v1/models"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$logsRoot = Join-Path $projectRoot "logs"
$aiScript = Join-Path $PSScriptRoot "start-ai-service.ps1"
$serviceRoot = Join-Path $projectRoot "apps\ai-service"
$backendRoot = Join-Path $projectRoot "apps\backend"
$frontendRoot = Join-Path $projectRoot "apps\web"
$composeFile = Join-Path $projectRoot "docker-compose.yml"

New-Item -ItemType Directory -Path $logsRoot -Force | Out-Null

function Require-Command {
    param([string]$Name)

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Required command not found: $Name"
    }
    return $command.Source
}

function Test-TcpPort {
    param([int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync("127.0.0.1", $Port)
        if (-not $task.Wait(1000)) {
            return $false
        }
        return $client.Connected
    }
    catch {
        return $false
    }
    finally {
        $client.Dispose()
    }
}

function Wait-TcpPort {
    param(
        [int]$Port,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-TcpPort -Port $Port) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Test-HttpEndpoint {
    param(
        [string]$Uri,
        [int]$TimeoutSeconds = 3
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Uri -Method Get -TimeoutSec $TimeoutSeconds
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    }
    catch {
        $response = $_.Exception.Response
        if ($response -and $response.StatusCode) {
            $code = [int]$response.StatusCode
            return $code -ge 200 -and $code -lt 500
        }
        return $false
    }
}

function Test-ExternalHttps {
    param([string]$Uri)

    return Test-HttpEndpoint -Uri $Uri -TimeoutSeconds 8
}

function Wait-HttpEndpoint {
    param(
        [string]$Uri,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpEndpoint -Uri $Uri) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-PortListener {
    param([int]$Port)

    return Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
}

function Start-DetachedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdout = Join-Path $logsRoot "$Name-$stamp.stdout.log"
    $stderr = Join-Path $logsRoot "$Name-$stamp.stderr.log"
    $process = Start-Process `
        -FilePath $FilePath `
        -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden `
        -PassThru `
        -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr

    Write-Host "$Name started. PID: $($process.Id)"
    Write-Host "  stdout: $stdout"
    Write-Host "  stderr: $stderr"
    return $process
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Restart-AiServiceProcess {
    param(
        [string]$PythonPath,
        [string]$ServiceRoot,
        [int]$Port
    )

    # On Windows, the venv launcher can leave the actual server child running
    # under the base Anaconda executable. Matching only Process.Path therefore
    # stops the launcher but leaves the old server bound to 8003. Inspect the
    # command line as well, while requiring the exact project root and port so
    # unrelated Python processes are never touched.
    $root = [IO.Path]::GetFullPath($ServiceRoot).TrimEnd('\')
    $serverProcesses = @()
    try {
        $serverProcesses = Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $commandLine = [string]$_.CommandLine
                if (-not $commandLine -or $_.ProcessId -eq $PID) {
                    return $false
                }
                $sameRoot = $commandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -ge 0
                $samePort = $commandLine -match ("(?i)--port\s+{0}\b" -f $Port)
                $isAiServer = $commandLine -match '(?i)(?:server\.py|uvicorn(?:\.exe)?\s+)'
                return $sameRoot -and $samePort -and $isAiServer
            }
    }
    catch {
        # The starter is normally elevated. If process inspection is denied,
        # retain the old path-based fallback for the launcher process.
        $serverProcesses = Get-Process -Name python,pythonw -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -eq $PythonPath }
    }

    foreach ($serverProcess in $serverProcesses) {
        $processId = if ($null -ne $serverProcess.ProcessId) {
            $serverProcess.ProcessId
        }
        else {
            $serverProcess.Id
        }
        if ($processId) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 700
}

Write-Host "=== Shinkou Insight: start all services ===" -ForegroundColor Cyan
Write-Host "Project root: $projectRoot"

# The AI service must be able to create outbound HTTPS sockets. Re-launch the
# complete starter once with administrator privileges so Docker and Python use
# the same network-capable Windows token. The UAC prompt appears only once.
if (-not $Elevated -and -not (Test-IsAdministrator)) {
    $elevatedArguments = @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ('"{0}"' -f $PSCommandPath),
        "-Elevated"
    )
    if ($SkipInfra) { $elevatedArguments += "-SkipInfra" }
    if ($KeepExistingAi) { $elevatedArguments += "-KeepExistingAi" }
    if ($SkipBackend) { $elevatedArguments += "-SkipBackend" }
    if ($SkipFrontend) { $elevatedArguments += "-SkipFrontend" }
    if ($NoBrowser) { $elevatedArguments += "-NoBrowser" }
    if ($AiPort -ne 8003) { $elevatedArguments += @("-AiPort", "$AiPort") }
    if ($BackendPort -ne 8080) { $elevatedArguments += @("-BackendPort", "$BackendPort") }
    if ($FrontendPort -ne 5173) { $elevatedArguments += @("-FrontendPort", "$FrontendPort") }
    if ($NetworkProbeUrl -ne "https://api.siliconflow.cn/v1/models") { $elevatedArguments += @("-NetworkProbeUrl", $NetworkProbeUrl) }

    $elevated = Start-Process `
        -FilePath (Get-Command powershell.exe).Source `
        -ArgumentList $elevatedArguments `
        -WorkingDirectory $projectRoot `
        -Verb RunAs `
        -Wait `
        -PassThru
    exit $elevated.ExitCode
}

if (-not (Test-ExternalHttps -Uri $NetworkProbeUrl)) {
    throw 'Outbound HTTPS preflight failed. No service will start in a restricted environment.'
}
Write-Host ("Outbound HTTPS check passed: {0}" -f $NetworkProbeUrl) -ForegroundColor Green

$docker = Require-Command -Name "docker.exe"
$maven = Require-Command -Name "mvn.cmd"
$npm = Require-Command -Name "npm.cmd"
$powerShell = Require-Command -Name "powershell.exe"

if (-not (Test-Path -LiteralPath $composeFile)) {
    throw "docker-compose.yml not found: $composeFile"
}
if (-not (Test-Path -LiteralPath $aiScript)) {
    throw "AI service start script not found: $aiScript"
}

if (-not $SkipInfra) {
    Write-Host "[1/4] Starting infrastructure containers..." -ForegroundColor Yellow
    $infra = @(
        "postgres",
        "redis",
        "milvus-etcd",
        "milvus-minio",
        "milvus",
        "minio",
        "minio-init"
    )
    & $docker compose --env-file (Join-Path $projectRoot ".env") -f $composeFile up -d $infra
    if ($LASTEXITCODE -ne 0) {
        throw "Infrastructure startup failed. Run 'docker compose ps' for details."
    }
    Write-Host "Infrastructure containers started."
}
else {
    Write-Host "[1/4] Infrastructure startup skipped."
}

Write-Host "[2/4] Starting AI service with external-network permission..." -ForegroundColor Yellow
$aiPython = Join-Path $projectRoot "apps\ai-service\.venv\Scripts\python.exe"
if (-not $KeepExistingAi) {
    Restart-AiServiceProcess -PythonPath $aiPython -ServiceRoot $serviceRoot -Port $AiPort
}
& $powerShell -NoProfile -ExecutionPolicy Bypass -File $aiScript -Port $AiPort -NoReload -Elevated -NetworkProbeUrl $NetworkProbeUrl
if (-not (Wait-HttpEndpoint -Uri "http://127.0.0.1:$AiPort/health" -TimeoutSeconds 45)) {
    throw "AI service did not become healthy on port $AiPort. Check logs\ai-service-*.stderr.log."
}
Write-Host "AI service is healthy: http://127.0.0.1:$AiPort/health"

if (-not $SkipBackend) {
    Write-Host "[3/4] Starting backend..." -ForegroundColor Yellow
    $backendHealth = "http://127.0.0.1:$BackendPort/actuator/health"
    if (Test-HttpEndpoint -Uri $backendHealth) {
        Write-Host "Backend is already healthy: $backendHealth"
    }
    else {
        $listener = Get-PortListener -Port $BackendPort
        if ($listener) {
            throw "Port $BackendPort is already occupied by PID $($listener.OwningProcess)."
        }
        Start-DetachedProcess `
            -Name "backend" `
            -FilePath $maven `
            -Arguments @("spring-boot:run", "-o") `
            -WorkingDirectory $backendRoot | Out-Null
        if (-not (Wait-HttpEndpoint -Uri $backendHealth -TimeoutSeconds 120)) {
            throw "Backend did not become healthy on port $BackendPort. Check logs\backend-*.stderr.log."
        }
        Write-Host "Backend is healthy: $backendHealth"
    }
}
else {
    Write-Host "[3/4] Backend startup skipped."
}

if (-not $SkipFrontend) {
    Write-Host "[4/4] Starting frontend..." -ForegroundColor Yellow
    $frontendUrl = "http://127.0.0.1:$FrontendPort/"
    if (Test-HttpEndpoint -Uri $frontendUrl) {
        Write-Host "Frontend is already running: $frontendUrl"
    }
    else {
        $listener = Get-PortListener -Port $FrontendPort
        if ($listener) {
            throw "Port $FrontendPort is already occupied by PID $($listener.OwningProcess)."
        }
        Start-DetachedProcess `
            -Name "frontend" `
            -FilePath $npm `
            -Arguments @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort") `
            -WorkingDirectory $frontendRoot | Out-Null
        if (-not (Wait-HttpEndpoint -Uri $frontendUrl -TimeoutSeconds 60)) {
            throw "Frontend did not become ready on port $FrontendPort. Check logs\frontend-*.stderr.log."
        }
        Write-Host "Frontend is ready: $frontendUrl"
    }
}
else {
    Write-Host "[4/4] Frontend startup skipped."
}

Write-Host ""
Write-Host "All requested services are ready." -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:$FrontendPort/"
Write-Host "Backend:  http://127.0.0.1:$BackendPort/"
Write-Host "AI:       http://127.0.0.1:$AiPort/health"

if (-not $NoBrowser -and -not $SkipFrontend) {
    Start-Process "http://127.0.0.1:$FrontendPort/"
}
