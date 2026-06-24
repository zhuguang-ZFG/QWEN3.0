// 配置管理模块

// 默认唤醒词列表
export const DEFAULT_WAKE_WORDS = '你好小智\n你好小志\n小爱同学\n你好小鑫\n你好小新\n小美同学\n小龙小龙\n喵喵同学\n小滨小滨\n小冰小冰\n嘿你好呀';

// 生成随机MAC地址
function generateRandomMac() {
    const hexDigits = '0123456789ABCDEF';
    let mac = '';
    for (let i = 0; i < 6; i++) {
        if (i > 0) mac += ':';
        for (let j = 0; j < 2; j++) {
            mac += hexDigits.charAt(Math.floor(Math.random() * 16));
        }
    }
    return mac;
}

// 加载配置
export function loadConfig() {
    const deviceMacInput = document.getElementById('deviceMac');
    const deviceNameInput = document.getElementById('deviceName');
    const clientIdInput = document.getElementById('clientId');
    const otaUrlInput = document.getElementById('otaUrl');
    const serverTypeInput = document.getElementById('serverType');
    const limaWsUrlInput = document.getElementById('limaWsUrl');
    const limaTokenInput = document.getElementById('limaToken');
    const wakewordWsUrlInput = document.getElementById('wakewordWsUrl');
    const wakewordEnabledInput = document.getElementById('wakewordEnabled');
    const wakewordListInput = document.getElementById('wakewordList');

    // 从localStorage加载MAC地址，如果没有则生成新的
    let savedMac = localStorage.getItem('xz_tester_deviceMac');
    if (!savedMac) {
        savedMac = generateRandomMac();
        localStorage.setItem('xz_tester_deviceMac', savedMac);
    }
    deviceMacInput.value = savedMac;

    // 从localStorage加载其他配置
    const savedDeviceName = localStorage.getItem('xz_tester_deviceName');
    if (savedDeviceName) {
        deviceNameInput.value = savedDeviceName;
    }

    const savedClientId = localStorage.getItem('xz_tester_clientId');
    if (savedClientId) {
        clientIdInput.value = savedClientId;
    }

    const savedOtaUrl = localStorage.getItem('xz_tester_otaUrl');
    if (savedOtaUrl && otaUrlInput) {
        otaUrlInput.value = savedOtaUrl;
    }

    // LiMa 配置
    const savedServerType = localStorage.getItem('xz_tester_serverType');
    if (savedServerType && serverTypeInput) {
        serverTypeInput.value = savedServerType;
    }

    const savedLimaWsUrl = localStorage.getItem('xz_tester_limaWsUrl');
    if (savedLimaWsUrl && limaWsUrlInput) {
        limaWsUrlInput.value = savedLimaWsUrl;
    }

    const savedLimaToken = localStorage.getItem('xz_tester_limaToken');
    if (savedLimaToken && limaTokenInput) {
        limaTokenInput.value = savedLimaToken;
    }

    // 根据服务器类型切换面板显示
    if (serverTypeInput) {
        toggleConnectionPanel(serverTypeInput.value);
    }

    const savedWakewordWsUrl = localStorage.getItem('xz_tester_wakewordWsUrl');
    if (savedWakewordWsUrl !== null && wakewordWsUrlInput) {
        wakewordWsUrlInput.value = savedWakewordWsUrl;
    }

    const savedWakewordEnabled = localStorage.getItem('xz_tester_wakewordEnabled');
    if (savedWakewordEnabled !== null && wakewordEnabledInput) {
        wakewordEnabledInput.value = savedWakewordEnabled;
    }

    const savedWakewordList = localStorage.getItem('xz_tester_wakewordList');
    if (savedWakewordList !== null && wakewordListInput) {
        wakewordListInput.value = savedWakewordList;
    } else if (wakewordListInput) {
        wakewordListInput.value = DEFAULT_WAKE_WORDS;
    }

    const emojiEnabledInput = document.getElementById('emojiEnabled');
    const savedEmojiEnabled = localStorage.getItem('xz_tester_emojiEnabled');
    if (savedEmojiEnabled !== null && emojiEnabledInput) {
        emojiEnabledInput.value = savedEmojiEnabled;
    }
}

