param(
    [Parameter(Mandatory = $true)][string]$Source,
    [Parameter(Mandatory = $true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$patcherPath = Join-Path $PSScriptRoot 'patcher.py'
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 $patcherPath install --source $Source --destination $Destination
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python $patcherPath install --source $Source --destination $Destination
} else {
    throw 'Python 3.8 or later is required to run the local patcher.'
}
exit $LASTEXITCODE
