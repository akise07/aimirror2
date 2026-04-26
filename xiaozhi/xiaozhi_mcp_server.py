"""
小智AI MCP 服务器 - Python 客户端
==================================
通过 WebSocket 连接小智AI MCP 接入点，注册工具，
当用户对小智说"你好"时，在本地控制台打印 "hello world"。
同时打印小智AI每次回答的文本内容。

协议：MCP (Model Context Protocol) over WebSocket
消息格式：JSON-RPC 2.0（可能包裹在 {"type":"mcp","payload":...} 中）
         同时可能收到对话消息（STT/TTS/LLM 等）

使用方法：
  1. pip install websockets
  2. python xiaozhi_mcp_server.py
"""

import asyncio
import json
import signal
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("❌ 缺少依赖：websockets")
    print("请执行: pip install websockets")
    sys.exit(1)


# ─── 配置 ───────────────────────────────────────────────────────────────
MCP_ENDPOINT = (
    "wss://api.xiaozhi.me/mcp/?token="
    "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJ1c2VySWQiOjkxMjk3MiwiYWdlbnRJZCI6MTc2NDcxMSwiZW5kcG9pbnRJZCI6ImFnZW50XzE3NjQ3MTEi"
    "LCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzc3MTI0ODkxLCJleHAiOjE4MDg2ODI0OTF9."
    "0_PgT_kJLTi-DmvGkiBYtr4rm7deJAB-XHEgL7ke8VwDlPxJa9ym2Dc8NdccEqs5T7XUHt0uwHiNDRflS_RZgQ"
)

RECONNECT_DELAY = 3  # 重连延迟（秒）
MAX_RECONNECT_DELAY = 60  # 最大重连延迟


# ─── 工具定义 ────────────────────────────────────────────────────────────
# 注册到小智AI的工具列表
# 命名规范：self.模块.功能
TOOLS = [
    {
        "name": "self.greet.hello",
        "description": "当用户打招呼、说你好或问候时调用此工具，在本地控制台打印 hello world",
        "inputSchema": {
            "type": "object",
            "properties": {
                "greeting": {
                    "type": "string",
                    "description": "用户的问候语"
                }
            },
            "required": []
        }
    },
    {
        "name": "self.system.get_time",
        "description": "获取本地系统当前时间",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
]


# ─── 工具执行逻辑 ────────────────────────────────────────────────────────
def execute_tool(name: str, arguments: dict) -> dict:
    """执行工具调用并返回结果"""
    if name == "self.greet.hello":
        greeting = arguments.get("greeting", "")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + "=" * 50)
        print(f"  🔔 小智AI 工具调用触发  [{timestamp}]")
        print(f"  👋 用户问候: {greeting}")
        print("  📢 hello world")
        print("=" * 50 + "\n")
        return {
            "content": [
                {"type": "text", "text": "已在本地控制台打印 hello world ✅"}
            ],
            "isError": False
        }

    elif name == "self.system.get_time":
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"  🕐 返回系统时间: {now}")
        return {
            "content": [
                {"type": "text", "text": f"当前系统时间: {now}"}
            ],
            "isError": False
        }

    else:
        return {
            "content": [
                {"type": "text", "text": f"未知工具: {name}"}
            ],
            "isError": True
        }


# ─── MCP 协议处理 ────────────────────────────────────────────────────────
def log(direction: str, msg: str):
    """带方向标识的日志输出"""
    arrow = "⬅️ 收到" if direction == "in" else "➡️ 发送"
    print(f"  {arrow} {msg}")


def extract_payload(data: dict) -> dict:
    """
    从消息中提取 JSON-RPC payload
    兼容两种格式：
      1. 直接 JSON-RPC: {"jsonrpc":"2.0","method":"initialize",...}
      2. MCP 包裹格式: {"type":"mcp","payload":{"jsonrpc":"2.0",...}}
    """
    if "payload" in data and isinstance(data.get("payload"), dict):
        return data["payload"]
    if "jsonrpc" in data:
        return data
    return data


