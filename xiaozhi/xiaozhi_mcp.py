#!/usr/bin/env python3
"""
小智 AI MCP 服务器
==================
通过 WebSocket 连接到小智 AI MCP 接入点，作为 MCP Server 角色。
捕获所有对话消息（tts/llm/stt 等）并打印到本地终端。

协议规范参考: https://xiaozhi.dev/docs/development/mcp/protocol/
交互流程：
  1. 建立 WebSocket 连接
  2. broker (client) 发送 initialize → 我们响应
  3. broker 发送 notifications/initialized
  4. broker 发送 tools/list → 我们响应工具列表
  5. 握手完成，broker 可发送 tools/call 调用我们的工具
  6. 同时接收对话消息（stt/tts/llm/text/emotion 等），打印到终端
"""

import asyncio
import json
import sys
import signal
import logging
from datetime import datetime
from typing import Any

import websockets

# ─── 配置 ────────────────────────────────────────────────────────────

MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOjkxMjk3MiwiYWdlbnRJZCI6MTc2NDcxMSwiZW5kcG9pbnRJZCI6ImFnZW50XzE3NjQ3MTEiLCJwdXJwb3NlIjoibWNwLWVuZHBvaW50IiwiaWF0IjoxNzc3MTI0ODkxLCJleHAiOjE4MDg2ODI0OTF9.0_PgT_kJLTi-DmvGkiBYtr4rm7deJAB-XHEgL7ke8VwDlPxJa9ym2Dc8NdccEqs5T7XUHt0uwHiNDRflS_RZgQ"

SERVER_NAME = "xiaozhi-local-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

RECONNECT_DELAY = 3       # 断线重连间隔（秒）
MAX_RECONNECT_DELAY = 60  # 最大重连间隔

# ─── 日志配置 ────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("xiaozhi-mcp")

# ─── ANSI 颜色 ───────────────────────────────────────────────────────

class C:
    """终端颜色"""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    BG_RED  = "\033[41m"


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


# ─── MCP 工具定义 ─────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "self.get_device_status",
        "description": "获取当前设备状态信息，包括连接状态、运行时间等",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "self.echo",
        "description": "回显输入的文本，用于测试 MCP 通信是否正常",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "要回显的文本内容"
                }
            },
            "required": ["message"]
        }
    },
    {
        "name": "self.get_time",
        "description": "获取当前服务器时间",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "self.print_message",
        "description": "向本地终端打印一条自定义消息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "要打印的文本内容"
                },
                "level": {
                    "type": "string",
                    "description": "日志级别: info, warn, error",
                    "enum": ["info", "warn", "error"]
                }
            },
            "required": ["text"]
        }
    },
]


# ─── 工具执行处理 ─────────────────────────────────────────────────────

async def handle_tool_call(name: str, arguments: dict) -> dict:
    """执行工具调用并返回结果"""
    log.info(f"{C.CYAN}🔧 工具调用: {name}{C.RESET} 参数: {json.dumps(arguments, ensure_ascii=False)}")

    if name == "self.get_device_status":
        result_text = json.dumps({
            "status": "online",
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "uptime": timestamp(),
            "python": sys.version.split()[0],
        }, ensure_ascii=False)

    elif name == "self.echo":
        msg = arguments.get("message", "")
        result_text = msg

    elif name == "self.get_time":
        result_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    elif name == "self.print_message":
        text = arguments.get("text", "")
        level = arguments.get("level", "info")
        prefix = {"info": "📝", "warn": "⚠️", "error": "❌"}.get(level, "📝")
        print(f"\n{C.BOLD}{prefix} [自定义消息 - {level}]{C.RESET} {text}\n")
        result_text = f"已打印: {text}"

    else:
        return {
            "content": [{"type": "text", "text": f"未知工具: {name}"}],
            "isError": True
        }

    return {
        "content": [{"type": "text", "text": result_text}],
        "isError": False
    }


# ─── 对话消息处理 ─────────────────────────────────────────────────────

