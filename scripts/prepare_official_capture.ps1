#!/usr/bin/env pwsh
# scripts/prepare_official_capture.ps1
#
# Prepares the environment for one unchanged official AULA L99 screen update capture.
#
# SAFETY: This script only verifies prerequisites. It never runs the updater,
# never accesses hardware, never flashes, and never modifies vendor files.
# It confirms the capture kit is ready BEFORE the user performs the update.

$ErrorActionPreference = "Stop"
$script:PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path (Join-Path $script:PSScriptRoot "..")

$manifest = @{
    "UartTFT-II_Flash.bin" = @{
        Size      = 127599044
        Sha256    = "4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4"
        Immutable = $true
    }
    "HFD_Code_V2.2.bin" = @{
        Size   = 305800
        Sha256 = "432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf"
    }
    "HFD_Code_V2.3.bin" = @{
        Size   = 313652
        Sha256 = "a76806ada9648d2672bbebead8a9bb396c0bc6f3a0a071e22e99001ac3359d03"
    }
    "Flash.ini" = @{
        Size   = 1571
        Sha256 = "e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c"
    }
    "L99 reset firmware 2026.5.25.zip" = @{
        Size   = 45080624
        Sha256 = "e854bebb87a592eaa8553dacff103a7ae62007318592cba2159685fbdb3615e3"
    }
}

$forbiddenFiles = @(
    "patched_UartTFT-II_Flash.bin"
)

$captureTools = @(
    @{ Name = "Procmon";  Hint = "procmon.exe / Process Monitor" },
    @{ Name = "USBPcap"; Hint = "USBPcap (Wireshark USB capture)" },
    @{ Name = "Wireshark"; Hint = "Wireshark / tshark.exe" },
    @{ Name = "Screen recorder"; Hint = "Lossless screen recording software" }
)

$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$passes   = New-Object System.Collections.Generic.List[string]

function Test-FileHash {
    param([string]$Path, [string]$ExpectedSha, [int]$ExpectedSize)
    if (-not (Test-Path -LiteralPath $Path)) {
        $failures.Add("MISSING: $Path")
        return $false
    }
    $actual = Get-FileHash -LiteralPath $Path -Algorithm SHA256 | Select-Object -ExpandProperty Hash
    $size   = (Get-Item -LiteralPath $Path).Length
    $ok = $true
    if ($actual -ne $ExpectedSha) {
        $failures.Add("HASH MISMATCH: $Path (expected $ExpectedSha, got $actual)")
        $ok = $false
    }
    if ($ExpectedSize -gt 0 -and $size -ne $ExpectedSize) {
        $failures.Add("SIZE MISMATCH: $Path (expected $ExpectedSize, got $size)")
        $ok = $false
    }
    if ($ok) { $passes.Add("VERIFIED: $Path ($size bytes, $actual)") }
    return $ok
}

Write-Host "========================================================================"
Write-Host "  OFFICIAL UPDATE CAPTURE - ENVIRONMENT PREPARATION (v0.6.0)"
Write-Host "  Release: v0.5.0  Commit: c82dc35  Decision: NO-GO"
Write-Host "  Capture preparation only - no updater execution, no hardware access"
Write-Host "========================================================================"
Write-Host ""

# 1. Working directory check
if ((Resolve-Path $repoRoot).Path -ne (Resolve-Path $PWD).Path) {
    $warnings.Add("Run from repo root: $repoRoot (current: $PWD)")
} else {
    $passes.Add("Working directory: $repoRoot")
}

# 2. Forbidden vendor files must not exist
foreach ($f in $forbiddenFiles) {
    $candidate = Join-Path $repoRoot $f
    if (Test-Path -LiteralPath $candidate) {
        $failures.Add("FORBIDDEN FILE PRESENT: $candidate (never use patched_UartTFT-II_Flash.bin)")
    } else {
        $passes.Add("ABSENT (good): $f")
    }
}

