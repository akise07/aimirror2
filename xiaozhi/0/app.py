# server.py
from mcp.server.fastmcp import FastMCP
import sys
import logging

logger = logging.getLogger('App')

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stderr.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')

import math
import random

# Create an MCP server
mcp = FastMCP("App")

# Add an addition tool
@mcp.tool()
def calculator(python_expression: str) -> dict:
    """For mathamatical calculation, always use this tool to calculate the result of a python expression."""
    result = eval(python_expression)
    logger.info(f"Calculating formula: {python_expression}, result: {result}")
    return {"success": True, "result": result}

@mcp.tool()
def room_temperature_humidity() -> dict:
    """获取房间温度和湿度"""
    logger.info(f"Question:")
    return {"success": True, "result": {"temperature": 25, "humidity": 60}}

# Start the server
if __name__ == "__main__":
    mcp.run(transport="stdio")
