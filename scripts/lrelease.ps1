param (
    [Parameter(Mandatory = $true)]
    [string]$TsFilesRaw,
    
    [Parameter(Mandatory = $true)]
    [string]$TsDir
)

$TsFiles = $TsFilesRaw -split ' ' | ForEach-Object { $_.Trim() }

$existingFiles = $TsFiles | Where-Object { Test-Path $_ }

if ($existingFiles) {
    Write-Host "Compiling .ts files to .qm..." -ForegroundColor Green
    & pyside6-lrelease $existingFiles
    Write-Host "Release complete!" -ForegroundColor Green
}
else {
    Write-Error "Error: No .ts files found in $TsDir. Please run lupdate first."
}