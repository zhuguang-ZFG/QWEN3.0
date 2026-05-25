# Shared arch checks for LiMa WeChat / wcferry install scripts.

function Get-PeMachineType {
    param([Parameter(Mandatory)][string]$Path)
    $b = [IO.File]::ReadAllBytes($Path)
    if ($b.Length -lt 64 -or $b[0] -ne 0x4D -or $b[1] -ne 0x5A) { return $null }
    $pe = [BitConverter]::ToInt32($b, 0x3c)
    if ($pe -le 0 -or ($pe + 6) -gt $b.Length) { return $null }
    return [BitConverter]::ToUInt16($b, $pe + 4)
}

function Get-PeArchLabel {
    param([Parameter(Mandatory)][string]$Path)
    switch (Get-PeMachineType $Path) {
        0x014c { return "i386 (32-bit)" }
        0x8664 { return "amd64 (64-bit)" }
        default { return "unknown" }
    }
}

function Get-PythonBits {
    $out = & python -c "import struct;print(struct.calcsize(chr(80))*8)" 2>$null
    if (-not $out) { return $null }
    return [int]($out | Select-Object -Last 1)
}

function Test-LiMaWcfHostOk {
    if (-not [Environment]::Is64BitOperatingSystem) {
        $msg = 'Need 64-bit Windows (wcferry sdk.dll is 64-bit). 32-bit Windows cannot run WCF bridge.'
        return @{ Ok = $false; Message = $msg }
    }
    if (-not [Environment]::Is64BitProcess) {
        $msg = 'Run this script from 64-bit PowerShell, not SysWOW64 powershell.exe.'
        return @{ Ok = $false; Message = $msg }
    }
    $bits = Get-PythonBits
    if ($bits -and $bits -ne 64) {
        $msg = "Need 64-bit Python (current: $bits-bit). Install Windows x86-64 Python from python.org."
        return @{ Ok = $false; Message = $msg }
    }
    return @{ Ok = $true; Message = '' }
}

function Write-LiMaWeChatArchBrief {
    Write-Host ''
    Write-Host 'LiMa WCF arch:'
    Write-Host '  Windows OS   : 64-bit required'
    Write-Host '  Python       : 64-bit required'
    Write-Host '  WeChat client: 32-bit (Program Files (x86)) - normal'
    Write-Host '  wcferry DLL  : 64-bit, hooks 32-bit WeChat'
    Write-Host ''
}
