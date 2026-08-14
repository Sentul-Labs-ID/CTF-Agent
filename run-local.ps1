param(
    [Parameter(Mandatory = $true)]
    [string]$Challenge,

    [string]$Model = "codex/gpt-5.6-terra",

    [int]$MaxChallenges = 1
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$cli = Join-Path $projectRoot ".venv\Scripts\ctf-solve.exe"
$challengePath = if ([System.IO.Path]::IsPathRooted($Challenge)) {
    $Challenge
} else {
    Join-Path $projectRoot $Challenge
}

if (-not (Test-Path -LiteralPath $cli)) {
    throw "CTF Agent belum terpasang: $cli tidak ditemukan."
}

if (-not (Test-Path -LiteralPath (Join-Path $challengePath "metadata.yml"))) {
    throw "metadata.yml tidak ditemukan di: $challengePath"
}

& $cli `
    --challenge $challengePath `
    --models $Model `
    --no-submit `
    --max-challenges $MaxChallenges `
    -v

exit $LASTEXITCODE