def handle_conversation_message(msg: dict):
    """处理非 MCP 的对话消息（stt/tts/llm/text/emotion 等），打印到终端"""
    msg_type = msg.get("type", "unknown")

    if msg_type == "stt":
        # 语音识别结果（用户说的话）
        text = msg.get("text", msg.get("data", {}).get("text", ""))
        if text:
            print(f"\n{C.GREEN}{C.BOLD}🎤 用户语音:{C.RESET} {C.GREEN}{text}{C.RESET}")

    elif msg_type == "tts":
        # TTS 语音合成（AI 要说的话）
        text = msg.get("text", msg.get("data", {}).get("text", ""))
        state = msg.get("state", msg.get("data", {}).get("state", ""))
        if text:
            print(f"{C.MAGENTA}🔊 AI语音:{C.RESET} {C.MAGENTA}{text}{C.RESET}")
        elif state == "start":
            print(f"{C.DIM}🔊 [TTS 开始播放]{C.RESET}")
        elif state == "stop":
            print(f"{C.DIM}🔊 [TTS 播放结束]{C.RESET}")

    elif msg_type == "llm":
        # LLM 文本响应（AI 的文字回复）
        text = msg.get("text", msg.get("data", {}).get("text", ""))
        emotion = msg.get("emotion", msg.get("data", {}).get("emotion", ""))
        if text:
            emoji = {"happy": "😊", "sad": "😢", "angry": "😠", "neutral": "🤖"}.get(emotion, "🤖")
            print(f"{C.BLUE}{C.BOLD}{emoji} AI回复:{C.RESET} {C.BLUE}{text}{C.RESET}")

    elif msg_type == "text":
        # 纯文本消息
        text = msg.get("text", msg.get("data", {}).get("text", ""))
        if text:
            print(f"{C.WHITE}📄 文本:{C.RESET} {text}")

    elif msg_type == "emotion":
        # 情感识别
        emotion = msg.get("emotion", msg.get("data", {}).get("emotion", ""))
        if emotion:
            print(f"{C.YELLOW}😄 情感:{C.RESET} {emotion}")

    elif msg_type == "listen":
        # 监听状态变化
        state = msg.get("state", msg.get("data", {}).get("state", ""))
        mode = msg.get("mode", msg.get("data", {}).get("mode", ""))
        if state:
            state_desc = {"start": "开始监听", "stop": "停止监听", "detect": "检测到语音"}.get(state, state)
            print(f"{C.DIM}👂 监听: {state_desc}{C.RESET}" + (f" (模式: {mode})" if mode else ""))

    elif msg_type == "iot":
        # IoT 设备控制
        devices = msg.get("devices", msg.get("data", {}))
        print(f"{C.YELLOW}🏠 IoT:{C.RESET} {json.dumps(devices, ensure_ascii=False)}")

    elif msg_type == "notification":
        # 通知
        text = msg.get("text", msg.get("data", {}).get("text", ""))
        title = msg.get("title", "")
        if text:
            print(f"{C.YELLOW}🔔 通知:{C.RESET} {f'[{title}] ' if title else ''}{text}")

    elif msg_type == "abort":
        # 中断
        reason = msg.get("reason", "")
        print(f"{C.RED}⛔ 中断:{C.RESET} {reason if reason else '会话被中断'}")

    elif msg_type == "hello":
        # 连接握手 hello
        version = msg.get("version", "")
        transport = msg.get("transport", "")
        session_id = msg.get("session_id", "")
        print(f"\n{C.BOLD}{C.CYAN}🤝 握手:{C.RESET} version={version} transport={transport} session={session_id[:16]}...")

    else:
        # 未知类型，打印原始消息
        print(f"{C.DIM}❓ [{msg_type}]:{C.RESET} {json.dumps(msg, ensure_ascii=False, indent=2)[:200]}")


# ─── MCP JSON-RPC 处理 ────────────────────────────────────────────────

