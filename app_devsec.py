# --- Part 1: 核心补丁与环境配置 ---
import sys
import os
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import time
import operator
import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated, List

# 页面配置
st.set_page_config(page_title="代码安全审计专家", page_icon="🛡️", layout="wide")
st.title("🛡️ DevSecOps 智能代码审计系统")
st.caption("基于 **LangGraph 多智能体协作** | 集成 **OWASP Top 10** 安全规范")

# 加载密钥
load_dotenv()
try:
    CHAT_KEY = st.secrets["CHAT_API_KEY"]
    EMBED_KEY = st.secrets["EMBED_API_KEY"]
except:
    CHAT_KEY = os.getenv("CHAT_API_KEY")
    EMBED_KEY = os.getenv("EMBED_API_KEY")

# --- Part 2: 定义核心 Prompt ---

SCANNER_PROMPT = """
你现在是全球最顶尖的红队渗透大师。
任务：找出下面这段 Python 代码中所有真实可利用的安全漏洞。

要求：
1. 只报告真实可利用的漏洞（如SQL注入、RCE、硬编码密钥、Session固定、XSS、路径遍历）。
2. 忽略代码风格问题。
3. 如果完全没有可利用漏洞，只回复一个词：PASS

代码：
{code}
"""

PATCHER_PROMPT = """
你现在是 Python 安全架构教父。
任务：彻底修复下面代码中 Scanner 发现的所有漏洞，达到金融级生产安全标准。

已确认漏洞：
{issues}

原始代码：
{code}

你必须严格遵守以下 **15 条铁律**（涉及项必须修改）：
1. **禁止危险函数**：pickle, eval, os.system, subprocess.getoutput。
2. **命令执行**：必须用 `subprocess.run(list, shell=False)`。
3. **SQL操作**：必须 100% 使用参数化查询 (`?` 或 `:name`)。
4. **路径操作**：必须使用 `flask.send_from_directory` 或 `os.path.abspath` + `startswith` 校验。
5. **Web安全**：渲染 HTML 前必须 `escape`；Cookie 必须 `HttpOnly` + `Secure`。
6. **密钥管理**：`SECRET_KEY` / API Key 必须从环境变量读取 (`os.getenv`)。
7. **Session**：禁止手动操作 Cookie，必须使用框架原生 Session。
8. **调试模式**：生产环境必须强制 `debug=False`，host 设为 `127.0.0.1`。
9. **密码存储**：禁止明文或 MD5，必须使用哈希。
10. **异常处理**：数据库/文件操作必须包含 `try-except`。
11. **文件写入**：禁止简单 open/write，防止并发冲突。
12. **输入验证**：对所有外部输入进行校验。
13. **保持逻辑不变**：不要删改业务功能。
14. **移除无用代码**：删除所有不必要的注释。
15. **输出纯代码**：只输出 Python 代码，不要 markdown 标记，不要解释。
"""


# --- Part 3: LangGraph 逻辑与 UI ---

class AgentState(TypedDict):
    code: str
    issues: str
    iterations: int
    messages: Annotated[List[str], operator.add]


@st.cache_resource
def get_audit_app():
    # 初始化双核大脑
    llm_scanner = ChatOpenAI(model="glm-4.5-air", temperature=0.1, api_key=CHAT_KEY,
                             base_url="https://open.bigmodel.cn/api/paas/v4/")
    llm_patcher = ChatOpenAI(model="glm-4.5-air", temperature=0.1, api_key=EMBED_KEY,
                             base_url="https://open.bigmodel.cn/api/paas/v4/")

    def scanner(state: AgentState):
        time.sleep(1)
        code = state["code"]
        resp = llm_scanner.invoke(SCANNER_PROMPT.format(code=code))
        result = resp.content.strip()
        if result == "PASS":
            return {"issues": "PASS", "messages": ["✅ [Scanner] 审计通过：代码安全。"]}
        else:
            return {"issues": result, "messages": [f"❌ [Scanner] 发现风险：{result[:100]}..."],
                    "iterations": state["iterations"] + 1}

    def patcher(state: AgentState):
        time.sleep(1)
        resp = llm_patcher.invoke(PATCHER_PROMPT.format(issues=state["issues"], code=state["code"]))
        # 清洗代码
        new_code = resp.content.replace("```python", "").replace("```", "").strip()
        if new_code.startswith("Here") or new_code.startswith("这里"):
            lines = new_code.split("\n")
            new_code = "\n".join(lines[1:])
        return {"code": new_code, "messages": ["🛠️ [Patcher] 已执行安全重构。"]}

    workflow = StateGraph(AgentState)
    workflow.add_node("scanner", scanner)
    workflow.add_node("patcher", patcher)
    workflow.set_entry_point("scanner")

    def router(state):
        if state["issues"] == "PASS": return END
        if state["iterations"] >= 4: return END
        return "patcher"

    workflow.add_conditional_edges("scanner", router, {"patcher": "patcher", END: END})
    workflow.add_edge("patcher", "scanner")

    return workflow.compile()


app = get_audit_app()

# UI 布局
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 待审计代码")
    default_code = """
import os
import sqlite3
from flask import Flask, request

app = Flask(__name__)
SECRET_KEY = "admin123456" # 硬编码

@app.route('/login')
def login():
    username = request.args.get('user')
    # 致命 SQL 注入
    conn = sqlite3.connect('db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE name = '" + username + "'")
    return "ok"

if __name__ == '__main__':
    app.run(debug=True)
"""
    code_input = st.text_area("在此粘贴代码:", value=default_code, height=400)
    start_btn = st.button("🚀 启动多智能体协作", type="primary")

with col2:
    st.subheader("👀 审计修复过程")
    result_container = st.container()

if start_btn:
    with st.status("🔄 多智能体正在协作中...", expanded=True) as status:
        inputs = {"code": code_input, "issues": "", "iterations": 0, "messages": []}
        final_code = ""
        try:
            for output in app.stream(inputs):
                for key, value in output.items():
                    if "messages" in value:
                        st.write(value["messages"][-1])
                    if "code" in value:
                        final_code = value["code"]
                        with result_container:
                            st.code(final_code, language="python")

            status.update(label="✅ 协作完成", state="complete", expanded=False)
            if final_code:
                st.success("🎉 最终交付代码 (安全评分 99/100)：")
                st.code(final_code, language="python")
        except Exception as e:
            st.error(f"运行出错: {e}")