# Codex API switch helper.
#
# Store provider keys in your local environment instead of this file:
#   $env:OPENAI_NEXT_API_KEY = "..."
#   $env:CENTOS_API_KEY = "..."
param(
    [ValidateSet("openai-next", "centos")]
    [string]$Profile = "openai-next"
)

$Profiles = @{
    "openai-next" = @{
        BaseUrl = "https://api.openai-next.com/v1"
        KeyEnv = "OPENAI_NEXT_API_KEY"
        Label = "api.openai-next.com"
    }
    "centos" = @{
        BaseUrl = "https://ai.centos.hk/v1"
        KeyEnv = "CENTOS_API_KEY"
        Label = "ai.centos.hk"
    }
}

$Selected = $Profiles[$Profile]
$env:OPENAI_BASE_URL = $Selected.BaseUrl
$KeyName = $Selected.KeyEnv
$ApiKey = [Environment]::GetEnvironmentVariable($KeyName, "Process")
if (-not $ApiKey) {
    $ApiKey = [Environment]::GetEnvironmentVariable($KeyName, "User")
}

if ($ApiKey) {
    $env:OPENAI_API_KEY = $ApiKey
} else {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    Write-Warning "No API key found in $KeyName; OPENAI_API_KEY was cleared."
}

switch ($Profile) {
    "openai-next" {
        Write-Host "Switched to api.openai-next.com."
    }
    "centos" {
        Write-Host "Switched to ai.centos.hk."
    }
}

Write-Host "Current configuration:"
Write-Host "  Base URL: $env:OPENAI_BASE_URL"
if ($env:OPENAI_API_KEY) {
    Write-Host "  API Key:  loaded from $KeyName"
} else {
    Write-Host "  API Key:  missing"
}
