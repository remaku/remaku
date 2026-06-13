param (
    [Parameter(Mandatory = $true)]
    [string]$TsFilesRaw
)

$TsFiles = $TsFilesRaw -split ' ' | ForEach-Object { $_.Trim() }

$files = (Get-ChildItem -Path .\remaku -Recurse -Include *.py -Exclude resources_rc.py).FullName

if ($files) {
    Write-Host "Found Python files, running pyside6-lupdate..." -ForegroundColor Cyan
    & pyside6-lupdate $files -ts $TsFiles
}
else {
    Write-Warning "No .py files found. Skipping lupdate."
}