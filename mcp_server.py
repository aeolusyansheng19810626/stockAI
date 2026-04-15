import asyncio
import base64
import json
import pickle
import os
from email.mime.text import MIMEText

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# ====== Gmail 授权 ======
def get_gmail_service():
    creds = None
    token_path = r"C:\stock-agent\token.pickle"
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build('gmail', 'v1', credentials=creds)

# ====== 创建 MCP Server ======
server = Server("stock-email-server")

# ====== 注册工具：告诉 MCP 这个 Server 有哪些工具 ======
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="send_email_report",
            description="发送邮件到指定的Gmail邮箱",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "收件人邮箱地址"
                    },
                    "subject": {
                        "type": "string",
                        "description": "邮件标题"
                    },
                    "body": {
                        "type": "string",
                        "description": "邮件正文，包含完整分析内容"
                    }
                },
                "required": ["to", "subject", "body"]
            }
        )
    ]

# ====== 注册工具执行逻辑 ======
@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "send_email_report":
        to = arguments["to"]
        subject = arguments["subject"]
        body = arguments["body"]

        try:
            service = get_gmail_service()
            message = MIMEText(body, 'plain', 'utf-8')
            message['to'] = to
            message['subject'] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(
                userId='me',
                body={'raw': raw}
            ).execute()
            result = f"✅ 邮件已成功发送到 {to}"
        except Exception as e:
            result = f"❌ 发送失败：{e}"

        return [types.TextContent(type="text", text=result)]

    return [types.TextContent(type="text", text=f"未知工具：{name}")]

# ====== 启动 Server ======
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())