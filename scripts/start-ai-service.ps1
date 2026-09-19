param(
    [int]$Port = 8003,
    [switch]$Reload,
    [switch]$NoReload
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$serviceRoot = Join-Path $projectRoot "apps\ai-service"
$pythonPath = Join-Path $serviceRoot ".venv\Scripts\python.exe"
$logRoot = Join-Path $projectRoot "logs"
$logPath = Join-Path $logRoot "ai-service.log"

# Prefer the project-local optional file-analysis toolchain when present.
# This keeps OCR/PDF/Office support working without requiring system-wide
# installation or a user-managed PATH on Windows.
$bundledToolDirs = @((Join-Path $projectRoot "tools\runtime\tesseract"))
$popplerRoot = Join-Path $projectRoot "tools\runtime\poppler"
$bundledToolDirs += Get-ChildItem -LiteralPath $popplerRoot -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Join-Path $_.FullName "Library\bin" } |
    Where-Object { Test-Path -LiteralPath $_ }
$bundledToolDirs += Join-Path $projectRoot "tools\runtime\libreoffice\program"
$bundledToolDirs = $bundledToolDirs | Where-Object { Test-Path -LiteralPath $_ }
if ($bundledToolDirs.Count -gt 0) {
    $env:Path = (($bundledToolDirs -join [IO.Path]::PathSeparator) + [IO.Path]::PathSeparator + $env:Path)
}
$bundledTessData = Join-Path $projectRoot "tools\runtime\tesseract\tessdata"
if (Test-Path -LiteralPath $bundledTessData) {
    $env:TESSDATA_PREFIX = $bundledTessData
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "AI service virtual environment not found: $pythonPath. Install requirements.txt first."
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    try {
        $health = Invoke-RestMethod -Uri "http://localhost:$Port/health" -Method Get -TimeoutSec 3
        $openapi = Invoke-RestMethod -Uri "http://localhost:$Port/openapi.json" -Method Get -TimeoutSec 3
        $hasTestRoute = $openapi.paths.PSObject.Properties.Name -contains "/internal/llm/test"
        $hasContextRoute = $openapi.paths.PSObject.Properties.Name -contains "/internal/llm/context"
        if ($health.service -eq "ai-service" -and $hasTestRoute -and $hasContextRoute) {
            Write-Host "Shinkou AI Service is already running on port $Port."
            Write-Host "Health check: http://localhost:$Port/health"
            exit 0
        }
    }
    catch {
        # The port is occupied, but it is not the current AI service.
    }
    $owner = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
    $ownerName = if ($owner) { $owner.ProcessName } else { "unknown" }
    $ownerPath = if ($owner -and $owner.Path) { $owner.Path } else { "path unavailable" }
    throw "Port $Port is used by PID $($listener.OwningProcess) ($ownerName, $ownerPath), but it is not Shinkou AI Service. Stop that service or start this script with -Port 8001."
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

if (-not $Reload -or $NoReload) {
    # The custom runner is needed because Uvicorn's regular asyncio runner
    # selects ProactorEventLoop on Windows, while psycopg's async pool needs
    # SelectorEventLoop.
    $arguments = @(
        "server.py",
        "--host",
        "0.0.0.0",
        "--port",
        "$Port"
    )
} else {
    $arguments = @(
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "$Port",
        "--loop",
        "asyncio",
        "--reload"
    )
}

Write-Host "Starting Shinkou AI Service: http://localhost:$Port"
Write-Host "Health check: http://localhost:$Port/health"
$logStamp = Get-Date -Format "yyyyMMdd-HHmmss"
$stdoutLogPath = Join-Path $logRoot "ai-service-$logStamp.stdout.log"
$stderrLogPath = Join-Path $logRoot "ai-service-$logStamp.stderr.log"
Write-Host "Standard output: $stdoutLogPath"
Write-Host "Error output: $stderrLogPath"

$argumentList = $arguments -join " "
$process = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList $argumentList `
    -WorkingDirectory $serviceRoot `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $stdoutLogPath `
    -RedirectStandardError $stderrLogPath

Write-Host "AI service process started. PID: $($process.Id)"
Start-Sleep -Seconds 2
try {
    $health = Invoke-RestMethod -Uri "http://localhost:$Port/health" -Method Get -TimeoutSec 3
    Write-Host "AI service is ready: $($health.service)"
}
catch {
    Write-Host "AI service process is running but not ready yet. Check the log files above."
}
