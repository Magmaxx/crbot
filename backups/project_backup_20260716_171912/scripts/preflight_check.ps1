param(
    [string]$ProjectRoot = ".",
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

function Read-EnvMap {
    param([string]$Path)
    $map = @{}
    if (!(Test-Path $Path)) { return $map }

    $lines = Get-Content $Path
    foreach ($line in $lines) {
        $trim = $line.Trim()
        if ([string]::IsNullOrWhiteSpace($trim)) { continue }
        if ($trim.StartsWith("#")) { continue }
        $idx = $trim.IndexOf("=")
        if ($idx -lt 1) { continue }
        $k = $trim.Substring(0, $idx).Trim()
        $v = $trim.Substring($idx + 1).Trim()
        $map[$k] = $v
    }
    return $map
}

function Assert-Path {
    param([string]$Path, [string]$Name)
    if (Test-Path $Path) {
        Write-Output "[OK] $Name => $Path"
        return $true
    } else {
        Write-Output "[FAIL] $Name => $Path"
        return $false
    }
}

$ok = $true

function Try-ParseFloat {
    param([string]$Value)
    $out = 0.0
    $ci = [System.Globalization.CultureInfo]::InvariantCulture
    $styles = [System.Globalization.NumberStyles]::Float
    $parsed = [double]::TryParse($Value, $styles, $ci, [ref]$out)
    return @{ ok = $parsed; value = $out }
}

if (!(Test-Path $ProjectRoot)) {
    throw "Project root not found: $ProjectRoot"
}

Push-Location $ProjectRoot
try {
    $ok = (Assert-Path ".\scripts\backup_project.ps1" "backup script") -and $ok
    $ok = (Assert-Path ".\scripts\restore_project.ps1" "restore script") -and $ok
    $ok = (Assert-Path ".\RUNBOOK.md" "runbook") -and $ok
    $ok = (Assert-Path ".\backups" "backups directory") -and $ok

    $envMap = Read-EnvMap -Path $EnvFile

    $required = @(
        "EXECUTION_ENABLED",
        "PAPER_ONLY",
        "USE_TESTNET",
        "DEFAULT_RISK_PROFILE",
        "MAX_NOTIONAL_PCT",
        "ORDER_SIZE_PCT"
    )

    foreach ($k in $required) {
        if ($envMap.ContainsKey($k)) {
            Write-Output "[OK] env key exists: $k=$($envMap[$k])"
        } else {
            Write-Output "[WARN] env key missing: $k"
            $ok = $false
        }
    }

    if ($envMap.ContainsKey("EXECUTION_ENABLED") -and $envMap["EXECUTION_ENABLED"] -eq "0") {
        Write-Output "[OK] Kill-switch default safe (EXECUTION_ENABLED=0)"
    } else {
        Write-Output "[WARN] Kill-switch not in safe default (expected EXECUTION_ENABLED=0)"
        $ok = $false
    }

    if ($envMap.ContainsKey("DEFAULT_RISK_PROFILE")) {
        $rp = $envMap["DEFAULT_RISK_PROFILE"].ToLower()
        if ($rp -in @("low", "balanced", "aggressive")) {
            Write-Output "[OK] Risk profile valid: $rp"
        } else {
            Write-Output "[FAIL] Risk profile invalid: $rp"
            $ok = $false
        }
    }

    if ($envMap.ContainsKey("ORDER_SIZE_PCT")) {
        $r = Try-ParseFloat $envMap["ORDER_SIZE_PCT"]
        if ($r.ok -and $r.value -gt 0 -and $r.value -le 1) {
            Write-Output "[OK] ORDER_SIZE_PCT in range (0,1]: $($envMap["ORDER_SIZE_PCT"])"
        } else {
            Write-Output "[FAIL] ORDER_SIZE_PCT must be numeric in range (0,1]: $($envMap["ORDER_SIZE_PCT"])"
            $ok = $false
        }
    }

    if ($envMap.ContainsKey("MAX_NOTIONAL_PCT")) {
        $r = Try-ParseFloat $envMap["MAX_NOTIONAL_PCT"]
        if ($r.ok -and $r.value -gt 0 -and $r.value -le 1) {
            Write-Output "[OK] MAX_NOTIONAL_PCT in range (0,1]: $($envMap["MAX_NOTIONAL_PCT"])"
        } else {
            Write-Output "[FAIL] MAX_NOTIONAL_PCT must be numeric in range (0,1]: $($envMap["MAX_NOTIONAL_PCT"])"
            $ok = $false
        }
    }

    if ($envMap.ContainsKey("BINANCE_API_KEY")) {
        $apiKey = $envMap["BINANCE_API_KEY"]
        if ([string]::IsNullOrWhiteSpace($apiKey)) {
            Write-Output "[WARN] BINANCE_API_KEY is empty"
        } elseif ($apiKey.Length -lt 16) {
            Write-Output "[WARN] BINANCE_API_KEY seems too short"
        } else {
            Write-Output "[OK] BINANCE_API_KEY basic format check passed"
        }
    } else {
        Write-Output "[WARN] BINANCE_API_KEY not set (acceptable for paper/test setup)"
    }

    if ($envMap.ContainsKey("BINANCE_API_SECRET")) {
        $apiSecret = $envMap["BINANCE_API_SECRET"]
        if ([string]::IsNullOrWhiteSpace($apiSecret)) {
            Write-Output "[WARN] BINANCE_API_SECRET is empty"
        } elseif ($apiSecret.Length -lt 16) {
            Write-Output "[WARN] BINANCE_API_SECRET seems too short"
        } else {
            Write-Output "[OK] BINANCE_API_SECRET basic format check passed"
        }
    } else {
        Write-Output "[WARN] BINANCE_API_SECRET not set (acceptable for paper/test setup)"
    }

    if ($ok) {
        Write-Output "PREFLIGHT_STATUS=OK"
        exit 0
    } else {
        Write-Output "PREFLIGHT_STATUS=FAIL"
        exit 2
    }
}
finally {
    Pop-Location
}
