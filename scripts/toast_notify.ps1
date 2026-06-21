param(
    [Parameter(Mandatory=$true)]
    [string]$Title,

    [Parameter(Mandatory=$false)]
    [string]$Message = "",

    [Parameter(Mandatory=$false)]
    [string]$AppId = "LiMa Guardian"
)

# PowerShell 5+ Windows 10/11 Toast — 纯原生 API，不依赖外部模块
try {
    # 初始化 WinRT 类型
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
} catch {
    Write-Error "此系统不支持 Windows Toast API (需要 Windows 10+ / PowerShell 5+)"
    exit 1
}

$xmlContent = @"
<?xml version="1.0" encoding="utf-8"?>
<toast duration="long">
    <visual>
        <binding template="ToastGeneric">
            <text hint-maxLines="1">$Title</text>
            <text>$Message</text>
        </binding>
    </visual>
    <actions>
        <action content="查看" arguments="open" />
        <action content="关闭" arguments="dismiss" activationType="system" />
    </actions>
</toast>
"@

try {
    $xml = New-Object -TypeName Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($xmlContent)
    $toast = New-Object -TypeName Windows.UI.Notifications.ToastNotification -ArgumentList $xml
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($AppId)
    $notifier.Show($toast)
    Write-Output "✅ Toast sent: $Title"
} catch {
    Write-Error "Toast failed: $_"
    exit 1
}