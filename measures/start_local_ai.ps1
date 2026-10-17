# Start the portable CPU installation prepared for this workspace, without downloads.
$ErrorActionPreference = 'Stop'
$measureRoot = $PSScriptRoot
try {
    $measureService = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 3
    Write-Output "Ollama este deja pornit: $($measureService.version)"
    exit 0
} catch { }
$measureExecutable = Join-Path $measureRoot 'cache\ollama-cpu\ollama.exe'
if (-not (Test-Path -LiteralPath $measureExecutable)) {
    throw 'Instalarea portabila lipseste. Instaleaza Ollama conform measures/LOCAL_AI.md.'
}
$env:OLLAMA_MODELS = Join-Path $measureRoot 'cache\ollama-models'
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$measureProcess = Start-Process -FilePath $measureExecutable -ArgumentList 'serve' -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $measureRoot 'cache\ollama-server.stdout.log') `
    -RedirectStandardError (Join-Path $measureRoot 'cache\ollama-server.stderr.log')
Write-Output "Ollama pornit in fundal, PID $($measureProcess.Id). Verifica disponibilitatea inainte de inferenta."
