param(
    [string]$BackupDirectory = 'F:\Dev\Backups\EquipED\daily',
    [string]$PostgresBin = 'F:\Dev\Servers\PostgreSQL\bin',
    [ValidateRange(7, 365)][int]$RetentionDays = 14
)

$ErrorActionPreference = 'Stop'
$oldPassfile = $env:PGPASSFILE
$oldTimeout = $env:PGCONNECT_TIMEOUT
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
$temporary = Join-Path $BackupDirectory "equiped-$stamp.dump.partial"
$archive = Join-Path $BackupDirectory "equiped-$stamp.dump"
$lock = $null

try {
    if (-not (Test-Path (Join-Path $BackupDirectory 'pgpass.conf'))) {
        throw 'Protected backup credential file is missing.'
    }
    # Prevent a manual run from overlapping the scheduled run.
    $lock = [IO.File]::Open(
        (Join-Path $BackupDirectory 'backup.lock'),
        [IO.FileMode]::OpenOrCreate,
        [IO.FileAccess]::ReadWrite,
        [IO.FileShare]::None
    )
    $env:PGPASSFILE = Join-Path $BackupDirectory 'pgpass.conf'
    $env:PGCONNECT_TIMEOUT = '15'
    $output = & "$PostgresBin\pg_dump.exe" -w -h 127.0.0.1 -p 5432 `
        -U equiped_backup -d equiped --format=custom --no-owner --no-privileges `
        --file=$temporary 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw 'pg_dump failed; incomplete archive will not be promoted.'
    }
    $toc = & "$PostgresBin\pg_restore.exe" --list $temporary 2>&1
    if ($LASTEXITCODE -ne 0 -or (Get-Item $temporary).Length -eq 0) {
        throw 'Backup archive validation failed.'
    }
    # Read/decompress every data block, not only the archive index.
    $output = & "$PostgresBin\pg_restore.exe" --file=NUL $temporary 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw 'Backup archive data-block validation failed.'
    }
    Move-Item $temporary $archive
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash
    "$hash  $([IO.Path]::GetFileName($archive))" |
        Set-Content -Encoding ASCII "$archive.sha256"
    $toc | Set-Content -Encoding UTF8 "$archive.toc.txt"
    [pscustomobject]@{
        Success = $true
        CompletedAt = (Get-Date).ToString('o')
        Archive = $archive
        Bytes = (Get-Item $archive).Length
        SHA256 = $hash
        TableDataEntries = @($toc | Where-Object { $_ -match ' TABLE DATA ' }).Count
        RetentionDays = $RetentionDays
    } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $BackupDirectory 'last-success.json')

    # Prune only this script's completed archives, and only after a successful dump.
    $cutoff = (Get-Date).AddDays(-$RetentionDays)
    Get-ChildItem $BackupDirectory -File -Filter 'equiped-*.dump' |
        Where-Object {
            $_.Name -match '^equiped-\d{8}-\d{6}-\d{3}\.dump$' -and
            $_.LastWriteTime -lt $cutoff
        } | ForEach-Object {
            $oldArchive = $_.FullName
            Remove-Item -LiteralPath $oldArchive
            foreach ($suffix in @('.sha256', '.toc.txt')) {
                if (Test-Path "$oldArchive$suffix") {
                    Remove-Item -LiteralPath "$oldArchive$suffix"
                }
            }
        }
    Write-Output "Backup verified: $archive"
} catch {
    [pscustomobject]@{
        Success = $false
        FailedAt = (Get-Date).ToString('o')
        Error = 'Backup failed. Inspect database/service availability and protected credentials.'
    } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $BackupDirectory 'last-failure.json')
    throw 'EquipED backup failed; no credentials or database records are logged.'
} finally {
    if ($null -ne $lock) { $lock.Dispose() }
    $env:PGPASSFILE = $oldPassfile
    $env:PGCONNECT_TIMEOUT = $oldTimeout
}
