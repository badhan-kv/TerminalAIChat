<#
.SYNOPSIS
    One-time setup for TerminalAIChat (mistralBot): installs Python
    dependencies and adds a `mistralbot` launch function to your PowerShell
    profile, pointing at this clone.

.USAGE
    From the cloned repo directory:  .\setup.ps1
#>

$ErrorActionPreference = "Stop"

$ProjectDir = $PSScriptRoot
$ChatPyPath = Join-Path $ProjectDir "chat.py"
$Marker = "# mistralbot (TerminalAIChat) - added by setup.ps1"

Write-Host "Installing Python dependencies..."
pip install -r (Join-Path $ProjectDir "requirements.txt")

$ProfileDir = Split-Path $PROFILE -Parent
if (-not (Test-Path $ProfileDir)) {
    New-Item -ItemType Directory -Path $ProfileDir -Force | Out-Null
}
if (-not (Test-Path $PROFILE)) {
    New-Item -ItemType File -Path $PROFILE -Force | Out-Null
}

$existing = Get-Content $PROFILE -Raw -ErrorAction SilentlyContinue
if ($existing -and $existing.Contains($Marker)) {
    Write-Host "'mistralbot' function already set up in `$PROFILE - skipping."
} else {
    $block = @"

$Marker
function mistralbot {
    python "$ChatPyPath" @args
}
"@
    Add-Content -Path $PROFILE -Value $block -Encoding utf8
    Write-Host "Added 'mistralbot' function to `$PROFILE ($PROFILE)."
}

Write-Host ""
Write-Host "Setup complete. Open a NEW PowerShell window and run 'mistralbot' from any directory."
Write-Host "First run will prompt for your Mistral and Tavily API keys - see GETTING_API_KEYS.md."
