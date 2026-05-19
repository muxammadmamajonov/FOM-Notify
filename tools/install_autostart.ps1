param(
    [ValidateSet("Install", "Remove", "Start", "Stop", "Restart", "Status")]
    [string]$Action = "Install",

    [string]$TaskName = "FOMNotifyBot",

    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,

    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

function Get-FOMRuntimePath {
    param([string]$Name)

    $dataDir = Join-Path $ProjectRoot "data"
    if (-not (Test-Path $dataDir)) {
        New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
    }

    return Join-Path $dataDir $Name
}

function Stop-FOMProcessFromPidFile {
    param([string]$PidFile)

    if (-not (Test-Path $PidFile)) {
        return
    }

    $rawPid = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $procId = 0
    if ([int]::TryParse($rawPid, [ref]$procId)) {
        $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }

    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Stop-FOMNotifyProcesses {
    Stop-FOMProcessFromPidFile -PidFile (Get-FOMRuntimePath "bot-process.pid")
    Stop-FOMProcessFromPidFile -PidFile (Get-FOMRuntimePath "bot-runner.pid")
}

function Install-FOMNotifyAutostart {
    $pythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
    $runnerScript = Join-Path $ProjectRoot "tools\run_bot_forever.ps1"

    if (-not (Test-Path $pythonExe)) {
        throw "Python executable not found: $pythonExe"
    }
    if (-not (Test-Path $runnerScript)) {
        throw "Runner script not found: $runnerScript"
    }

    $powerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    $argument = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runnerScript`" -ProjectRoot `"$ProjectRoot`""

    $action = New-ScheduledTaskAction `
        -Execute $powerShellExe `
        -Argument $argument `
        -WorkingDirectory $ProjectRoot

    $triggers = @(
        (New-ScheduledTaskTrigger -AtLogOn),
        (New-ScheduledTaskTrigger -AtStartup)
    )

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -MultipleInstances IgnoreNew `
        -RestartCount 999 `
        -RestartInterval (New-TimeSpan -Minutes 1) `
        -StartWhenAvailable

    $principal = New-ScheduledTaskPrincipal `
        -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
        -LogonType Interactive `
        -RunLevel Limited

    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $triggers `
        -Settings $settings `
        -Principal $principal `
        -Description "Runs FOM-Notify bot automatically and keeps it alive after reboot/logon." | Out-Null

    Write-Host "Autostart task installed: $TaskName"

    if (-not $NoStart) {
        Start-FOMNotifyAutostart
    }
}

function Remove-FOMNotifyAutostart {
    Stop-FOMNotifyAutostart
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
    Write-Host "Autostart task removed: $TaskName"
}

function Start-FOMNotifyAutostart {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Autostart task started: $TaskName"
}

function Stop-FOMNotifyAutostart {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Stop-FOMNotifyProcesses
    Write-Host "Autostart task stopped: $TaskName"
}

function Restart-FOMNotifyAutostart {
    Stop-FOMNotifyAutostart
    Start-Sleep -Seconds 2
    Start-FOMNotifyAutostart
}

function Show-FOMNotifyAutostartStatus {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) {
        Write-Host "Autostart task is not installed: $TaskName"
        return
    }

    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    [PSCustomObject]@{
        TaskName       = $TaskName
        State          = $task.State
        LastRunTime    = $info.LastRunTime
        LastTaskResult = $info.LastTaskResult
        NextRunTime    = $info.NextRunTime
        RunnerPidFile  = Get-FOMRuntimePath "bot-runner.pid"
        BotPidFile     = Get-FOMRuntimePath "bot-process.pid"
    } | Format-List
}

switch ($Action) {
    "Install" { Install-FOMNotifyAutostart }
    "Remove" { Remove-FOMNotifyAutostart }
    "Start" { Start-FOMNotifyAutostart }
    "Stop" { Stop-FOMNotifyAutostart }
    "Restart" { Restart-FOMNotifyAutostart }
    "Status" { Show-FOMNotifyAutostartStatus }
}
