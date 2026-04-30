# Achat 성능 모니터링 스크립트
# 사용법: .\monitor.ps1 [-InstallPath "C:\Achat"] [-RefreshSec 2]

param(
    [string]$InstallPath = "C:\Achat",
    [int]$RefreshSec = 2
)

$ModelPath   = Join-Path $InstallPath "models\model_q4km.gguf"
$ProcessName = "Achat"
$CpuSampleMs = 800

# 모델 파일 크기 (정적)
$modelSize = if (Test-Path $ModelPath) {
    "{0:N2} GB" -f ((Get-Item $ModelPath).Length / 1GB)
} else {
    "파일 없음 ($ModelPath)"
}

# 시스템 전체 RAM (정적)
$totalRamGB = (Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1MB

function Get-CpuPercent($proc) {
    $c1 = $proc.CPU
    Start-Sleep -Milliseconds $CpuSampleMs
    $proc.Refresh()
    $c2 = $proc.CPU
    $pct = ($c2 - $c1) / ($CpuSampleMs / 1000) / $env:NUMBER_OF_PROCESSORS * 100
    return [math]::Round([math]::Max(0, $pct), 1)
}

function Write-Header($title) {
    Write-Host "[ $title ]" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  Achat 성능 모니터  |  종료: Ctrl+C" -ForegroundColor Cyan
Write-Host ""

while ($true) {
    $proc    = Get-Process $ProcessName -ErrorAction SilentlyContinue
    $sysNow  = Get-CimInstance Win32_OperatingSystem
    $freeGB  = $sysNow.FreePhysicalMemory / 1MB
    $usedGB  = $totalRamGB - $freeGB
    $ramPct  = [math]::Round($usedGB / $totalRamGB * 100, 1)

    Clear-Host
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host "  Achat 성능 모니터  |  $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
    Write-Host ("=" * 44) -ForegroundColor Cyan
    Write-Host ""

    Write-Header "모델"
    Write-Host ("  파일 크기  : {0}" -f $modelSize)
    Write-Host ""

    Write-Header "프로세스 ($ProcessName)"
    if ($proc) {
        $cpu     = Get-CpuPercent $proc
        $wsGB    = [math]::Round($proc.WorkingSet64     / 1GB, 2)
        $privGB  = [math]::Round($proc.PrivateMemorySize64 / 1GB, 2)

        Write-Host ("  RAM (Working Set)  : {0:N2} GB" -f $wsGB)
        Write-Host ("  RAM (Private)      : {0:N2} GB" -f $privGB)
        Write-Host ("  CPU 사용률         : {0} %" -f $cpu)
    } else {
        Write-Host "  앱이 실행중이지 않습니다." -ForegroundColor Red
    }
    Write-Host ""

    Write-Header "시스템 RAM"
    Write-Host ("  전체   : {0:N1} GB" -f $totalRamGB)
    Write-Host ("  사용중 : {0:N1} GB  ({1} %)" -f $usedGB, $ramPct)
    Write-Host ("  여유   : {0:N1} GB" -f $freeGB)
    Write-Host ""

    Write-Host ("  갱신 주기: ${RefreshSec}s  |  Ctrl+C 로 종료") -ForegroundColor DarkGray

    if ($proc) {
        # CPU 샘플링에 이미 $CpuSampleMs 소비됨
        $remain = $RefreshSec - ($CpuSampleMs / 1000)
        if ($remain -gt 0) { Start-Sleep -Seconds $remain }
    } else {
        Start-Sleep -Seconds $RefreshSec
    }
}
