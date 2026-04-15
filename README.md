# StockAI 股票分析 Agent

基于 LangChain 的智能股票分析助手，moomoo 风格 Streamlit Web UI。

---

## 环境搭建

```bash
# 创建虚拟环境
python -m venv .venv

# 激活（PowerShell）
.\.venv\Scripts\Activate.ps1

# 激活（Git Bash）
source .venv/Scripts/activate

# 安装依赖
pip install -r requirements.txt
```

### 启动 Web UI
```bash
streamlit run app.py
```

---

## 项目结构

```
stock-agent/
├── app.py              # Streamlit Web UI（主程序）
├── tools.py            # 工具定义（get_stock_data / search_web 等）
├── mcp_server.py       # MCP Server（Gmail 发信工具，供外部 MCP 客户端调用）
├── components/
│   └── stock_ticker.py # 实时股价侧边栏组件（1秒自动刷新）
├── skills/             # 工具使用说明（注入 system prompt）
│   ├── skill_get_stock_data.md
│   ├── skill_get_stock_history.md
│   ├── skill_search_web.md
│   └── skill_send_email.md
├── charts/             # 走势图输出目录（运行时自动创建）
├── vectorstore/        # ChromaDB 向量库（运行时自动创建，不上传 git）
├── .env                # API Keys（不上传 git，参考 .env.example）
├── .env.example        # API Keys 模板
├── token.pickle        # Gmail OAuth 凭证（不上传 git）
└── requirements.txt
```

---

## API Keys

所有 key 存放在 `.env`（不上传 git），通过 `python-dotenv` 读取。

```
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
TAVILY_API_KEY=your_tavily_api_key
```

---

## 双模型架构

```
用户提问
   ↓
Groq（工具调用循环，最多 5 步）
   ├─ search_web        ← 新闻、近期动态
   ├─ get_stock_data    ← 实时股价
   ├─ get_stock_history ← 历史走势图
   ├─ search_documents  ← 财报 PDF 检索
   └─ send_email_report ← 发送邮件报告
   ↓
开发模式 → Groq 生成最终报告
正式模式 → Gemini 2.5 Flash 生成最终报告
              ↓（429 限速）
          等待 65 秒重试
              ↓（重试仍 429）
          Groq 降级兜底
```

- **Groq**：负责多步工具调用（llama-4-scout，速度快；可切换 openai/gpt-oss-120b，质量更高但较慢）
- **Gemini 2.5 Flash**：负责生成最终高质量报告（正式模式）
- **开发模式**：全程使用 Groq，适合调试

---

## Gemini 免费层限制

| 限制 | 额度 |
|------|------|
| RPM（每分钟请求数） | 5 |
| 配额重置时间 | 北京时间 15:00 |

### 限速处理逻辑
1. 触发 429 → 等待 65 秒自动重试
2. 重试仍然 429 → 标记 `gemini_exhausted = True`，后续请求直接走 Groq
3. 刷新页面 → 状态重置，恢复使用 Gemini

---

## 主要功能

### 实时进度面板
处理时显示 `st.status` 可折叠进度面板，实时展示每一步工具调用（工具名 + 参数），完成后自动折叠。

### 快捷卡片
首页欢迎屏和聊天记录下方均显示 4 个快捷提问卡片，处理中自动隐藏防止误点，处理完成后自动刷新恢复。

### RAG 财报检索
侧边栏上传财报 PDF，自动分片向量化存入 ChromaDB。问财务数据时优先从文档检索，未找到时改用网络搜索。

### MCP Server
`mcp_server.py` 提供标准 MCP 协议的 Gmail 发信工具，可接入 Claude Desktop 等 MCP 客户端。

---

## 工具说明

### `get_stock_data(ticker)`
- 数据源：yfinance
- 返回：当前价格、涨跌幅、52周高低点、市盈率、成交量

### `search_web(query)`
- 数据源：Tavily API
- 搜索关键词必须用英文，每次返回 3 条结果
- 自动附加当天日期提升结果时效性

### `get_stock_history(ticker, period)`
- period 可选：`1mo` / `3mo` / `6mo` / `1y` / `2y`
- 走势图保存到 `charts/`，页面自动显示

### `search_documents(query)`
- 从已上传的财报 PDF 中检索相关内容
- 向量库持久化到 `./vectorstore`，重启后不丢失
- 嵌入模型：`paraphrase-multilingual-MiniLM-L12-v2`（支持中文，本地运行）
- 首次上传 PDF 时会自动下载模型（约 120MB）

### `send_email_report(to, subject, body)`
- 通过 Gmail API 发送
- 首次使用需要 OAuth 授权，生成 `token.pickle`
- `token.pickle` 不要删除，否则需要重新授权

---

## Gmail OAuth 初始化

首次使用邮件功能：
1. 触发邮件发送操作
2. 浏览器弹出 Google 授权页面
3. 授权完成后生成 `token.pickle`，后续自动使用

换机器时复制 `token.pickle`，或重新授权。

---

## System Prompt 编写经验

本项目用 Groq（LLaMA）负责工具调用，LLaMA 对指令遵循能力相对较弱，措辞对工具选择行为影响很大。

### 各模型遵循指令能力对比

| 模型 | 能力 | 说明 |
|------|------|------|
| Claude | 最强 | 软语气基本能遵守 |
| GPT-4o | 强 | 大多数情况够用 |
| Gemini 2.5 Flash | 中等 | 需稍明确措辞 |
| LLaMA（Groq） | 较弱 | 必须用强制句式 |

### 结论：对 LLM 下指令要像写强制规定，而不是建议

**无效写法：**
```
如果用户询问财务数据，优先调用 search_documents
```

**有效写法：**
```
用户询问财报、财务数据时，【必须】首先调用 search_documents，禁止直接调用 search_web 或使用训练数据回答
```

两个关键点：
1. system prompt 用禁止句式（"禁止"、"【必须】"）
2. tool description 里同步加强，LLM 选工具时会同时参考两处

### 工具调用次数控制

LLM 可能对同一工具反复调用（如 search_web 调用 4 次）。通过 prompt 明确限制次数（`search_web 最多调用 2 次`）可以缓解，但不能完全保证——代码层面的硬限制更可靠。

---

## 注意事项

- `tools.py` 不要随意修改，工具签名变更会影响 LangChain 工具绑定
- `skills/*.md` 是注入 system prompt 的工具说明，修改后立即生效
- `charts/` 目录运行时自动创建，无需手动建
- Pydantic 警告（Python 3.14 兼容性）不影响运行，忽略即可
- matplotlib 使用 Agg 后端（非交互式），避免 Windows GUI 线程阻塞
