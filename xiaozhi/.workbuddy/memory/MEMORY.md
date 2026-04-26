# 长期记忆

## 项目：小智AI MCP 服务器
- **项目路径**: `f:\_Project\Electron\AIMirror\aimirror2\xiaozhi\`
- **主程序**: `xiaozhi_mcp_server.py`
- **协议**: MCP (JSON-RPC 2.0) over WebSocket
- **接入点**: `wss://api.xiaozhi.me/mcp/?token=...`
- **Python**: 系统 Python 3.12 (`C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`)
- **关键依赖**: websockets

## 小智AI MCP 协议要点
- 协议版本: `2024-11-05`
- 消息格式: JSON-RPC 2.0，可能包裹在 `{"type":"mcp","payload":{...}}` 中
- **交互流程（双向initialize）**:
  1. 客户端发送 initialize
  2. 服务器也发送自己的 initialize（xz-mcp-broker 是 host 角色）
  3. 客户端响应服务器的 initialize
  4. 服务器发送 notifications/initialized
  5. 服务器发送 tools/list（请求客户端工具列表）→ 客户端响应
  6. 握手完成，服务器可发 tools/call
- 工具命名规范: `self.模块.功能`
- 工具定义包含: name, description, inputSchema (JSON Schema)
- 工具调用响应: `{"content": [{"type": "text", "text": "..."}], "isError": bool}`
- **对话消息类型**: stt（用户语音）、tts（AI语音）、llm（AI文本）、listen、text、abort、emotion、iot、notification
- **服务器名称**: xz-mcp-broker v0.0.1
