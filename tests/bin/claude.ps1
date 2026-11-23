$python = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $python) {
  & py -3 (Join-Path $PSScriptRoot 'claude') @args
} else {
  & python (Join-Path $PSScriptRoot 'claude') @args
}
exit $LASTEXITCODE
