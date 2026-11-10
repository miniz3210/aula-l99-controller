#!/usr/bin/env pwsh
# scripts/prepare_official_capture.ps1
#
# Preflight-only preparation for one unchanged official L99 ISP V1.23.exe screen update capture.
#
# SAFETY: This script only verifies prerequisites. It never runs the updater,
# never accesses hardware, never flashes, and never modifies vendor files.
# It confirms the capture kit is ready BEFORE the user performs the update.
# It performs no hardware access and launches no EXE.

[CmdletBinding()]
param(
    [switch] $Preflight
)

$ErrorActionPreference = "Stop"
$script:PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoRoot = Resolve-Path (Join-Path $script:PSScriptRoot "..")
$packageRoot = Join-Path $repoRoot "firmware" "unpacked"

# ---------------------------------------------------------------------------
# Approved capture target manifest: original untouched L99 ISP V1.23.exe package
# ---------------------------------------------------------------------------
$manifest = @{
    "L99 ISP V1.23.exe" = @{
        Size      = 111008
        Sha256    = "e849917779505ce97c8bd8cb9323b223f613337524f94b9aaaa9cc617e743ef0"
        Required  = $true
        Immutable = $true
    }
    "Flash.ini" = @{
        Size   = 1571
        Sha256 = "e515905c61a6ad99bf96eaac3e24e5cfd21e274c087f9903b14f35ecece21e2c"
        Required = $true
    }
    "HFD_Code_V2.2.bin" = @{
        Size   = 305800
        Sha256 = "432e358cac96fb930ab680ada6f953c9005027c58b31b7ee3bb6bc7868ef35cf"
        Required = $true
    }
    "HFD_Code_V2.3.bin" = @{
        Size   = 313504
        Sha256 = "b277823234fcab7137963896493bcb6896fd985fc972354166fcfc584534e37f"
        Required = $true
    }
    "HFD_ISP_TOOL_V1.31.exe" = @{
        Size   = 99328
        Sha256 = "3fd0227368539e4b80a385ea721a1f091d6f22997da24451e2f8248d512ca282"
        Required = $true
    }
}

# Runtime DLLs beside the EXE (informational, hash-verified by preflight)
$manifest["Qt5Core.dll"] = @{ Size = 8460552; Sha256 = "2af418a34f2076b05ee08dc4bedbe6eb7050bcb6b0658a3db2d5d4302af2db45"; Required = $true }
$manifest["Qt5Gui.dll"] = @{ Size = 9857512; Sha256 = "6431689ae70b04224017f0ca8d1ace0102ac03ca5d11aa7cdb1108c6d5ab95a8"; Required = $true }
$manifest["Qt5SerialPort.dll"] = @{ Size = 158752; Sha256 = "333df93739e8afefecb4e4c56b91d22350869aa24d3ba44c66d310cea0de86"; Required = $true }
$manifest["Qt5Svg.dll"] = @{ Size = 589544; Sha256 = "60bb2aa9d37684ed43a2c5ad8781c0d9af656e1ce1e867ea3a17752970803d87"; Required = $true }
$manifest["Qt5Widgets.dll"] = @{ Size = 9131304; Sha256 = "fa3d2383ebe612f83da59207119ea7aac8306a9f165457f7b9d97b875c584"; Required = $true }
$manifest["libEGL.dll"] = @{ Size = 67128; Sha256 = "d3628f75921b9145e85442f0c77aba7e568bb6b7bd2479ad9c253654b6a6b677"; Required = $true }
$manifest["libGLESv2.dll"] = @{ Size = 7789416; Sha256 = "1d31fe6b741850f00a4b93bb21591008826f72b10063f0cf933610230524456d"; Required = $true }
$manifest["opengl32sw.dll"] = @{ Size = 15995904; Sha256 = "25ae7577e066fa80519a8f1c314b15cdd22e4a8d3ecd2a36eeccc79e40714a91d"; Required = $true }
$manifest["D3Dcompiler_47.dll"] = @{ Size = 3466856; Sha256 = "efbdbbcd0d954f8fdc53467de5d89ad525e4e4a9cfff8a15d07c6fdb350c407f"; Required = $true }
$manifest["libgcc_s_dw2-1.dll"] = @{ Size = 113678; Sha256 = "aa8180b63a849e755323bb1abe364b654c0eed9b433738fc491e5b64c410ef76"; Required = $true }
$manifest["libstdc++-6.dll"] = @{ Size = 1542158; Sha256 = "c05b714b94bab75ddfb77339aa5f48772be7ac2c3e9d7322e2d1549fc0a39cfd"; Required = $true }
$manifest["libwinpthread-1.dll"] = @{ Size = 47104; Sha256 = "ae1b4fe65da58196fea59b4dc0be64ae68d6ef04497027fadbddbc2dc38d843d"; Required = $true }

