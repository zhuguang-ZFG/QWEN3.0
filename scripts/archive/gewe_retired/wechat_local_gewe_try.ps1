# Try self-hosted Gewechat on Windows Docker (Plan B when GeWeAPI registration fails)
$ErrorActionPreference = "Stop"
$DataDir = "$env:USERPROFILE\gewechat-data"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null

docker ps -a --filter name=gewe-local --format "{{.Names}}" | ForEach-Object {
    if ($_ -eq "gewe-local") { docker rm -f gewe-local 2>$null }
}

Write-Host "=== Pull gewe image ==="
docker pull registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest
docker tag registry.cn-hangzhou.aliyuncs.com/gewe/gewe:latest gewe-local-img

Write-Host "=== Run container ==="
docker run -d --name gewe-local --restart=unless-stopped `
  -v "${DataDir}:/root/temp" -p 2531:2531 -p 2532:2532 `
  --privileged gewe-local-img /usr/sbin/init

Write-Host "Waiting 60s for mysql/gewe..."
Start-Sleep -Seconds 60

Write-Host "=== getTokenId ==="
$tokResp = curl.exe -s -m 15 -X POST "http://127.0.0.1:2531/v2/api/tools/getTokenId" -H "Content-Type: application/json" -d "{}"
Write-Host $tokResp

Write-Host "=== getLoginQrCode ==="
if ($tokResp -match '"data"\s*:\s*"([a-f0-9]+)"') {
    $tok = $Matches[1]
    $qrBody = '{"appId":"","regionId":"330000","proxyIp":"","type":"ipad"}'
    $qrResp = curl.exe -s -m 90 -X POST "http://127.0.0.1:2531/v2/api/login/getLoginQrCode" `
        -H "Content-Type: application/json" -H "X-GEWE-TOKEN: $tok" -d $qrBody
    Write-Host $qrResp.Substring(0, [Math]::Min(500, $qrResp.Length))
    if ($qrResp -match '"ret"\s*:\s*200') {
        Write-Host "OK: open http://127.0.0.1:2531 or use scripts/wechat_joint_debug.py refresh-qr --gewe-base http://127.0.0.1:2531/v2/api"
    }
} else {
    Write-Host "Token failed; check: docker logs gewe-local --tail 50"
}
