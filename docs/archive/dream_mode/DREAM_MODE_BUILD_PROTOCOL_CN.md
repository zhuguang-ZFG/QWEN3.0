# 构建系统与协议层实现分析

> 本文档详细分析 ESP32 固件的构建系统和协议层具体实现。

## 目录

1. [构建系统](#1-构建系统)
2. [协议层实现](#2-协议层实现)
3. [MCP 服务器实现](#3-mcp-服务器实现)

---

## 1. 构建系统

### 架构概览

```
esp32S_XYZ/
├─ Makefile                    # 顶层构建入口
├─ firmware/
│  ├─ u1-grbl/                # U1 运动控制器固件 (PlatformIO)
│  └─ u8-xiaozhi/             # U8 主板固件 (ESP-IDF)
│     ├─ CMakeLists.txt        # 项目级 CMake
│     ├─ main/
│     │  └─ CMakeLists.txt     # 主组件 CMake (1200+ 行)
│     └─ sdkconfig.defaults*   # 芯片默认配置
└─ server/
   └─ xiaozhi-esp32-server/   # Java BusinessServer (Maven)
```

### 顶层 Makefile

```makefile
# 构建目标
make build-u1     # PlatformIO 构建 U1 固件
make build-u8     # ESP-IDF 构建 U8 固件
make build-server # Maven 构建 Java 服务

# 烧录目标
make flash-u1     # 烧录 U1 (自动检测串口)
make flash-u8     # 烧录 U8 (自动检测串口)

# 测试目标
make test         # 运行所有测试
make test-schema  # Schema 验证
make test-gpio    # GPIO 静态检查
make test-python  # Python 单元测试
make test-fake    # Fake 集成测试

# 工具目标
make lint         # 代码检查
make clean        # 清理构建产物
make fake-u1      # 启动 U1 模拟器
make fake-ai      # 启动 AI 模拟器
```

### U8 固件构建系统 (ESP-IDF CMake)

#### 项目级 CMakeLists.txt

```cmake
cmake_minimum_required(VERSION 3.16)
add_compile_options(-Wno-missing-field-initializers)
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
idf_build_set_property(MINIMAL_BUILD ON)
set(PROJECT_VER "2.2.6")
project(xiaozhi)
```

#### 主组件 CMakeLists.txt (1200+ 行)

**源文件组织**：

```cmake
# 核心源文件
set(SOURCES
    "audio/audio_codec.cc"
    "audio/audio_service.cc"
    "audio/demuxer/ogg_demuxer.cc"
    "audio/codecs/*.cc"           # 6 种音频编解码器
    "audio/processors/*.cc"       # 音频处理器
    "led/*.cc"                    # LED 控制
    "display/*.cc"                # 显示模块
    "protocols/*.cc"              # 协议实现
    "mcp_server.cc"
    "system_info.cc"
    "application.cc"
    "ota.cc"
    "settings.cc"
    "device_state_machine.cc"
    "assets.cc"
    "main.cc"
)

# 板型公共文件
list(APPEND SOURCES
    "boards/common/board.cc"
    "boards/common/wifi_board.cc"
    "boards/common/ml307_board.cc"
    # ... 更多公共模块
)
```

**板型选择系统**：

```cmake
# 基于 Kconfig 选择板型
if(CONFIG_BOARD_TYPE_ESP_BOX_3)
    set(BOARD_TYPE "esp-box-3")
    set(BUILTIN_TEXT_FONT font_noto_basic_20_4)
    set(BUILTIN_ICON_FONT font_awesome_20_4)
    set(DEFAULT_EMOJI_COLLECTION noto-emoji_128)
elseif(CONFIG_BOARD_TYPE_M5STACK_CARDPUTER_ADV)
    set(BOARD_TYPE "m5stack-cardputer-adv")
    # ...
endif()

# 加载板型特定源文件
file(GLOB BOARD_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/boards/${BOARD_TYPE}/*.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/boards/${BOARD_TYPE}/*.c
)
list(APPEND SOURCES ${BOARD_SOURCES})
```

**条件编译**：

```cmake
# 音频处理器选择
if(CONFIG_USE_AUDIO_PROCESSOR)
    list(APPEND SOURCES "audio/processors/afe_audio_processor.cc")
else()
    list(APPEND SOURCES "audio/processors/no_audio_processor.cc")
endif()

# 唤醒词选择 (ESP32-S3/P4 vs 其他)
if(CONFIG_IDF_TARGET_ESP32S3 OR CONFIG_IDF_TARGET_ESP32P4)
    list(APPEND SOURCES "audio/wake_words/afe_wake_word.cc")
    list(APPEND SOURCES "audio/wake_words/custom_wake_word.cc")
else()
    list(APPEND SOURCES "audio/wake_words/esp_wake_word.cc")
endif()

# ESP32 特殊处理
if(CONFIG_IDF_TARGET_ESP32)
    list(REMOVE_ITEM SOURCES
        "audio/codecs/box_audio_codec.cc"
        "audio/codecs/es8388_audio_codec.cc"
        # ... 更多移除
    )
endif()
```

**语言本地化**：

```cmake
# 支持 20+ 种语言
if(CONFIG_LANGUAGE_ZH_CN)
    set(LANG_DIR "zh-CN")
elseif(CONFIG_LANGUAGE_EN_US)
    set(LANG_DIR "en-US")
# ... 更多语言
endif()

# 语言文件处理
set(LANG_JSON "${CMAKE_CURRENT_SOURCE_DIR}/assets/locales/${LANG_DIR}/language.json")
set(LANG_HEADER "${CMAKE_CURRENT_SOURCE_DIR}/assets/lang_config.h")

# 生成语言配置头文件
add_custom_command(
    OUTPUT ${LANG_HEADER}
    COMMAND python ${PROJECT_DIR}/scripts/gen_lang.py
            --language "${LANG_DIR}"
            --output "${LANG_HEADER}"
    DEPENDS ${LANG_JSON} ${PROJECT_DIR}/scripts/gen_lang.py
)
```

**资源管理**：

```cmake
# 字体资源
set(BUILTIN_TEXT_FONT font_puhui_basic_20_4)
set(BUILTIN_ICON_FONT font_awesome_20_4)
set(DEFAULT_EMOJI_COLLECTION twemoji_64)

# 音频资源
file(GLOB LANG_SOUNDS ${CMAKE_CURRENT_SOURCE_DIR}/assets/locales/${LANG_DIR}/*.ogg)
file(GLOB COMMON_SOUNDS ${CMAKE_CURRENT_SOURCE_DIR}/assets/common/*.ogg)

# 资源分区
partition_table_get_partition_info(size "--partition-name assets" "size")
partition_table_get_partition_info(offset "--partition-name assets" "offset")
```

### 组件依赖

```cmake
idf_component_register(SRCS ${SOURCES}
    EMBED_FILES ${LANG_SOUNDS} ${COMMON_SOUNDS}
    INCLUDE_DIRS ${INCLUDE_DIRS}
    PRIV_REQUIRES
        esp_pm              # 电源管理
        esp_psram           # PSRAM 支持
        esp_netif           # 网络接口
        esp_http_server     # HTTP 服务器
        esp_driver_gpio     # GPIO 驱动
        esp_driver_uart     # UART 驱动
        esp_driver_spi      # SPI 驱动
        esp_driver_i2c      # I2C 驱动
        esp_driver_i2s      # I2S 驱动
        esp_driver_jpeg     # JPEG 解码
        esp_driver_ppa      # PPA 加速
        app_update          # 应用更新
        spi_flash           # Flash 操作
        bt                  # 蓝牙
        fatfs               # 文件系统
)
```

---

## 2. 协议层实现

### WebSocket 协议 (`websocket_protocol.cc`)

#### 连接建立

```cpp
bool WebsocketProtocol::OpenAudioChannel() {
    // 1. 读取配置
    Settings settings("websocket", false);
    std::string url = settings.GetString("url");
    std::string token = settings.GetString("token");
    int version = settings.GetInt("version");

    // 2. 创建 WebSocket
    auto network = Board::GetInstance().GetNetwork();
    websocket_ = network->CreateWebSocket(1);

    // 3. 设置 HTTP 头
    if (!token.empty()) {
        if (token.find(" ") == std::string::npos) {
            token = "Bearer " + token;
        }
        websocket_->SetHeader("Authorization", token.c_str());
    }
    websocket_->SetHeader("Protocol-Version", std::to_string(version_).c_str());
    websocket_->SetHeader("Device-Id", SystemInfo::GetMacAddress().c_str());
    websocket_->SetHeader("Client-Id", Board::GetInstance().GetUuid().c_str());

    // 4. 注册回调
    websocket_->OnData([this](const char* data, size_t len, bool binary) {
        if (binary) {
            // 处理二进制音频数据
            ParseBinaryAudio(data, len);
        } else {
            // 处理 JSON 控制消息
            auto root = cJSON_ParseWithLength(data, len);
            ParseJsonMessage(root);
        }
        last_incoming_time_ = std::chrono::steady_clock::now();
    });

    // 5. 连接服务器
    if (!websocket_->Connect(url.c_str())) {
        SetError("Failed to connect");
        return false;
    }

    // 6. 发送 hello
    auto message = GetHelloMessage();
    SendText(message);

    // 7. 等待服务器 hello (10秒超时)
    EventBits_t bits = xEventGroupWaitBits(
        event_group_handle_,
        WEBSOCKET_PROTOCOL_SERVER_HELLO_EVENT,
        pdTRUE, pdFALSE,
        pdMS_TO_TICKS(10000)
    );

    return (bits & WEBSOCKET_PROTOCOL_SERVER_HELLO_EVENT) != 0;
}
```

#### 音频数据发送

```cpp
bool WebsocketProtocol::SendAudio(std::unique_ptr<AudioStreamPacket> packet) {
    if (websocket_ == nullptr || !websocket_->IsConnected()) {
        return false;
    }

    if (version_ == 2) {
        // BinaryProtocol2: 12 字节头
        std::string serialized;
        serialized.resize(sizeof(BinaryProtocol2) + packet->payload.size());
        auto bp2 = (BinaryProtocol2*)serialized.data();
        bp2->version = htons(version_);
        bp2->type = 0;  // OPUS
        bp2->reserved = 0;
        bp2->timestamp = htonl(packet->timestamp);
        bp2->payload_size = htonl(packet->payload.size());
        memcpy(bp2->payload, packet->payload.data(), packet->payload.size());
        return websocket_->Send(serialized.data(), serialized.size(), true);
    }
    else if (version_ == 3) {
        // BinaryProtocol3: 4 字节头
        std::string serialized;
        serialized.resize(sizeof(BinaryProtocol3) + packet->payload.size());
        auto bp3 = (BinaryProtocol3*)serialized.data();
        bp3->type = 0;  // OPUS
        bp3->reserved = 0;
        bp3->payload_size = htons(packet->payload.size());
        memcpy(bp3->payload, packet->payload.data(), packet->payload.size());
        return websocket_->Send(serialized.data(), serialized.size(), true);
    }
    else {
        // 原始数据
        return websocket_->Send(packet->payload.data(), packet->payload.size(), true);
    }
}
```

#### 消息接收处理

```cpp
websocket_->OnData([this](const char* data, size_t len, bool binary) {
    if (binary) {
        // 二进制音频数据
        if (on_incoming_audio_ != nullptr) {
            if (version_ == 2) {
                BinaryProtocol2* bp2 = (BinaryProtocol2*)data;
                bp2->version = ntohs(bp2->version);
                bp2->type = ntohs(bp2->type);
                bp2->timestamp = ntohl(bp2->timestamp);
                bp2->payload_size = ntohl(bp2->payload_size);
                auto payload = (uint8_t*)bp2->payload;
                on_incoming_audio_(std::make_unique<AudioStreamPacket>(AudioStreamPacket{
                    .sample_rate = server_sample_rate_,
                    .frame_duration = server_frame_duration_,
                    .timestamp = bp2->timestamp,
                    .payload = std::vector<uint8_t>(payload, payload + bp2->payload_size)
                }));
            }
            // version 3 和原始数据类似处理
        }
    } else {
        // JSON 控制消息
        auto root = cJSON_ParseWithLength(data, len);
        auto type = cJSON_GetObjectItem(root, "type");
        if (cJSON_IsString(type)) {
            if (strcmp(type->valuestring, "hello") == 0) {
                ParseServerHello(root);
            } else {
                on_incoming_json_(root);
            }
        }
        cJSON_Delete(root);
    }
    last_incoming_time_ = std::chrono::steady_clock::now();
});
```

### MQTT 协议 (`mqtt_protocol.h`)

```cpp
class MqttProtocol : public Protocol {
public:
    bool Start() override;
    bool SendAudio(std::unique_ptr<AudioStreamPacket> packet) override;
    bool OpenAudioChannel() override;
    void CloseAudioChannel(bool send_goodbye = true) override;
    bool IsAudioChannelOpened() const override;

private:
    void* mqtt_client_ = nullptr;
    std::string subscribe_topic_;
    std::string publish_topic_;

    bool SendText(const std::string& text) override;
    void OnMqttMessage(const char* topic, const uint8_t* payload, size_t len);
};
```

### 二进制协议定义 (`protocol.h`)

```cpp
// 协议版本 2: 12 字节头
struct BinaryProtocol2 {
    uint16_t version;          // 协议版本 (网络字节序)
    uint16_t type;             // 消息类型 (0=OPUS, 1=JSON)
    uint32_t reserved;         // 保留字段
    uint32_t timestamp;        // 时间戳 (毫秒，用于 AEC)
    uint32_t payload_size;     // 载荷大小 (字节)
    uint8_t payload[];         // 载荷数据
} __attribute__((packed));

// 协议版本 3: 4 字节头
struct BinaryProtocol3 {
    uint8_t type;              // 消息类型
    uint8_t reserved;          // 保留字段
    uint16_t payload_size;     // 载荷大小 (网络字节序)
    uint8_t payload[];         // 载荷数据
} __attribute__((packed));

// 音频流包
struct AudioStreamPacket {
    int sample_rate = 0;
    int frame_duration = 0;
    uint32_t timestamp = 0;
    std::vector<uint8_t> payload;
};
```

### 状态消息发送

```cpp
void Protocol::SendMotionEvent(cJSON* fields) {
    cJSON* root = cJSON_Duplicate(fields, 1);
    cJSON_DeleteItemFromObjectCaseSensitive(root, "session_id");
    cJSON_AddStringToObject(root, "session_id", session_id_.c_str());
    cJSON_DeleteItemFromObjectCaseSensitive(root, "type");
    cJSON_AddStringToObject(root, "type", "motion_event");
    char* serialized = cJSON_PrintUnformatted(root);
    cJSON_Delete(root);
    std::string message(serialized);
    cJSON_free(serialized);
    SendText(message);
}

void Protocol::SendDeviceInfo(cJSON* fields) {
    // 类似处理，type 改为 "device_info"
}

void Protocol::SendSelfCheck(cJSON* fields) {
    // 类似处理，type 改为 "self_check"
}
```

---

## 3. MCP 服务器实现

### 工具注册

```cpp
class McpServer {
public:
    static McpServer& GetInstance() {
        static McpServer instance;
        return instance;
    }

    void AddTool(const std::string& name,
                 const std::string& description,
                 const PropertyList& properties,
                 std::function<ReturnValue(const PropertyList&)> callback) {
        tools_.push_back(new McpTool(name, description, properties, callback));
    }

    void ParseMessage(const cJSON* json) {
        int id = cJSON_GetObjectItem(json, "id")->valueint;
        std::string method = cJSON_GetObjectItem(json, "method")->valuestring;

        if (method == "tools/list") {
            GetToolsList(id, "", false);
        } else if (method == "tools/call") {
            std::string tool_name = cJSON_GetObjectItem(json, "params")
                ->GetObjectItem("name")->valuestring;
            cJSON* arguments = cJSON_GetObjectItem(json, "params")
                ->GetObjectItem("arguments");
            DoToolCall(id, tool_name, arguments);
        }
    }
};
```

### 工具调用

```cpp
std::string McpTool::Call(const PropertyList& properties) {
    ReturnValue return_value = callback_(properties);

    cJSON* result = cJSON_CreateObject();
    cJSON* content = cJSON_CreateArray();

    if (std::holds_alternative<ImageContent*>(return_value)) {
        // 图片结果
        auto image_content = std::get<ImageContent*>(return_value);
        cJSON* image = cJSON_CreateObject();
        cJSON_AddStringToObject(image, "type", "image");
        cJSON_AddStringToObject(image, "image", image_content->to_json().c_str());
        cJSON_AddItemToArray(content, image);
        delete image_content;
    } else {
        // 文本结果
        cJSON* text = cJSON_CreateObject();
        cJSON_AddStringToObject(text, "type", "text");
        if (std::holds_alternative<std::string>(return_value)) {
            cJSON_AddStringToObject(text, "text", std::get<std::string>(return_value).c_str());
        }
        cJSON_AddItemToArray(content, text);
    }

    cJSON_AddItemToObject(result, "content", content);
    cJSON_AddBoolToObject(result, "isError", false);

    char* json_str = cJSON_PrintUnformatted(result);
    std::string result_str(json_str);
    cJSON_free(json_str);
    cJSON_Delete(result);
    return result_str;
}
```

### 属性系统

```cpp
class Property {
public:
    Property(const std::string& name, PropertyType type)
        : name_(name), type_(type), has_default_value_(false) {}

    Property(const std::string& name, PropertyType type, int default_value,
             int min_value, int max_value)
        : name_(name), type_(type), has_default_value_(true),
          min_value_(min_value), max_value_(max_value) {
        value_ = default_value;
    }

    std::string to_json() const {
        cJSON *json = cJSON_CreateObject();
        if (type_ == kPropertyTypeBoolean) {
            cJSON_AddStringToObject(json, "type", "boolean");
            if (has_default_value_) {
                cJSON_AddBoolToObject(json, "default", value<bool>());
            }
        } else if (type_ == kPropertyTypeInteger) {
            cJSON_AddStringToObject(json, "type", "integer");
            if (has_default_value_) {
                cJSON_AddNumberToObject(json, "default", value<int>());
            }
            if (min_value_.has_value()) {
                cJSON_AddNumberToObject(json, "minimum", min_value_.value());
            }
            if (max_value_.has_value()) {
                cJSON_AddNumberToObject(json, "maximum", max_value_.value());
            }
        }
        // ...
    }
};
```

---

## 4. 总结

### 构建系统特点

| 特性 | 实现 |
|------|------|
| 多平台支持 | PlatformIO (U1) + ESP-IDF (U8) + Maven (Server) |
| 板型适配 | 100+ 板型，Kconfig 条件编译 |
| 语言本地化 | 20+ 语言，自动生成头文件 |
| 资源管理 | 字体/音频/表情，分区烧录 |
| 芯片适配 | ESP32/ESP32-S3/ESP32-P4 条件编译 |

### 协议层特点

| 特性 | 实现 |
|------|------|
| 双传输 | WebSocket (主) + MQTT (备) |
| 双协议 | 二进制 (音频) + JSON (控制) |
| 协议版本 | v2 (12字节头) + v3 (4字节头) |
| MCP 集成 | 工具注册/调用，属性系统 |
| 状态上报 | motion_event/device_info/self_check |

---

*分析完毕。构建系统与协议层的实现细节已被完整解析。*
