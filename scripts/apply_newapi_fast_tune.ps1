# Push and run apply_newapi_fast_tune.sh on JDCloud (15-min fast path).
# Usage: pwsh -File scripts/apply_newapi_fast_tune.ps1

$ErrorActionPreference = "Stop"
$Repo = Split-Path $PSScriptRoot -Parent
$Host_ = if ($env:LIMA_JDCLOUD_SERVER) { $env:LIMA_JDCLOUD_SERVER } else { "117.72.118.95" }
$Key = if ($env:LIMA_DEPLOY_KEY_PATH) { $env:LIMA_DEPLOY_KEY_PATH } else { "$env:USERPROFILE\.ssh\id_ed25519" }

$sshArgs = @("-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-o", "StrictHostKeyChecking=accept-new")
if (Test-Path $Key) { $sshArgs += @("-i", $Key) }

$local = Join-Path $Repo "deploy\jdcloud\apply_newapi_fast_tune.sh"
if (-not (Test-Path $local)) { throw "missing $local" }

Write-Host "=== Fast-tune NewAPI on $Host_ ===" -ForegroundColor Cyan
# Prefer key; if BatchMode fails, user can set LIMA_JDCLOUD_SSH_PASS and we use paramiko via python helper
try {
    scp @sshArgs $local "root@${Host_}:/tmp/apply_newapi_fast_tune.sh"
    ssh @sshArgs "root@$Host_" "chmod +x /tmp/apply_newapi_fast_tune.sh && bash /tmp/apply_newapi_fast_tune.sh"
} catch {
    Write-Host "SSH key failed, trying paramiko password from env LIMA_JDCLOUD_SSH_PASS ..." -ForegroundColor Yellow
    $pass = $env:LIMA_JDCLOUD_SSH_PASS
    if (-not $pass) { throw "Set LIMA_JDCLOUD_SSH_PASS or fix SSH key. $_" }
    $py = Join-Path $Repo ".venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { $py = "python" }
    & $py -c @"
import paramiko, pathlib
host='$Host_'
password='''$pass'''
script=pathlib.Path(r'$local').read_text(encoding='utf-8')
c=paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(host, username='root', password=password, timeout=25, allow_agent=False, look_for_keys=False)
sftp=c.open_sftp()
with sftp.file('/tmp/apply_newapi_fast_tune.sh','w') as f: f.write(script)
sftp.close()
stdin,stdout,stderr=c.exec_command('chmod +x /tmp/apply_newapi_fast_tune.sh && bash /tmp/apply_newapi_fast_tune.sh', timeout=180)
print(stdout.read().decode('utf-8','replace'))
err=stderr.read().decode('utf-8','replace')
if err: print(err)
code=stdout.channel.recv_exit_status()
c.close()
raise SystemExit(code)
"@
}

Write-Host "=== Next: Web UI headers + Kimi CLI base_url ===" -ForegroundColor Green
Write-Host "Doc: docs/ops/NEWAPI_KIMI_IMPROVEMENT_PLAN_CN.md"
