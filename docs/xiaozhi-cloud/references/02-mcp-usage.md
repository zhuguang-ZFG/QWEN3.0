# MCP 协议物联网控制用法说明

> 来源：https://xiaozhi.dev/docs/development/mcp/usage/
> 抓取日期：2026-07-05

## 简介

MCP（Model Context Protocol）是新一代推荐用于物联网控制的协议，通过标准 JSON-RPC 2.0 格式在后台与设备间发现和调用"工具"（Tool），实现灵活的设备控制。

## 典型使用流程

1. 设备启动后通过基础协议（如 WebSocket/MQTT）与后台建立连接。
2. 后台通过 MCP 协议的 `initialize` 方法初始化会话。
3. 后台通过 `tools/list` 获取设备支持的所有工具（功能）及参数说明。
4. 后台通过 `tools/call` 调用具体工具，实现对设备的控制。

## 设备端工具注册方法

设备通过 `McpServer::AddTool` 方法注册可被后台调用的"工具"：

```cpp
void AddTool(
    const std::string& name,           // 工具名称，建议唯一且有层次感，如 self.dog.forward
    const std::string& description,    // 工具描述，简明说明功能，便于大模型理解
    const PropertyList& properties,    // 输入参数列表（可为空），支持类型：布尔、整数、字符串
    std::function<ReturnValue(const PropertyList)> callback // 工具被调用时的回调实现
);
```

### 参数说明

- **name**：工具唯一标识，建议用"模块.功能"命名风格。
- **description**：自然语言描述，便于 AI/用户理解。
- **properties**：参数列表，支持类型有布尔、整数、字符串，可指定范围和默认值。
- **callback**：收到调用请求时的实际执行逻辑，返回值可为 bool/int/string。

## 典型注册示例

```cpp
void InitializeTools() {
    auto& mcp_server = McpServer::GetInstance();

    // 例1：无参数，控制机器人前进
    mcp_server.AddTool("self.dog.forward", "机器人向前移动", PropertyList(),
        [this](const PropertyList&) -> ReturnValue {
            servo_dog_ctrl_send(DOG_STATE_FORWARD, NULL);
            return true;
        });

    // 例2：带参数，设置灯光 RGB 颜色
    mcp_server.AddTool("self.light.set_rgb", "设置RGB颜色", PropertyList({
        Property("r", kPropertyTypeInteger, 0, 255),
        Property("g", kPropertyTypeInteger, 0, 255),
        Property("b", kPropertyTypeInteger, 0, 255)
    }), [this](const PropertyList& properties) -> ReturnValue {
        int r = properties["r"].value<int>();
        int g = properties["g"].value<int>();
        int b = properties["b"].value<int>();
        led_on_ = true;
        SetLedColor(r, g, b);
        return true;
    });
}
```

## 常见工具调用 JSON-RPC 示例

### 1. 获取工具列表

```json
{
  "jsonrpc": "2.0",
  "method": "tools/list",
  "params": { "cursor": "" },
  "id": 1
}
```

### 2. 控制底盘前进

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "self.chassis.go_forward",
    "arguments": {}
  },
  "id": 2
}
```

### 3. 切换灯光模式

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "self.chassis.switch_light_mode",
    "arguments": { "light_mode": 3 }
  },
  "id": 3
}
```

## 工具注册最佳实践

### 命名规范

- 使用有层次的命名：`self.模块.功能`
- 保持名称简洁且具有描述性
- 避免使用特殊字符和空格

```cpp
// 好的命名示例
"self.light.set_brightness"
"self.motor.rotate_left"
"self.sensor.get_temperature"
"self.display.show_text"
```

### 参数设计

- 使用清晰的参数名称
- 设置合理的参数范围和默认值
- 提供详细的参数描述

```cpp
PropertyList({
    Property("volume", kPropertyTypeInteger, 0, 100, "音量大小，范围0-100"),
    Property("enabled", kPropertyTypeBool, true, "是否启用功能"),
    Property("message", kPropertyTypeString, "", "要显示的文本内容")
})
```

### 错误处理

```cpp
mcp_server.AddTool("self.servo.set_angle", "设置舵机角度", PropertyList({
    Property("angle", kPropertyTypeInteger, 0, 180)
}), [this](const PropertyList& properties) -> ReturnValue {
    try {
        int angle = properties["angle"].value<int>();
        if (angle < 0 || angle > 180) {
            return "角度超出范围：0-180";
        }
        SetServoAngle(angle);
        return true;
    } catch (const std::exception& e) {
        return std::string("设置角度失败：") + e.what();
    }
});
```

## 注意事项

- 工具名称、参数及返回值请以设备端 `AddTool` 注册为准。
- 推荐所有新项目统一采用 MCP 协议进行物联网控制。
- 详细协议与进阶用法请查阅 MCP 协议文档。

## 常见问题

### Q: 如何处理工具调用超时？

A: 在工具回调中避免长时间阻塞操作，对于耗时操作可以异步处理并立即返回状态。

### Q: 可以动态添加或删除工具吗？

A: 当前实现通常在设备启动时注册工具，动态管理需要重新设计工具注册机制。

### Q: 如何处理工具调用权限？

A: 可以在工具回调中添加权限检查逻辑，或在后台API层面进行权限控制。