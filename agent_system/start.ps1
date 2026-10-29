$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverDir = Join-Path (Split-Path -Parent $root) "mc_server"
$logPath = Join-Path $serverDir "logs\latest.log"
$pythonPath = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path (Join-Path $root ".env"))) {
    throw "Missing $root\.env. Copy .env.example to .env and set GOOGLE_API_KEY and RCON_PASSWORD."
}

if (-not (Test-Path $pythonPath)) {
    $pythonPath = "python"
}

$serverProcess = $null
$agentProcess = $null

# Remove stale log so we only check the current session
if (Test-Path $logPath) {
    Remove-Item $logPath -Force -ErrorAction SilentlyContinue
}

try {
    if (-not (Test-Path (Join-Path $serverDir "paper.jar"))) {
        throw "Missing mc_server/paper.jar. Install PaperMC before starting the combined launcher."
    }

    Write-Host "[+] Starting PaperMC server..."
    $serverProcess = Start-Process `
        -FilePath "java" `
        -ArgumentList "-Xms2G", "-Xmx2G", "-jar", "paper.jar", "--nogui" `
        -WorkingDirectory $serverDir `
        -PassThru
    Write-Host "[+] PaperMC PID: $($serverProcess.Id)"

    Write-Host "[+] Waiting for PaperMC readiness..."
    $serverReady = $false
    $deadline = (Get-Date).AddSeconds(120)

    while ((Get-Date) -lt $deadline) {
        if ($serverProcess.HasExited) {
            throw "PaperMC exited before reporting readiness."
        }

        # Check if the fresh server boot completed
        $doneFound = $false
        if (Test-Path $logPath) {
            try {
                $doneFound = (Get-Content $logPath -ErrorAction SilentlyContinue | Select-String -Pattern "Done \(" -Quiet)
            }
            catch {
                $doneFound = $false
            }
        }

        # Check RCON only after the server finishes loading
        if ($doneFound) {
            try {
                $connection = New-Object System.Net.Sockets.TcpClient
                $connection.Connect("127.0.0.1", 25575)
                $serverReady = $connection.Connected
                $connection.Dispose()
                if ($serverReady) {
                    break
                }
            }
            catch {
                # Port not open yet; retry next loop
            }
        }

        Start-Sleep -Seconds 1
    }

    if (-not $serverReady) {
        throw "Timed out waiting for PaperMC Done log and RCON readiness."
    }

    Write-Host "[+] PaperMC is online and RCON is ready."
    Write-Host "[+] Starting the Minecraft assistant..."
    $agentProcess = Start-Process `
        -FilePath $pythonPath `
        -ArgumentList "-m", "agent_system.main" `
        -WorkingDirectory $root `
        -NoNewWindow `
        -PassThru
    Write-Host "[+] Assistant process started (PID: $($agentProcess.Id))."
    Write-Host "[+] Both processes are running. Press Ctrl+C to stop both."

    while (-not $agentProcess.HasExited -and -not $serverProcess.HasExited) {
        Start-Sleep -Seconds 1
    }
}
catch {
    Write-Error $_
}
finally {
    foreach ($process in @($agentProcess, $serverProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Write-Host "[+] Stopping PID $($process.Id)..."
            Stop-Process -Id $process.Id -Force
        }
    }
}