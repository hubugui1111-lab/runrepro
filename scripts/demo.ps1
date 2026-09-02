param(
    [Parameter(Mandatory = $true)]
    [string]$RunUrl,
    [string]$Bundle = ".runrepro-demo",
    [string]$Act = "act"
)

$ErrorActionPreference = "Stop"
if (Test-Path -LiteralPath $Bundle) {
    throw "Refusing to overwrite existing demo bundle: $Bundle"
}

uv run runrepro pull $RunUrl --output $Bundle
uv run runrepro inspect $Bundle
uv run runrepro diff $Bundle
uv run runrepro replay $Bundle --act $Act --timeout 900