# 3. Vendor file hash verification (files are local/ignored; report status only)
Write-Host "--- Verifying official file hashes (local/ignored files only) ---"
$vendorFound = $false
foreach ($name in $manifest.Keys) {
    # Check common local locations
    $candidates = @(
        Join-Path $repoRoot $name,
        Join-Path $repoRoot "vendor" $name,
        Join-Path $repoRoot "tools" "softce-aula-l99-research" "extracted" $name,
        Join-Path $env:USERPROFILE "Desktop" $name,
        Join-Path $env:USERPROFILE "Downloads" $name
    )
    $found = $false
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            $found = $true
            $vendorFound = $true
            Test-FileHash -Path $c `
                -ExpectedSha $manifest[$name].Sha256 `
                -ExpectedSize $manifest[$name].Size
            break
        }
    }
    if (-not $found) {
        $warnings.Add("NOT FOUND LOCALLY: $name (place the untouched official file before capture)")
    }
}

if (-not $vendorFound) {
    $warnings.Add("No official vendor files found locally; hashes cannot be verified until files are placed.")
}

# 4. Capture tooling presence (informational; do not fail if missing - user installs)
Write-Host ""
Write-Host "--- Capture tooling (informational) ---"
foreach ($tool in $captureTools) {
    $passes.Add("TOOL REQUIRED: $($tool.Name) - $($tool.Hint)")
}

# 5. No updater process running
Write-Host ""
Write-Host "--- Updater process check ---"
$updaterNames = @("HFD_ISP_TOOL_V1.31.exe", "L99 ISP V1.23.exe", "Screen Reset EXE")
foreach ($name in $updaterNames) {
    $proc = Get-Process -Name ([System.IO.Path]::GetFileNameWithoutExtension($name)) -ErrorAction SilentlyContinue
    if ($proc) {
        $failures.Add("UPDATER RUNNING: $name (close before capture)")
    } else {
        $passes.Add("NOT RUNNING: $name")
    }
}

# 6. Git status - no vendor/capture files tracked
Write-Host ""
Write-Host "--- Git status (no vendor/capture/generated files tracked) ---"
try {
    $status = git -C $repoRoot status --porcelain 2>$null
    if ($LASTEXITCODE -ne 0) {
        $warnings.Add("git status unavailable or not a repository")
    } else {
        $trackedLarge = @()
        $trackedPaths = git -C $repoRoot ls-files 2>$null | ForEach-Object { $_.Trim() }
        foreach ($p in $trackedPaths) {
            $full = Join-Path $repoRoot $p
            if (Test-Path -LiteralPath $full) {
                $len = (Get-Item -LiteralPath $full).Length
                if ($len -gt 5MB) {
                    $trackedLarge += "$p ($len bytes)"
                }
            }
        }
        if ($trackedLarge.Count -gt 0) {
            $failures.Add("TRACKED FILE OVER 5 MB: $($trackedLarge -join ', ')")
        } else {
            $passes.Add("No tracked file over 5 MB")
        }
        $ignoredExtensions = @(".exe", ".bin", ".pcapng", ".pcap", ".zip", ".dll", ".sys")
        $vendorTracked = $trackedPaths | Where-Object {
            $ext = [System.IO.Path]::GetExtension($_)
            $ignoredExtensions -contains $ext -or $_ -like "vendor/*"
        }
        if ($vendorTracked.Count -gt 0) {
            $failures.Add("VENDOR/CAPTURE FILE TRACKED: $($vendorTracked -join ', ')")
        } else {
            $passes.Add("No vendor/capture/generated files tracked")
        }
    }
} catch {
    $warnings.Add("Git check skipped: $_")
}

# 7. Summary
Write-Host ""
Write-Host "========================================================================"
Write-Host "  SUMMARY"
Write-Host "========================================================================"
Write-Host "PASSES:"
foreach ($p in $passes) { Write-Host "  [OK] $p" }
if ($warnings.Count -gt 0) {
    Write-Host ""
    Write-Host "WARNINGS:"
    foreach ($w in $warnings) { Write-Host "  [!] $w" }
}
if ($failures.Count -gt 0) {
    Write-Host ""
    Write-Host "FAILURES - CAPTURE NOT READY:"
    foreach ($f in $failures) { Write-Host "  [X] $f" }
    Write-Host ""
    Write-Host "Resolve all failures before starting captures. Decision remains NO-GO."
    exit 1
}

Write-Host ""
Write-Host "Capture environment is ready. Start all captures BEFORE opening the updater."
Write-Host "Continue captures for 30 seconds after success/restart."
Write-Host "Do not run the updater in this preparation step."
exit 0
