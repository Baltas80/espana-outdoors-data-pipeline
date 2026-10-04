param(
    [Parameter(Mandatory = $true)]
    [string]$Root,

    [string]$Catalog = "data/catalog.sqlite",

    [ValidateSet("auto", "always", "never")]
    [string]$HashMode = "auto",

    [int]$ProgressEvery = 100
)

$ErrorActionPreference = "Stop"

Write-Host "España Outdoor Data Pipeline - scanner"
Write-Host "Root: $Root"
Write-Host "Catalog: $Catalog"
Write-Host "Hash mode: $HashMode"

python -m espana_outdoors_pipeline.scanner `
    --root $Root `
    --catalog $Catalog `
    --hash-mode $HashMode `
    --progress-every $ProgressEvery

if ($LASTEXITCODE -ne 0) {
    throw "Scanner failed with exit code $LASTEXITCODE"
}
