# --- 必须放在第一行，用于修复 Streamlit Cloud 的数据库报错 ---
__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
# ---------------------------------------------------------

import streamlit as st
# ... (后面跟着你原来的代码)
# --- 模块 1: 基础设置 ---
import streamlit as st
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# 1. 设置网页标题
st.set_page_config(page_title="杭州电商智能客服", page_icon="🤖", layout="wide")
st.title("🤖 杭州电商智能客服 (Agent版)")

# 2. 加载环境
load_dotenv()
chat_key = os.getenv("CHAT_API_KEY")
embed_key = os.getenv("EMBED_API_KEY")


# 3. 定义缓存函数 (只运行一次，极大提升速度)
@st.cache_resource
def get_agent():
    print("🔄 正在初始化 Agent...")

    # --- A. 准备 RAG ---
    embedding_model = OpenAIEmbeddings(
        model="embedding-2",
        api_key=embed_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        check_embedding_ctx_length=False
    )
    vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_model)
    retriever = vector_db.as_retriever(search_kwargs={"k": 3})

    # --- B. 定义工具 ---
    @tool
    def lookup_policy(query: str) -> str:
        """查阅公司内部知识库/产品手册。当用户询问产品功效、成分、退换货政策时使用。"""
        docs = retriever.invoke(query)
        if not docs: return "未找到信息。"
        return "\n\n".join([d.page_content for d in docs])

    @tool
    def get_stock(product_name: str) -> str:
        """查询商品库存。"""
        if "神仙水" in product_name: return "库存充足: 88瓶"
        return "暂时缺货"

    @tool
    def check_delivery(order_id: str) -> str:
        """查询物流状态。"""
        return f"订单 {order_id} 已发出，当前位置：杭州萧山。"

    # --- C. 组装 Agent ---
    llm = ChatOpenAI(
        model="glm-4.5-air",
        api_key=chat_key,
        base_url="https://open.bigmodel.cn/api/paas/v4/"
    )

    # 创建并返回这个 Agent
    return create_react_agent(model=llm, tools=[lookup_policy, get_stock, check_delivery])


# 获取 Agent 实例
agent_executor = get_agent()

# --- 模块 2: 聊天记录管理 ---

# 如果抽屉里没有 messages 这个本子，就放一本新的进去
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 侧边栏：清空对话按钮
with st.sidebar:
    if st.button("🗑️ 清空对话"):
        st.session_state["messages"] = []
        st.rerun() # 刷新网页

# 把本子里的历史记录画在屏幕上
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- 模块 3: 处理用户输入 ---

# 当用户输入了内容...
user_input = st.chat_input("请输入问题，例如：神仙水有货吗？")

if user_input:
    # 1. 显示用户的消息
    with st.chat_message("user"):
        st.write(user_input)
    # 记在本子上
    st.session_state["messages"].append({"role": "user", "content": user_input})

    # 2. AI 开始干活
    with st.chat_message("assistant"):
        # 创建一个状态容器 (显示 "AI 正在思考...")
        with st.status("🤖 AI 正在大脑风暴...", expanded=True) as status:

            # 构造输入
            inputs = {"messages": st.session_state["messages"]}

            # 流式运行 Agent
            final_response = ""
            for chunk in agent_executor.stream(inputs, stream_mode="values"):
                latest_msg = chunk["messages"][-1]

                # 如果是工具调用 (Tool Call) -> 显示在状态框里
                if latest_msg.type == "ai" and latest_msg.tool_calls:
                    tool_name = latest_msg.tool_calls[0]["name"]
                    tool_args = latest_msg.tool_calls[0]["args"]
                    st.write(f"🔨 **正在调用工具**: `{tool_name}`")
                    st.json(tool_args)  # 展示参数

                # 如果是工具返回 (Tool Output) -> 显示结果
                elif latest_msg.type == "tool":
                    st.write(f"✅ **工具返回结果**: {latest_msg.content[:100]}...")  # 只显示前100字

                # 如果是最终回复
                elif latest_msg.type == "ai" and not latest_msg.tool_calls:
                    final_response = latest_msg.content

            # 任务完成，更新状态框标题
            status.update(label="✨ 回答完毕", state="complete", expanded=False)

        # 3. 把最终答案写出来
        st.write(final_response)
        # 记在本子上
        st.session_state["messages"].append({"role": "assistant", "content": final_response})