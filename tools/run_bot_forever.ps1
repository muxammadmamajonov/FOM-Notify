param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [int]$RestartDelaySeconds = 10
)

$ErrorActionPreference = "Stop"

$dataDir = Join-Path $ProjectRoot "data"
$logDir = Join-Path $dataDir "logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

$runnerPidFile = Join-Path $dataDir "bot-runner.pid"
$botPidFile = Join-Path $dataDir "bot-process.pid"
$runnerLog = Join-Path $logDir "bot-runner.log"
$stdoutLog = Join-Path $logDir "bot-stdout.log"
$stderrLog = Join-Path $logDir "bot-stderr.log"

function Write-RunnerLog {
    param([string]$Message)

    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -LiteralPath $runnerLog -Value "[$stamp] $Message"
}

function Test-RunningPid {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return $false
    }

    $rawPid = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $procId = 0
    if (-not [int]::TryParse($rawPid, [ref]$procId)) {
        return $false
    }

    return [bool](Get-Process -Id $procId -ErrorAction SilentlyContinue)
}

if (Test-RunningPid -PidFile $runnerPidFile) {
    Write-RunnerLog "Another runner is already active. Exiting duplicate runner."
    exit 0
}

Set-Content -LiteralPath $runnerPidFile -Value $PID

try {
    $pythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        throw "Python executable not found: $pythonExe"
    }

    Set-Location $ProjectRoot
    $env:RUN_ONCE = "0"
    $env:PYTHONUNBUFFERED = "1"

    while ($true) {
        Write-RunnerLog "Starting bot process."

        $proc = Start-Process `
            -FilePath $pythonExe `
            -ArgumentList @("-m", "src.main") `
            -WorkingDirectory $ProjectRoot `
            -PassThru `
            -RedirectStandardOutput $stdoutLog `
            -RedirectStandardError $stderrLog `
            -WindowStyle Hidden

        Set-Content -LiteralPath $botPidFile -Value $proc.Id
        $proc.WaitForExit()
        Remove-Item -LiteralPath $botPidFile -Force -ErrorAction SilentlyContinue

        Write-RunnerLog "Bot process exited with code $($proc.ExitCode). Restarting in $RestartDelaySeconds seconds."
        Start-Sleep -Seconds $RestartDelaySeconds
    }
} catch {
    Write-RunnerLog "Runner failed: $($_.Exception.Message)"
    throw
} finally {
    Remove-Item -LiteralPath $botPidFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $runnerPidFile -Force -ErrorAction SilentlyContinue
    Write-RunnerLog "Runner stopped."
}
