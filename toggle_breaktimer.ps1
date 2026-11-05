# BreakTimer Ultra - Toggle Script (Start / Stop)
# タスクバーにピン留めしてワンクリックで起動/停止

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainPy = Join-Path $scriptDir "main.py"

# Find running BreakTimer python processes (exclude self)
$currentPid = $PID
$found = @()
Get-Process | Where-Object { $_.ProcessName -match 'python' } | ForEach-Object {
    try {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)").CommandLine
        if ($cmdLine -and $cmdLine -match [regex]::Escape($scriptDir) -and $cmdLine -match 'main\.py') {
            $found += $_
        }
    } catch {}
}

if ($found.Count -gt 0) {
    # BreakTimer is running -> Stop it
    foreach ($proc in $found) {
        try { $proc.Kill() } catch {}
    }
    # Show brief balloon notification via PowerShell
    Add-Type -AssemblyName System.Windows.Forms
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.Visible = $true
    $notify.BalloonTipTitle = "BreakTimer Ultra"
    $notify.BalloonTipText = "停止しました"
    $notify.BalloonTipIcon = "Info"
    $notify.ShowBalloonTip(2000)
    Start-Sleep -Milliseconds 2500
    $notify.Dispose()
} else {
    # BreakTimer is not running -> Start it
    $pythonw = "pythonw.exe"
    Start-Process -FilePath $pythonw -ArgumentList "`"$mainPy`"" -WorkingDirectory $scriptDir -WindowStyle Hidden
}
