# Registers the CokingCoalExport scheduled task. Run as Administrator.
# Triggers: 00:00, 06:00, 12:00, 18:00 daily.

$ProjectRoot = "C:\Users\0200705\Downloads\dimpu"
$BatPath     = Join-Path $ProjectRoot "scripts\run_export.bat"
$TaskName    = "CokingCoalExport"

if (-not (Test-Path $BatPath)) {
    Write-Error "Batch file not found: $BatPath"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $ProjectRoot

$Triggers = @(
    (New-ScheduledTaskTrigger -Daily -At 12:00AM),
    (New-ScheduledTaskTrigger -Daily -At  6:00AM),
    (New-ScheduledTaskTrigger -Daily -At 12:00PM),
    (New-ScheduledTaskTrigger -Daily -At  6:00PM)
)

$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Triggers `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Fetch last 100 rows of coal_articles from Azure SQL and upload .xlsx to Google Drive." `
    -Force

Write-Host ""
Write-Host "Registered scheduled task '$TaskName'."
Write-Host "Triggers: 00:00, 06:00, 12:00, 18:00 daily."
Write-Host ""
Write-Host "Manual test:    Start-ScheduledTask -TaskName $TaskName"
Write-Host "View status:    Get-ScheduledTask -TaskName $TaskName | Get-ScheduledTaskInfo"
Write-Host "Open in GUI:    taskschd.msc"