def handle_conversation_message(data: dict):
    """
    处理对话类消息（非 MCP JSON-RPC），打印用户和AI的文本内容。
    可能的消息类型：
      - stt: 语音识别结果（用户说的话）
      - tts: 语音合成状态（AI 的回答文本）
      - llm: 大模型情感/状态
      - text: 文本消息
      - listen: 监听状态变化
      - abort: 中止消息
    """
    msg_type = data.get("type", "")
    session_id = data.get("session_id", "")

    # ── STT 语音识别 → 用户说的话 ──
    if msg_type == "stt":
        text = data.get("text", "")
        if text:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n  🗣️  用户说: {text}  [{timestamp}]")

    # ── TTS 语音合成 → AI 的回答 ──
    elif msg_type == "tts":
        state = data.get("state", "")
        text = data.get("text", "")
        if state == "sentence_start" and text:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"  🤖 AI回答: {text}  [{timestamp}]")
        elif state == "start":
            print(f"  🔊 AI开始说话...")
        elif state == "stop":
            print(f"  🔇 AI说完  ")

    # ── LLM 情感状态 ──
    elif msg_type == "llm":
        emotion = data.get("emotion", "")
        if emotion:
            print(f"  😊 AI情感: {emotion}")

    # ── 监听状态 ──
    elif msg_type == "listen":
        state = data.get("state", "")
        mode = data.get("mode", "")
        if state == "start":
            print(f"  🎤 开始监听 (模式: {mode or 'auto'})")
        elif state == "stop":
            print(f"  🎤 停止监听")
        elif state == "detect":
            wake_word = data.get("text", "")
            print(f"  👂 唤醒词检测: {wake_word}")

    # ── 文本消息 ──
    elif msg_type == "text":
        role = data.get("role", "")
        text = data.get("text", "")
        if text:
            prefix = "👤" if role == "user" else "🤖"
            print(f"  {prefix} {role}: {text}")

    # ── 中止 ──
    elif msg_type == "abort":
        reason = data.get("reason", "")
        print(f"  ⏹️ 中止 (原因: {reason})")

    # ── 其他未知类型但有文本 ──
    elif msg_type not in ("mcp", "hello"):
        # 尝试提取任何文本内容
        text = data.get("text", "")
        if text:
            print(f"  📨 [{msg_type}] {text}")


def wrap_response(payload: dict, original_msg: dict) -> str:
    """
    根据收到的消息格式决定响应的包装方式
    如果原消息是 MCP 包裹格式，响应也用包裹格式
    """
    if "type" in original_msg and original_msg.get("type") == "mcp":
        session_id = original_msg.get("session_id", "")
        wrapped = {
            "session_id": session_id,
            "type": "mcp",
            "payload": payload
        }
        return json.dumps(wrapped, ensure_ascii=False)
    else:
        return json.dumps(payload, ensure_ascii=False)


def handle_jsonrpc(payload: dict, original_msg: dict) -> str | None:
    """处理单个 JSON-RPC 请求，返回响应字符串（无需响应时返回 None）"""

    method = payload.get("method", "")
    msg_id = payload.get("id")
    params = payload.get("params", {})

    # ── initialize ──
    if method == "initialize":
        log("in", f"initialize (id={msg_id})")
        capabilities = params.get("capabilities", {})
        if capabilities:
            log("in", f"  平台能力: {json.dumps(capabilities, ensure_ascii=False)}")

        response_payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "hello-world-mcp-server",
                    "version": "1.0.0"
                }
            }
        }
        log("out", f"initialize 响应 → 协议版本 2024-11-05, 工具数 {len(TOOLS)}")
        return wrap_response(response_payload, original_msg)

    # ── notifications/initialized ──
    if method == "notifications/initialized":
        log("in", "notifications/initialized ✓ 会话已就绪")
        return None  # 通知不需要响应

    # ── tools/list ──
    if method == "tools/list":
        cursor = params.get("cursor", "")
        log("in", f"tools/list (cursor='{cursor}', id={msg_id})")

        response_payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS
            }
        }
        tool_names = [t["name"] for t in TOOLS]
        log("out", f"tools/list 响应 → {tool_names}")
        return wrap_response(response_payload, original_msg)

    # ── tools/call ──
    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        log("in", f"tools/call → {tool_name}({arguments})")

        result = execute_tool(tool_name, arguments)

        response_payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result
        }
        status = "❌ 错误" if result.get("isError") else "✅ 成功"
        log("out", f"tools/call 响应 → {status}")
        return wrap_response(response_payload, original_msg)

    # ── 未知方法 ──
    if msg_id is not None:
        log("in", f"未知方法: {method}")
        response_payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}"
            }
        }
        return wrap_response(response_payload, original_msg)

    return None