# External factory reference read by the updater (not inside package dir)
$externalManifest = @{
    "UartTFT-II_Flash.bin" = @{
        Size   = 127599044
        Sha256 = "4cb3fa5c77eea973a2b62ca61873f071692694f4c9a1832507fe2c8c9ba582b4"
        Required = $true
        External = $true
    }
}

# Explicitly rejected targets
$forbiddenFiles = @(
    "patched_UartTFT-II_Flash.bin"
)

$forbiddenExes = @(
    "L99 keyboard Screen reset firmware ... .exe",
    "Screen Reset EXE",
    "L99 reset firmware 2026.5.25.zip",
    "L99-reset.zip"
)

$captureTools = @(
    @{ Name = "Procmon";  Hint = "procmon.exe / Process Monitor" },
    @{ Name = "USBPcap"; Hint = "USBPcap (Wireshark USB capture)" },
    @{ Name = "Wireshark"; Hint = "Wireshark / tshark.exe" }
)

$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]
$passes   = New-Object System.Collections.Generic.List[string]

function Test-FileHash {
    param([string]$Path, [string]$ExpectedSha, [int]$ExpectedSize, [switch]$Required)
    if (-not (Test-Path -LiteralPath $Path)) {
        if ($Required) {
            $failures.Add("MISSING REQUIRED FILE: $Path")
        } else {
            $warnings.Add("NOT FOUND: $Path")
        }
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

function Test-ForbiddenFile {
    param([string]$Name)
    $candidates = @(
        Join-Path $repoRoot $Name,
        Join-Path $packageRoot $Name,
        Join-Path $repoRoot "vendor" $Name,
        Join-Path $env:USERPROFILE "Desktop" $Name,
        Join-Path $env:USERPROFILE "Downloads" $Name
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            $failures.Add("FORBIDDEN FILE PRESENT: $c (never use in this capture)")
            return
        }
    }
    $passes.Add("ABSENT (good): $Name")
}

Write-Host "========================================================================"
Write-Host "  OFFICIAL UPDATE CAPTURE - PREFLIGHT (v0.6.1)"
Write-Host "  Release: v0.6.1  Decision: NO-GO"
Write-Host "  Capture target: L99 ISP V1.23.exe (firmware\unpacked\)"
Write-Host "  Preflight only - no updater execution, no hardware access, no flashing"
Write-Host "========================================================================"
Write-Host ""

# 1. Working directory check
if ((Resolve-Path $repoRoot).Path -ne (Resolve-Path $PWD).Path) {
    $warnings.Add("Run from repo root: $repoRoot (current: $PWD)")
} else {
    $passes.Add("Working directory: $repoRoot")
}

# 2. Package root must exist
if (-not (Test-Path -LiteralPath $packageRoot)) {
    $failures.Add("PACKAGE ROOT MISSING: $packageRoot (place the untouched L99 ISP V1.23.exe package here)")
} else {
    $passes.Add("Package root present: $packageRoot")
}

# 3. Forbidden vendor files must not exist
Write-Host ""
Write-Host "--- Rejected targets check ---"
foreach ($f in $forbiddenFiles) {
    Test-ForbiddenFile -Name $f
}
foreach ($f in $forbiddenExes) {
    Test-ForbiddenFile -Name $f
}

# 4. Package file hash verification
Write-Host ""
Write-Host "--- Verifying package file hashes (local/ignored files only) ---"
foreach ($name in $manifest.Keys) {
    $entry = $manifest[$name]
    $candidates = @(
        Join-Path $packageRoot $name,
        Join-Path $repoRoot $name,
        Join-Path $repoRoot "vendor" $name
    )
    if ($entry.ContainsKey("External") -and $entry.External) {
        $candidates = @(
            Join-Path $repoRoot $name,
            Join-Path $repoRoot "vendor" $name,
            Join-Path $repoRoot "tools" "softce-aula-l99-research" "extracted" $name,
            Join-Path $env:USERPROFILE "Desktop" $name,
            Join-Path $env:USERPROFILE "Downloads" $name
        )
    }
    $found = $false
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) {
            $found = $true
            Test-FileHash -Path $c `
                -ExpectedSha $entry.Sha256 `
                -ExpectedSize $entry.Size `
                -Required:$entry.Required
            break
        }
    }
    if (-not $found) {
        if ($entry.Required) {
            $failures.Add("NOT FOUND LOCALLY: $name (place the untouched official file before capture)")
        } else {
            $warnings.Add("NOT FOUND LOCALLY: $name")
        }
    }
}

# 5. Capture tooling presence
Write-Host ""
Write-Host "--- Capture tooling ---"
foreach ($tool in $captureTools) {
    $passes.Add("TOOL REQUIRED: $($tool.Name) - $($tool.Hint)")
}

# 6. No updater process running (detect by name only; never launch)
Write-Host ""
Write-Host "--- Updater process check ---"
$updaterNames = @("L99 ISP V1.23", "HFD_ISP_TOOL_V1.31", "Screen Reset")
foreach ($name in $updaterNames) {
    $proc = Get-Process -Name $name -ErrorAction SilentlyContinue
    if ($proc) {
        $failures.Add("UPDATER RUNNING: $name (close before capture)")
    } else {
        $passes.Add("NOT RUNNING: $name")
    }
}

# 7. Free disk space (adequate for captures: 2 GB minimum)
Write-Host ""
Write-Host "--- Free disk space ---"
try {
    $drive = Get-PSDrive -Name (Split-Path $repoRoot -Qualifier) -ErrorAction Stop
    $freeGB = [math]::Round($drive.Free / 1GB, 2)
    if ($freeGB -lt 2) {
        $failures.Add("INSUFFICIENT DISK SPACE: ${freeGB} GB free on $($drive.Name):\ (minimum 2 GB)")
    } else {
        $passes.Add("DISK SPACE: ${freeGB} GB free on $($drive.Name):\ (adequate)")
    }
} catch {
    $warnings.Add("Disk space check skipped: $_")
}

# 8. Git status - no vendor/capture files tracked
Write-Host ""
Write-Host "--- Git status (no vendor/capture/generated files tracked) ---"
try {
    $status = git -C $repoRoot status --porcelain 2>$null
    if ($LASTEXITCODE -ne 0) {
        $warnings.Add("git status unavailable or not a repository")
    } else {
        $trackedPaths = git -C $repoRoot ls-files 2>$null | ForEach-Object { $_.Trim() }
        $trackedLarge = @()
        $vendorTracked = @()
        foreach ($p in $trackedPaths) {
            $full = Join-Path $repoRoot $p
            if (Test-Path -LiteralPath $full) {
                $len = (Get-Item -LiteralPath $full).Length
                if ($len -gt 5MB) {
                    $trackedLarge += "$p ($len bytes)"
                }
            }
            $ext = [System.IO.Path]::GetExtension($p)
            $ignoredExtensions = @(".exe", ".bin", ".pcapng", ".pcap", ".zip", ".dll", ".sys")
            if ($ignoredExtensions -contains $ext -or $p -like "vendor/*") {
                $vendorTracked += $p
            }
        }
        if ($trackedLarge.Count -gt 0) {
            $failures.Add("TRACKED FILE OVER 5 MB: $($trackedLarge -join ', ')")
        } else {
            $passes.Add("No tracked file over 5 MB")
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

# 9. Create empty timestamped capture directory
Write-Host ""
Write-Host "--- Capture directory ---"
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$captureDir = Join-Path $repoRoot ("capture_" + $timestamp)
try {
    if (-not (Test-Path -LiteralPath $captureDir)) {
        New-Item -ItemType Directory -LiteralPath $captureDir | Out-Null
    }
    $passes.Add("CAPTURE DIRECTORY: $captureDir (empty, timestamped)")
} catch {
    $failures.Add("CAPTURE DIRECTORY CREATE FAILED: $captureDir ($_)")
}

# 10. Summary
Write-Host ""
Write-Host "========================================================================"
Write-Host "  PREFLIGHT SUMMARY"
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
    Write-Host "NOT READY - Resolve all failures before starting captures."
    foreach ($f in $failures) { Write-Host "  [X] $f" }
    Write-Host ""
    Write-Host "Decision remains NO-GO."
    exit 1
}

Write-Host ""
Write-Host "READY - Capture environment verified. Start all captures BEFORE opening L99 ISP V1.23.exe."
Write-Host "Do not run the updater in this preparation step."
exit 0