// 切换连接面板显示（LiMa 直连 vs 小智 OTA）
export function toggleConnectionPanel(serverType) {
    const limaPanel = document.getElementById('limaConnection');
    const xiaozhiPanel = document.getElementById('xiaozhiConnection');
    if (limaPanel && xiaozhiPanel) {
        limaPanel.style.display = serverType === 'lima' ? 'block' : 'none';
        xiaozhiPanel.style.display = serverType === 'xiaozhi' ? 'block' : 'none';
    }
}

// 保存配置
export function saveConfig() {
    const deviceMacInput = document.getElementById('deviceMac');
    const deviceNameInput = document.getElementById('deviceName');
    const clientIdInput = document.getElementById('clientId');
    const serverTypeInput = document.getElementById('serverType');
    const wakewordWsUrlInput = document.getElementById('wakewordWsUrl');
    const wakewordEnabledInput = document.getElementById('wakewordEnabled');
    const wakewordListInput = document.getElementById('wakewordList');

    localStorage.setItem('xz_tester_deviceMac', deviceMacInput.value);
    localStorage.setItem('xz_tester_deviceName', deviceNameInput.value);
    localStorage.setItem('xz_tester_clientId', clientIdInput.value);
    const emojiEnabledInput = document.getElementById('emojiEnabled');
    if (emojiEnabledInput) {
        localStorage.setItem('xz_tester_emojiEnabled', emojiEnabledInput.value);
    }
    // LiMa 配置
    if (serverTypeInput) {
        localStorage.setItem('xz_tester_serverType', serverTypeInput.value);
    }
    if (wakewordEnabledInput) {
        localStorage.setItem('xz_tester_wakewordEnabled', wakewordEnabledInput.value);
    }
    if (wakewordListInput) {
        localStorage.setItem('xz_tester_wakewordList', wakewordListInput.value);
    }
    if (wakewordWsUrlInput && wakewordWsUrlInput.value.trim()) {
        localStorage.setItem('xz_tester_wakewordWsUrl', wakewordWsUrlInput.value.trim());
    }
}

// 获取配置值
export function getConfig() {
    // 从DOM获取值
    const deviceMac = document.getElementById('deviceMac')?.value.trim() || '';
    const deviceName = document.getElementById('deviceName')?.value.trim() || '';
    const clientId = document.getElementById('clientId')?.value.trim() || '';
    const emojiEnabled = document.getElementById('emojiEnabled')?.value !== 'false';
    const serverType = document.getElementById('serverType')?.value || 'lima';
    const limaWsUrl = document.getElementById('limaWsUrl')?.value.trim() || '';
    const limaToken = document.getElementById('limaToken')?.value.trim() || '';

    return {
        deviceId: deviceMac,  // 使用MAC地址作为deviceId
        deviceName,
        deviceMac,
        clientId,
        emojiEnabled,
        serverType,
        limaWsUrl,
        limaToken
    };
}

// 保存连接URL
export function saveConnectionUrls() {
    const otaUrl = document.getElementById('otaUrl')?.value.trim() || '';
    const wsUrl = document.getElementById('serverUrl')?.value.trim() || '';
    const limaWsUrl = document.getElementById('limaWsUrl')?.value.trim() || '';
    const limaToken = document.getElementById('limaToken')?.value.trim() || '';
    localStorage.setItem('xz_tester_otaUrl', otaUrl);
    localStorage.setItem('xz_tester_wsUrl', wsUrl);
    localStorage.setItem('xz_tester_limaWsUrl', limaWsUrl);
    localStorage.setItem('xz_tester_limaToken', limaToken);
}
