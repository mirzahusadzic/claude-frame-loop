$python = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $python) {
  & py -3 (Join-Path $PSScriptRoot 'gadfly') @args
} else {
  & python (Join-Path $PSScriptRoot 'gadfly') @args
}
exit $LASTEXITCODE
