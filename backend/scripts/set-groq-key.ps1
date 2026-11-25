# Prompts for a Groq API key (hidden input) and writes it into backend/.env.
# Creates backend/.env from .env.example if it does not exist. The key is never printed.
$ErrorActionPreference = "Stop"
$backend = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $backend ".env"
if (-not (Test-Path $envPath)) {
    Copy-Item (Join-Path $backend ".env.example") $envPath
}

$secure = Read-Host "Paste your Groq API key (input is hidden)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if (-not $key) {
    Write-Host "No key entered. backend/.env was not changed."
    exit 1
}

$lines = Get-Content $envPath | ForEach-Object {
    if ($_ -match '^GROQ_API_KEY=') { "GROQ_API_KEY=$key" }
    elseif ($_ -match '^LLM_MODE=') { "LLM_MODE=live" }
    else { $_ }
}
# UTF-8 without BOM so python-dotenv reads the first line cleanly.
[IO.File]::WriteAllLines($envPath, [string[]]$lines)
Write-Host "Saved to $envPath (key length $($key.Length), LLM_MODE=live)."
