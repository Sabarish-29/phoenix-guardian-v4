# Phoenix Guardian V5 — Demo Startup Checklist (PowerShell)
# Run this 10 minutes before presenting
# Usage: powershell -File scripts/demo_start.ps1

Write-Host ""
Write-Host "🛡️  Phoenix Guardian V5 — Demo Startup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allOk = $true

# 1. Check backend is running
Write-Host -NoNewline "Backend running... "
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/health" -TimeoutSec 5 -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        Write-Host "✅" -ForegroundColor Green
    } else {
        Write-Host "❌ HTTP $($resp.StatusCode)" -ForegroundColor Red
        $allOk = $false
    }
} catch {
    Write-Host "❌ Start with: python -m uvicorn phoenix_guardian.api.main:app --reload --port 8000" -ForegroundColor Red
    $allOk = $false
}

# 2. Check frontend (optional)
Write-Host -NoNewline "Frontend running... "
try {
    $resp = Invoke-WebRequest -Uri "http://localhost:3000" -TimeoutSec 3 -ErrorAction Stop
    Write-Host "✅" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Not running (cd phoenix-ui && npm start)" -ForegroundColor Yellow
}

# 3. Check Redis
Write-Host -NoNewline "Redis running... "
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $tcp.Connect("localhost", 6379)
    $tcp.Close()
    Write-Host "✅" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Redis not running — Ghost Protocol uses in-memory fallback" -ForegroundColor Yellow
}

# 4. Seed ghost protocol
Write-Host -NoNewline "Seeding Ghost Protocol... "
try {
    $env:OPENBLAS_NUM_THREADS = "1"
    python scripts/seed_ghost_protocol.py 2>&1 | Out-Null
    Write-Host "✅" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Seed script error" -ForegroundColor Yellow
}

# 5. Check agent health endpoints
$agents = @("treatment-shadow", "silent-voice", "zebra-hunter")
foreach ($agent in $agents) {
    Write-Host -NoNewline "Agent $agent... "
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/$agent/health" -TimeoutSec 5 -ErrorAction Stop
        $body = $resp.Content | ConvertFrom-Json
        if ($body.status -eq "healthy") {
            Write-Host "✅" -ForegroundColor Green
        } else {
            Write-Host "⚠️  Status: $($body.status)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "❌ Not reachable" -ForegroundColor Red
        $allOk = $false
    }
}

# 6. Pre-warm caches
Write-Host ""
Write-Host -NoNewline "Pre-warming caches... "
try {
    $env:OPENBLAS_NUM_THREADS = "1"
    python scripts/demo_warmup.py 2>&1 | Out-Null
    Write-Host "✅ Done" -ForegroundColor Green
} catch {
    Write-Host "⚠️  Warmup script failed" -ForegroundColor Yellow
}

# 7. Summary
Write-Host ""
if ($allOk) {
    Write-Host "🚀 All checks passed. Opening demo..." -ForegroundColor Green
} else {
    Write-Host "⚠️  Some checks failed. Fix issues before presenting." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Demo URL: http://localhost:3000/v5-dashboard" -ForegroundColor White
Write-Host ""
Write-Host "Demo order:" -ForegroundColor Cyan
Write-Host "  1. Dashboard overview (30 sec)"
Write-Host "  2. Treatment Shadow — Rajesh Kumar (45 sec)"
Write-Host "  3. Silent Voice — Lakshmi Devi + toggle (45 sec)"
Write-Host "  4. Zebra Hunter — Priya Sharma + timeline (45 sec)"
Write-Host "  5. Zebra Hunter — Arjun Nair + Ghost Protocol (30 sec)"
Write-Host "  6. Closing line (15 sec)"
Write-Host ""
Write-Host "TOTAL: 3 minutes 30 seconds" -ForegroundColor Cyan
Write-Host ""