class McpServer:
    """小智 MCP 服务器核心"""

    def __init__(self):
        self.ws = None
        self.request_id = 0
        self.session_id = ""
        self.initialized = False
        self._reconnect_delay = RECONNECT_DELAY

    def next_id(self) -> int:
        self.request_id += 1
        return self.request_id

    async def send_json(self, data: dict):
        """发送 JSON 消息"""
        if self.ws is None:
            return
        raw = json.dumps(data, ensure_ascii=False)
        log.debug(f"→ {raw[:200]}")
        await self.ws.send(raw)

    async def send_mcp(self, payload: dict):
        """发送 MCP 消息（包裹在 type=mcp 外层）"""
        msg = {
            "type": "mcp",
            "session_id": self.session_id,
            "payload": payload
        }
        await self.send_json(msg)

    async def send_mcp_response(self, req_id, result: dict):
        """发送 MCP 成功响应"""
        await self.send_mcp({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": result
        })

    async def send_mcp_error(self, req_id, code: int, message: str):
        """发送 MCP 错误响应"""
        await self.send_mcp({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message}
        })

    async def send_notification(self, method: str, params: dict = None):
        """发送 MCP 通知（无 id）"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            payload["params"] = params
        await self.send_mcp(payload)

    # ─── MCP 请求处理 ─────────────────────────────────────────────

    async def handle_mcp_request(self, payload: dict):
        """处理收到的 MCP JSON-RPC 请求"""
        method = payload.get("method", "")
        req_id = payload.get("id")
        params = payload.get("params", {})

        log.info(f"{C.CYAN}← MCP 请求: {method} (id={req_id}){C.RESET}")

        if method == "initialize":
            # 阶段 2: broker 发送 initialize，我们响应
            broker_caps = params.get("capabilities", {})
            log.info(f"  broker 能力: {json.dumps(broker_caps, ensure_ascii=False)[:100]}")

            await self.send_mcp_response(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            })
            print(f"{C.BOLD}{C.GREEN}✅ MCP 初始化完成{C.RESET} (protocol={PROTOCOL_VERSION})")

        elif method == "notifications/initialized":
            # broker 确认初始化完成（通知，无需回复）
            self.initialized = True
            print(f"{C.BOLD}{C.GREEN}✅ 收到 initialized 通知，握手完成{C.RESET}")

        elif method == "tools/list":
            # 阶段 3: broker 请求工具列表
            cursor = params.get("cursor", "")
            with_user_tools = params.get("withUserTools", False)
            log.info(f"  cursor={cursor!r} withUserTools={with_user_tools}")

            tools_to_return = list(TOOLS)
            await self.send_mcp_response(req_id, {
                "tools": tools_to_return,
                "nextCursor": ""  # 无分页
            })
            print(f"{C.CYAN}📋 已返回 {len(tools_to_return)} 个工具{C.RESET}")

        elif method == "tools/call":
            # 阶段 4: broker 调用工具
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            result = await handle_tool_call(tool_name, arguments)
            await self.send_mcp_response(req_id, result)

        else:
            log.warning(f"未知 MCP 方法: {method}")
            if req_id is not None:
                await self.send_mcp_error(req_id, -32601, f"Method not found: {method}")

    async def handle_mcp_response(self, payload: dict):
        """处理收到的 MCP JSON-RPC 响应（我们发出请求后的回复）"""
        req_id = payload.get("id")
        result = payload.get("result")
        error = payload.get("error")
        if error:
            log.warning(f"收到 MCP 错误响应 (id={req_id}): {error}")
        else:
            log.debug(f"收到 MCP 成功响应 (id={req_id}): {json.dumps(result, ensure_ascii=False)[:100]}")

    # ─── 消息分发 ─────────────────────────────────────────────────

    async def handle_message(self, raw: str):
        """处理收到的 WebSocket 消息"""
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            log.warning(f"无法解析 JSON: {raw[:100]}")
            return

        msg_type = msg.get("type", "")

        # 保存 session_id
        sid = msg.get("session_id", "")
        if sid:
            self.session_id = sid

        if msg_type == "mcp":
            # MCP 协议消息
            payload = msg.get("payload", {})
            method = payload.get("method", "")

            if "method" in payload and "id" not in payload and "result" not in payload:
                # 通知消息（无 id，无 result）
                await self.handle_mcp_request(payload)
            elif "method" in payload and "id" in payload:
                # 请求消息（有 method + id）
                await self.handle_mcp_request(payload)
            elif "result" in payload or "error" in payload:
                # 响应消息
                await self.handle_mcp_response(payload)
            else:
                log.debug(f"未识别的 MCP 消息: {json.dumps(payload, ensure_ascii=False)[:200]}")

        else:
            # 对话消息（stt/tts/llm/text/emotion/listen/iot/notification 等）
            handle_conversation_message(msg)

    # ─── 主连接循环 ───────────────────────────────────────────────

    async def run(self):
        """主运行循环，支持断线重连"""
        print(f"\n{C.BOLD}{C.CYAN}{'='*60}")
        print(f"  小智 AI MCP 服务器")
        print(f"  服务器: {SERVER_NAME} v{SERVER_VERSION}")
        print(f"  协议版本: {PROTOCOL_VERSION}")
        print(f"  接入点: {MCP_ENDPOINT[:50]}...")
        print(f"{'='*60}{C.RESET}\n")

        while True:
            try:
                log.info(f"正在连接到小智 MCP 接入点...")
                async with websockets.connect(
                    MCP_ENDPOINT,
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=5,
                    max_size=2**22,  # 4MB
                ) as ws:
                    self.ws = ws
                    self.initialized = False
                    self._reconnect_delay = RECONNECT_DELAY  # 重置重连间隔

                    print(f"{C.BOLD}{C.GREEN}🌐 WebSocket 连接已建立{C.RESET}\n")
                    print(f"{C.DIM}等待 MCP 握手...{C.RESET}")
                    print(f"{C.DIM}{'─'*50}{C.RESET}")

                    async for raw_msg in ws:
                        await self.handle_message(raw_msg)

            except websockets.ConnectionClosed as e:
                self.ws = None
                print(f"\n{C.RED}⚡ 连接关闭: code={e.code} reason={e.reason}{C.RESET}")
            except websockets.InvalidStatusCode as e:
                self.ws = None
                print(f"\n{C.RED}❌ 连接被拒绝: {e.status_code}{C.RESET}")
                if e.status_code in (401, 403):
                    print(f"{C.RED}   Token 可能已过期，请更新 MCP_ENDPOINT 中的 token{C.RESET}")
                    break  # 认证失败不重连
            except Exception as e:
                self.ws = None
                print(f"\n{C.RED}❌ 连接异常: {type(e).__name__}: {e}{C.RESET}")

            # 断线重连
            print(f"{C.YELLOW}⏳ {self._reconnect_delay} 秒后重连...{C.RESET}")
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, MAX_RECONNECT_DELAY)


# ─── 入口 ─────────────────────────────────────────────────────────────

async def main():
    server = McpServer()

    # 优雅退出
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        print(f"\n{C.YELLOW}正在关闭...{C.RESET}")
        stop_event.set()

    # Windows 下使用 signal.SIGINT (Ctrl+C)
    if sys.platform == "win32":
        signal.signal(signal.SIGINT, lambda *_: signal_handler())
    else:
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

    # 运行主循环
    task = asyncio.create_task(server.run())
    await stop_event.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    print(f"{C.GREEN}已退出{C.RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{C.YELLOW}已退出{C.RESET}")