# ─── WebSocket 主循环 ────────────────────────────────────────────────────
async def run_mcp_server():
    """连接小智AI MCP 接入点并处理消息"""
    retry_count = 0

    while True:
        try:
            print(f"\n🔌 正在连接小智AI MCP 接入点...")
            print(f"   地址: {MCP_ENDPOINT[:60]}...")

            async with websockets.connect(
                MCP_ENDPOINT,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            ) as ws:
                retry_count = 0  # 重置重试计数
                print("✅ 已连接！等待小智AI平台消息...\n")
                print("━" * 60)
                print("  💡 对小智AI说话，对话内容将在此打印")
                print("  💡 说「你好」→ 触发 hello world 工具")
                print("━" * 60 + "\n")

                async for raw_message in ws:
                    try:
                        data = json.loads(raw_message)

                        # 提取消息类型
                        msg_type = data.get("type", "")

                        # ── 处理对话类消息（STT/TTS/LLM 等）──
                        if msg_type and msg_type != "mcp" and "jsonrpc" not in data:
                            handle_conversation_message(data)
                            continue

                        # ── 处理 MCP JSON-RPC 消息 ──
                        # 调试：打印收到的原始消息
                        log("in", f"原始消息: {json.dumps(data, ensure_ascii=False)[:300]}")

                        # 提取 JSON-RPC payload
                        payload = extract_payload(data)

                        # 如果包裹格式内含对话信息，也处理
                        if msg_type == "mcp":
                            payload_type = payload.get("type", "")
                            if payload_type and payload_type not in ("", "mcp") and "jsonrpc" not in payload:
                                handle_conversation_message(payload)
                                # 仍继续处理可能的 JSON-RPC

                        # 处理 JSON-RPC 请求
                        response = handle_jsonrpc(payload, data)

                        # 发送响应
                        if response is not None:
                            await ws.send(response)

                    except json.JSONDecodeError as e:
                        print(f"  ⚠️ JSON 解析失败: {e}")
                    except Exception as e:
                        print(f"  ⚠️ 消息处理异常: {e}")

        except websockets.ConnectionClosedError as e:
            print(f"\n🔌 连接关闭 (code={e.code}, reason={e.reason})")
        except websockets.InvalidStatusCode as e:
            print(f"\n❌ 连接被拒绝 (HTTP {e.status_code})")
            if e.status_code == 401 or e.status_code == 403:
                print("   → Token 可能已过期，请检查 MCP 接入点地址中的 token")
                break
        except Exception as e:
            print(f"\n❌ 连接异常: {e}")

        # 重连逻辑
        retry_count += 1
        delay = min(RECONNECT_DELAY * retry_count, MAX_RECONNECT_DELAY)
        print(f"⏳ {delay}秒后重连... (第 {retry_count} 次重试)")
        await asyncio.sleep(delay)


# ─── 入口 ────────────────────────────────────────────────────────────────
async def main():
    print("╔══════════════════════════════════════════════════╗")
    print("║     小智AI MCP 服务器 - hello world 版          ║")
    print("║     协议: MCP (JSON-RPC 2.0) over WebSocket     ║")
    print("╚══════════════════════════════════════════════════╝\n")

    # 优雅退出
    loop = asyncio.get_event_loop()
    stop = asyncio.Future()

    def _signal_handler():
        print("\n\n🛑 收到退出信号，正在关闭...")
        stop.set_result(True)

    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)
    else:
        # Windows: 用 Ctrl+C 直接退出
        pass

    task = asyncio.create_task(run_mcp_server())

    try:
        await stop
    except KeyboardInterrupt:
        print("\n\n🛑 正在关闭...")
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        print("👋 已退出")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 已退出")
