# Downloads (or resumes) the Geofabrik dated OSM snapshots used by 01b_osm_geofabrik.py
# (the first three for 2017/2020/2023, the other four for the final maps of 2018/2019/2021/2022).
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$snap = Join-Path $root 'data\raw\osm_snapshots'
New-Item -ItemType Directory -Force $snap | Out-Null
$log = Join-Path $root 'outputs\lu20\logs\download_snapshots.log'
foreach ($u in 'asia/india/southern-zone-240101.osm.pbf', 'asia/india-210101.osm.pbf', 'asia/india-180101.osm.pbf',
              'asia/india-190101.osm.pbf', 'asia/india-200101.osm.pbf', 'asia/india-220101.osm.pbf', 'asia/india-230101.osm.pbf') {
    $f = Join-Path $snap (Split-Path $u -Leaf)
    for ($k = 0; $k -lt 20; $k++) {
        & curl.exe -s -L -C - --retry 5 -o $f "https://download.geofabrik.de/$u"
        if ($LASTEXITCODE -eq 0) { break }
        "$(Get-Date -Format HH:mm:ss) $u curl exit $LASTEXITCODE, retrying" | Out-File $log -Append
        Start-Sleep -Seconds 30
    }
    "$(Get-Date -Format HH:mm:ss) $u done: $((Get-Item $f).Length) bytes" | Out-File $log -Append
}
