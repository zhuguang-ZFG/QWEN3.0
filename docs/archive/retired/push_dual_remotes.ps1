# Push origin then gitee (GI-G-1 wrapper)
param(
    [string]$Repo = "D:\GIT",
    [string]$Ref = "HEAD",
    [switch]$DryRun,
    [switch]$Notify
)

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Args = @("scripts/push_dual_remotes.py", "--repo", $Repo, "--ref", $Ref)
if ($DryRun) { $Args += "--dry-run" }
if ($Notify) { $Args += "--notify" }
& python @Args
exit $LASTEXITCODE
