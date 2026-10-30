# Waits until the three Geofabrik snapshots are fully downloaded (exact published sizes), then runs the
# whole 20 m chain. Started detached so it survives the chat session.
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$snap = Join-Path $root 'data\raw\osm_snapshots'
$sizes = @{ 'southern-zone-240101.osm.pbf' = 465226293; 'india-210101.osm.pbf' = 842017858; 'india-180101.osm.pbf' = 453343586 }
$log = Join-Path $root 'outputs\lu20\logs\wait_then_run.log'
"$(Get-Date -Format HH:mm:ss) waiting for snapshots" | Out-File $log -Append
while ($true) {
    $ok = $true
    foreach ($f in $sizes.Keys) {
        $p = Join-Path $snap $f
        if (-not (Test-Path $p) -or (Get-Item $p).Length -ne $sizes[$f]) { $ok = $false }
    }
    if ($ok) { break }
    Start-Sleep -Seconds 30
}
"$(Get-Date -Format HH:mm:ss) all snapshots complete; starting run_all.py" | Out-File $log -Append
Set-Location $root
& python -u scripts\lu20\run_all.py *> (Join-Path $root 'outputs\lu20\logs\chain_stdout.log')
"$(Get-Date -Format HH:mm:ss) run_all.py finished with exit code $LASTEXITCODE" | Out-File $log -Append
