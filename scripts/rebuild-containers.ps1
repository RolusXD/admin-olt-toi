[CmdletBinding()]
param(
    [switch]$NoCache
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

function Invoke-Compose {
    param([Parameter(Mandatory)][string[]]$Arguments)

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($Arguments -join ' ')"
    }
}

Push-Location $projectRoot
try {
    Write-Host "Validating docker-compose.yml..." -ForegroundColor Cyan
    Invoke-Compose -Arguments @("config", "--quiet")

    $buildArguments = @("build")
    if ($NoCache) {
        $buildArguments += "--no-cache"
    }
    $buildArguments += @("backend", "worker", "frontend")

    Write-Host "Building backend, worker and frontend..." -ForegroundColor Cyan
    Invoke-Compose -Arguments $buildArguments

    Write-Host "Recreating containers..." -ForegroundColor Cyan
    Invoke-Compose -Arguments @("up", "-d", "--force-recreate", "backend", "worker", "frontend")

    Write-Host "Container status:" -ForegroundColor Cyan
    Invoke-Compose -Arguments @("ps")
}
finally {
    Pop-Location
}
