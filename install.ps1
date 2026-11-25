# hez-kouling-analyzer - PowerShell installer
# Usage:  .\install.ps1
#         .\install.ps1 -Force        # skip the overwrite prompt

param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Force UTF-8 console I/O so the Chinese skill name and the Python subprocess
# output render correctly. Without this, Windows PowerShell 5.1 shows mojibake.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    [Console]::InputEncoding  = [System.Text.Encoding]::UTF8
    $OutputEncoding           = [System.Text.Encoding]::UTF8
} catch { }

$SkillName = 'hez口令解析分析'
$Src       = $PSScriptRoot

if (-not (Test-Path (Join-Path $Src 'SKILL.md'))) {
    Write-Host '[ERROR] SKILL.md not found next to this script.' -ForegroundColor Red
    Write-Host '        Run install.ps1 from inside the cloned repository.'
    exit 1
}

$Root = Join-Path $env:USERPROFILE '.workbuddy-ai\skills'
$Dest = Join-Path $Root $SkillName

Write-Host ''
Write-Host '  hez-kouling-analyzer  -  Install' -ForegroundColor Cyan
Write-Host ''
Write-Host "  Source : $Src"
Write-Host "  Target : $Dest"
Write-Host ''

if (-not (Test-Path $Root)) {
    New-Item -ItemType Directory -Path $Root -Force | Out-Null
}

# Back up rather than clobber.
if (Test-Path $Dest) {
    if (-not $Force) {
        $ans = Read-Host '  An existing install was found. Back it up and replace? (Y/N)'
        if ($ans -notmatch '^[yY]') {
            Write-Host '  Cancelled.'
            exit 0
        }
    }
    $Bak = "$Dest.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Move-Item -LiteralPath $Dest -Destination $Bak
    Write-Host "  Backed up to: $Bak" -ForegroundColor Yellow
}

New-Item -ItemType Directory -Path $Dest -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $Src 'SKILL.md')   -Destination $Dest -Force
Copy-Item -LiteralPath (Join-Path $Src 'scripts')    -Destination $Dest -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Src 'references') -Destination $Dest -Recurse -Force

Write-Host ''
if (Test-Path (Join-Path $Dest 'SKILL.md')) {
    Write-Host '  [OK] Installed.' -ForegroundColor Green
    Write-Host "       $Dest"
    Write-Host ''
    Write-Host '  Next:'
    Write-Host '    1. Restart WorkBuddy so the skill list refreshes'
    Write-Host '    2. Say: 用 hez口令解析分析 帮我看看这个包的口令接口'
    Write-Host ''
    Write-Host '  Verify the parser:'
    $tool = Join-Path $Dest 'scripts\dex_tool.py'
    if (Get-Command python -ErrorAction SilentlyContinue) {
        python $tool
    } else {
        Write-Host '    (python not found - install Python 3.8+ or use read-only mode)'
    }
} else {
    Write-Host '  [FAIL] Copy did not complete. Check permissions.' -ForegroundColor Red
    exit 1
}

Write-Host ''