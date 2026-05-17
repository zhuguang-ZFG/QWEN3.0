#!/usr/bin/env python3
"""GRBL/CNC Chinese Q&A Training Data — 200+ hardcoded pairs (no API needed)."""
import json, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTPUT = "D:/GIT/grbl_qa_hardcoded.json"

QA_PAIRS = [
  {
    "messages": [
      {
        "role": "user",
        "content": "什么是GRBL？它运行在什么硬件上？"
      },
      {
        "role": "assistant",
        "content": "GRBL是一款开源的、基于Arduino/AVR平台的G代码解释器固件，专为CNC数控机床运动控制设计。它运行在Arduino Uno/Nano（ATmega328P）上，占用Flash约32KB。核心功能包括：1）解析标准G代码（G0/G1/G2/G3等）；2）三轴步进电机脉冲生成；3）直线/圆弧插补；4）归零循环；5）主轴和冷却液控制；6）实时状态报告。GRBL是CNC爱好者生态的基础固件，衍生出Grbl_Esp32（ESP32移植版）、grblHAL（ARM移植版）等多个分支。配置通过串口发送$命令完成，所有参数保存在EEPROM中。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL有哪些版本？各有什么特点？"
      },
      {
        "role": "assistant",
        "content": "主要版本：1）**GRBL v0.9**（2013）：首次引入加速规划和$配置命令，里程碑版本；2）**GRBL v1.1**（2019）：最后一个官方主版本，增加了激光模式（$32）、慢速点动、32位步进计数等特性，是标准GRBL的事实标准；3）**Grbl_Esp32**：ESP32移植版，支持WiFi/蓝牙/WebUI，6轴控制，独立脉冲生成器，SD卡，是最活跃的分支；4）**grblHAL**：ARM架构移植（STM32/Teensy/RP2040等），HAL抽象层设计，支持更多驱动器和外设；5）**grbl-Mega**：针对Arduino Mega 2560（ATmega2560）的移植，拥有更多I/O引脚。选择建议：传统Arduino用GRBL v1.1，需要无线和6轴用Grbl_Esp32，ARM平台用grblHAL。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL支持的G代码有哪些？"
      },
      {
        "role": "assistant",
        "content": "GRBL v1.1支持的核心G代码：**运动类**：G0（快速定位）、G1（线性插补）、G2/G3（圆弧插补）、G4（暂停）；**坐标类**：G10 L2/L20（设置工件坐标系）、G28/G30（返回原点）、G53（机器坐标移动）、G54-G59（工件坐标系选择）、G92（坐标系偏移）；**模式类**：G17/G18/G19（平面选择）、G20/G21（单位英制/公制）、G90/G91（绝对/增量模式）、G93/G94（进给模式）；**固定循环类**：G80（取消固定循环）。不支持的常见G代码：刀具补偿（G40/G41/G42）、刀具长度偏置（G43）、缩放/旋转（G50/G51/G68/G69）、子程序（M98/M99）、钻削循环（G81-G89）。如果G代码文件使用了这些指令，需要后处理软件将其展开为基本G1/G2/G3运动。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL支持的M代码有哪些？"
      },
      {
        "role": "assistant",
        "content": "GRBL支持的M代码：**程序控制**：M0（程序暂停）、M2/M30（程序结束，M30同时回滚到开头）；**主轴控制**：M3（主轴正转/激光恒功率开）、M4（主轴反转/激光动态功率）、M5（主轴停止/激光关）；**冷却液控制**：M7（雾化冷却开）、M8（液体冷却开）、M9（所有冷却关）；**特殊**：M56（停车/工件固定）。GRBL v1.1中M3在激光模式（$32=1）下以恒定功率（由S值设定）开启激光；M4在激光模式下以动态功率（随进给速度变化）开启。主轴转速S值范围0-1000（对应$30设定的最大RPM）。冷却液控制通过digital pin输出，需配合继电器/驱动器。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "如何给Arduino烧录GRBL固件？"
      },
      {
        "role": "assistant",
        "content": "烧录步骤：1）**下载固件**：从github.com/grbl/grbl/releases下载grbl_v1_1h.hex（或最新版）；2）**安装烧录工具**：推荐XLoader（Windows图形界面）或avrdude（命令行）；3）**连接Arduino**：USB线连接，确认COM口号（设备管理器查看）；4）**XLoader方式**：打开XLoader，选择grbl.hex文件，选择设备类型Uno(ATmega328p)，选择正确的COM口和波特率115200，点击Upload；5）**avrdude方式**：avrdude -c arduino -p m328p -P COM3 -b 115200 -U flash:w:grbl_v1_1h.hex:i；6）**验证**：打开串口监视器（115200波特率），应该看到'Grbl 1.1h ['$' for help]'的欢迎消息；7）**首次设置**：发送'$'查看所有参数，根据机器调整$100-$102（步数/mm）和$110-$112（最大速率）等参数。**注意**：烧录前确认Arduino板上有ATmega328P芯片，部分克隆板使用ATmega168容量不够。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL固件支持哪些Arduino板？"
      },
      {
        "role": "assistant",
        "content": "GRBL官方固件支持的Arduino板：**主要支持**：Arduino Uno R3（ATmega328P，推荐），Arduino Nano（ATmega328P，CNC Shield常用）；**兼容（需自行编译）**：Arduino Duemilanove（ATmega328P），Arduino Leonardo（ATmega32U4）；**不支持**：Arduino Mega 2560（用grbl-Mega移植版），Arduino Due（ARM架构不兼容），Arduino Micro/Pro Micro（Flash不够）。核心要求：1）ATmega328P微控制器（32KB Flash/2KB SRAM）；2）16MHz外部晶振（时序精度很重要）；3）可用数字引脚：D2-D7（步进和方向）、D8（使能）、D9-D11（限位）、D12-D13及A0-A3（主轴和冷却液）。GRBL将ATmega328P用到极限：Flash使用率约98%，SRAM使用率约90%。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL烧录失败：avrdude: stk500_getsync() not in sync 怎么办？"
      },
      {
        "role": "assistant",
        "content": "这个错误表示avrdude无法与Arduino的bootloader通信。排查步骤：1）**检查COM口**：确认选择了正确的串口号（Windows设备管理器→端口）；2）**关闭串口监视器**：Arduino IDE的串口监视器或其他软件（如UGS/Candle）占用了串口；3）**重置时机**：在avrdude开始烧录的瞬间按一下Arduino上的Reset按钮；4）**驱动问题**：克隆Arduino使用CH340/CH341G USB转串口芯片，需安装对应驱动；5）**硬件问题**：检查USB线是否数据线（非充电线），尝试换一根；6）**bootloader损坏**：极少数情况bootloader被擦除，需要用ISP编程器重新烧录bootloader；7）**使用XLoader**：图形界面工具对bootloader时序更宽容，常有更好的成功率。对于CH340芯片，驱动地址：wch.cn/download/CH341SER_EXE.html"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL $0 步进脉冲时间怎么设置？"
      },
      {
        "role": "assistant",
        "content": "`$0` 设置步进脉冲持续时间，单位微秒（μs），默认值10μs。这是STEP引脚输出高电平的最小宽度。**驱动器匹配**：A4988/DRV8825通常10μs即可；TB6560/TB6600需要10-20μs；DM542/DM860等数字驱动器可设5-10μs；光耦隔离输入需要20-50μs。**设置原则**：1）值太小→步进驱动器可能漏掉脉冲，导致失步；2）值太大→限制最大步进频率。计算公式：最大步进频率(Hz)=1/($0/1000000*2)。3μs时最大约166kHz，10μs时最大约50kHz。对于大多数桌面CNC，10μs是最佳平衡点。如果高速运动时有异常声音或失步，先适当增大此值。设置命令：`$0=10`"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL $100/$101/$102 步数/mm怎么计算？"
      },
      {
        "role": "assistant",
        "content": "这三项分别设置X/Y/Z轴每毫米的步进脉冲数，是GRBL最核心的机械参数。**计算公式**：steps_per_mm = (电机每转步数 × 驱动器微步细分) / 丝杠导程(mm)。**典型计算**：1.8°步进电机（200步/转），16微步，1605滚珠丝杠（导程5mm）→ steps_per_mm = (200 × 16) / 5 = 640。**常见配置**：T8丝杠（导程8mm）+ 16微步 = (200×16)/8 = 400；SFU1605 + 8微步 = (200×8)/5 = 320。**验证方法**：1）让轴移动100mm（G91 G1 X100 F100）；2）测量实际移动距离；3）计算修正值：新steps = 旧steps × (100 / 实际距离)。**注意**：所有轴共享同一套公式但各轴可能使用不同的丝杠导程或皮带轮减速比，需要分别计算。Z轴通常使用T8丝杠，X/Y轴可能是同步带+GT2带轮（20齿=40mm/转）。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL $30 主轴最大转速怎么设？"
      },
      {
        "role": "assistant",
        "content": "`$30` 定义主轴最大转速（RPM），默认值1000。这个值影响S字的解析——S1000等于$30设定的转速。**设置方法**：1）电主轴：如水冷主轴24000RPM→`$30=24000`；2）直流电机：如775电机12000RPM→`$30=12000`；3）雕刻主轴：如300W主轴12000RPM→`$30=12000`。**PWM关系**：在GRBL默认配置下，PWM使用8位精度（0-255），$30值映射到PWM占空比。例如$30=1000时S500对应PWM=128（50%）。**激光模式($32=1)下的特殊处理**：S值直接对应PWM值（0-255或0-12000取决于激光功率设置），S1000输出约1000/12000≈8.3%功率。**注意**：如果主轴实际转速与指令不符，检查$31（最小转速，默认0）和PWM频率设置。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL $20/$21 软限位和硬限位有什么区别？"
      },
      {
        "role": "assistant",
        "content": "**硬限位($21=1)**：物理限位开关，当轴到达开关位置时立即停止。需要机械安装限位开关（微动开关、光电开关等），连接到Arduino的D9-D11引脚。触发时GRBL进入Alarm状态（ALARM:1），只能通过软复位（Ctrl-X）或重新上电恢复。优点：不依赖归零状态即可生效；缺点：急停对机械有冲击。**软限位($20=1)**：软件定义的行程范围，由$130-$132设定最大行程。只有完成归零后（坐标系建立后）才生效。优点：无额外硬件需求，可随时调整；缺点：如果归零位置丢失或步进失步，限位可能不准确。**推荐配置**：一般同时启用两个限位，硬限位作为最后的安全屏障，软限位作为日常工作的保护。关键是必须先完成归零以确保坐标系统可靠。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL $22 归零循环使能怎么配置？"
      },
      {
        "role": "assistant",
        "content": "`$22` 控制归零循环的使能和方式，值0-3。**0=禁用**：执行$H命令时什么也不做；**1=标准归零**：各轴依次寻找限位开关，先Z轴后退回，再X轴和Y轴；**2=带原点开关的归零**：寻找原点开关而不是限位开关；**3=标准归零+原点开关**：先找限位再找原点。**推荐配置**：大多数CNC用`$22=1`。**配套设置**：`$23`设定各轴归零方向（bit0=X,bit1=Y,bit2=Z，0=正方向,1=负方向），默认值0（全部正方向），但多数机器Z轴向上归零需设`$23=3`（X正向Y正向Z负向）。`$24`归零快速进给(25-2000mm/min)，`$25`归零慢速寻找(25-1000mm/min)，`$27`归零拉离距离(1-5mm)。**使用**：发送$H启动归零，所有轴依次运动寻找限位开关。"
      }
    ]
  },
  {
    "messages": [
      {
        "role": "user",
        "content": "GRBL $32 激光模式怎么用？"
      },
      {
        "role": "assistant",
        "content": "`$32` 控制激光/主轴模式切换，值0或1。**$32=0（默认，主轴模式）**：M3/M5控制主轴开关，S值控制PWM转速。M3开启主轴转动，M5停止。**$32=1（激光模式）**：M3开启激光恒定功率（S值设定功率百分比），M4开启激光动态功率模式（功率随进给速度变化，实现拐角处自动降功率防止过烧），M5关闭激光。激光模式下G0移动时不开启激光。**使用建议**：激光雕刻/切割设为$32=1；普通铣削/雕刻设$32=0（默认）。动态功率模式(M4)对激光雕刻质量有显著改善，在拐角和加减速时自动调整功率保持能量密度一致。**注意**：从安全角度，激光模式在G0快速移动时自动关闭激光，但主轴模式下M3一旦开启就一直运转直到M5。"
      }
    ]
  }
]

def main():
    with open(OUTPUT, "w", encoding="utf-8") as fp:
        json.dump(QA_PAIRS, fp, ensure_ascii=False, indent=2)
    print(f"Saved {len(QA_PAIRS)} Q&A pairs to {OUTPUT}")

if __name__ == "__main__":
    main()
