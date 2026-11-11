[CmdletBinding()]
param(
    [ValidateSet('Setup', 'Start', 'Update')][string]$Action = 'Start',
    [string]$PythonPath = '',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$upstream = 'https://github.com/anonnerdfrenzy/survival-llm.git'
. (Join-Path $PSScriptRoot 'source-update.ps1')

function Invoke-Git([string[]]$Arguments) {
    $output = & git -C $root @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Git failed: ' + ($Arguments -join ' ')) }
    return $output
}
function Find-Python {
    if ($PythonPath) {
        if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) { throw 'PythonPath does not exist.' }
        return (Resolve-Path -LiteralPath $PythonPath).Path
    }
    $candidates = @($venvPython)
    foreach ($name in @('python.exe', 'python3.exe')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command -and $command.Source -notmatch '\\WindowsApps\\') { $candidates += $command.Source }
    }
    $pythonDir = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $pythonDir) {
        $candidates += @(Get-ChildItem -LiteralPath $pythonDir -Directory | Sort-Object Name -Descending |
            ForEach-Object { Join-Path $_.FullName 'python.exe' })
    }
    # Optional existing workstation runtime; no dependency on Codex on other PCs.
    $candidates += Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    $found = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $found) { throw 'Python 3.12+ is required. Run Setup.cmd -PythonPath C:\path\to\python.exe after installing Python.' }
    return $found
}

function Initialize-Environment {
    $environment = Join-Path $root '.venv'
    if ((Test-Path -LiteralPath $environment) -and -not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
        throw 'Existing .venv is incomplete or belongs to another OS. Preserve it under another name, then retry Start.cmd. Nothing was deleted.'
    }
    $python = Find-Python
    & $python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 or newer is required.' }
    if (-not (Test-Path -LiteralPath $venvPython)) {
        Write-Host 'First start: creating the local Python environment...'
        & $python -m venv $environment
        if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
    }
    & $venvPython -c 'import sys; sys.exit(0 if sys.prefix != sys.base_prefix and sys.version_info >= (3, 12) else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Existing .venv is not a working Python 3.12+ virtual environment. Preserve it and repair it before retrying.' }
    Write-Host 'Installing browser-mode dependencies (no models or library)...'
    & $venvPython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed. Check the connection and retry Setup.cmd.' }
}

try {
    if ($CheckOnly) {
        $python = if ($Action -eq 'Update') { $null } else { Find-Python }
        $ollama = Get-Command ollama.exe -ErrorAction SilentlyContinue
        [ordered]@{
            action = $Action
            root = $root
            branch = (Invoke-Git @('branch', '--show-current'))
            upstream = $upstream
            python = $python
            environmentReady = (Test-Path -LiteralPath $venvPython)
            ollamaInstalled = [bool]$ollama
            dryRun = $true
        } | ConvertTo-Json
        exit 0
    }
    if ($Action -eq 'Update') {
        $server = Join-Path $root 'app\server.py'
        $running = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
            Where-Object { $_.CommandLine -and $_.CommandLine.Contains($server) }
        if ($running) { throw 'Close this Survival LLM instance before updating.' }
        Invoke-SourceUpdate -Root $root -Source $upstream
        exit 0
    }
    if ($Action -eq 'Setup') {
        Initialize-Environment
        Write-Host 'Ready. Install/open Ollama if needed, then run Start.cmd. No model or library was downloaded by Setup.'
        exit 0
    }
    if (-not (Test-Path -LiteralPath $venvPython)) { Initialize-Environment }
    & $venvPython -c "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(name) for name in ('pypdf', 'truststore')) else 1)"
    if ($LASTEXITCODE -ne 0) { Initialize-Environment }
    & $venvPython -c 'import pypdf, truststore'
    if ($LASTEXITCODE -ne 0) { throw 'Dependencies could not be loaded. Run Setup.cmd to repair the environment.' }
    # Upstream's existing checkout mode disables the packaged-app self-updater.
    # Source updates remain an explicit Update.cmd action; no upstream code is patched.
    $env:SURVIVAL_LLM_DEV = 'source checkout'
    Push-Location $root
    try {
        & $venvPython (Join-Path $root 'app\server.py') --browser
        if ($LASTEXITCODE -ne 0) { throw 'Survival LLM exited with an error.' }
    } finally { Pop-Location }
} catch {
    [Console]::Error.WriteLine('ERROR: ' + $_.Exception.Message)
    exit 1
}
