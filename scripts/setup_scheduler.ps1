# ============================================
# AI Job Application Agent - Task Scheduler Setup
# ============================================
# Run this script ONCE as Administrator to create the scheduled task.
#
# Usage (in elevated PowerShell):
#   .\scripts\setup_scheduler.ps1

$TaskName = "AIJobApplicationAgent"
$Description = "Runs the AI Job Application Agent daily at 9:00 AM PKT"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$BatPath = Join-Path $ProjectRoot "scripts\run_agent.bat"
$WorkingDir = $ProjectRoot
$LogPath = Join-Path $ProjectRoot "data\logs\scheduler.log"

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell -> 'Run as Administrator' and try again."
    exit 1
}

# Remove existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing task '$TaskName'..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the action
$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatPath`" >> `"$LogPath`" 2>&1" `
    -WorkingDirectory $WorkingDir

# Create the trigger (daily at 9:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00AM"

# Create settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Description $Description `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest

Write-Host ""
Write-Host "Scheduled task '$TaskName' created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Name:      $TaskName"
Write-Host "  Schedule:  Daily at 9:00 AM"
Write-Host "  Script:    $BatPath"
Write-Host "  Log:       $LogPath"
Write-Host ""
Write-Host "To verify: Open Task Scheduler (taskschd.msc) and look for '$TaskName'"
Write-Host "To run now: Right-click the task -> 'Run'"
Write-Host "To remove:  Unregister-ScheduledTask -TaskName '$TaskName'"
