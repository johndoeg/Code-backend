while ($true) {
    Clear-Host
    Write-Host "==============================="
    Write-Host "Starting Flask..."
    Write-Host "==============================="

    python app.py

    Write-Host ""
    Write-Host "Flask exited with code $LASTEXITCODE"
    Write-Host "Restarting in 3 seconds..."
    Start-Sleep -Seconds 3
}