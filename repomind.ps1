# repomind.ps1
# PowerShell wrapper for RepoMind
# Place this in a folder that's in your PATH (e.g., C:\Tools)
# Or run it directly: .\repomind.ps1 index .

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$CliArgs
)

# Find the Python script
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Use the project virtualenv when present (root or inside the package dir)
$VenvPython = "$ScriptDir\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    $VenvPython = "$ScriptDir\repomind\.venv\Scripts\python.exe"
}

if (Test-Path $VenvPython) {
    & $VenvPython -m repomind.cli $Command @CliArgs
} else {
    python -m repomind.cli $Command @CliArgs
}
