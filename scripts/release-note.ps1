param (
  [Parameter(Mandatory = $true)]
  [string]$TagName,
    
  [Parameter(Mandatory = $false)]
  [string]$ChangelogPath = "CHANGELOG.md",
    
  [Parameter(Mandatory = $false)]
  [string]$OutputPath = "RELEASE_BODY.md"
)

$tag = $TagName -replace '^v', ''

if (-not (Test-Path $ChangelogPath)) {
  Write-Warning "Warning: '$ChangelogPath' not found. Creating an empty release body."
  [System.IO.File]::WriteAllText($OutputPath, "", [System.Text.Encoding]::UTF8)
  Exit 0
}

Write-Host "Extracting release notes for version: v$tag..." -ForegroundColor Cyan

$content = [System.IO.File]::ReadAllText($ChangelogPath, [System.Text.Encoding]::UTF8)

$regex = "(?ms)^## v$([regex]::Escape($tag))\s*\r?\n(.+?)(?=\r?\n## |\z)"

if ($content -match $regex) {
  $releaseBody = $Matches[1].Trim()
  [System.IO.File]::WriteAllText($OutputPath, $releaseBody, [System.Text.Encoding]::UTF8)
  Write-Host "Successfully generated $OutputPath!" -ForegroundColor Green
}
else {
  Write-Warning "Warning: Could not find section '## v$tag' in $ChangelogPath."
  [System.IO.File]::WriteAllText($OutputPath, "", [System.Text.Encoding]::UTF8)
}