# --- 1. 核心补丁 (解决云端数据库报错) ---
import sys
import os

try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

# --- 2. 页面配置 ---
st.set_page_config(page_title="电商智能客服", page_icon="🛍️", layout="wide")
st.title("🛍️ 杭州电商智能客服 (Agent版)")

# 加载环境与密钥
load_dotenv()
try:
    # 优先读云端 Secrets
    CHAT_KEY = st.secrets["CHAT_API_KEY"]
    EMBED_KEY = st.secrets["EMBED_API_KEY"]
except:
    # 本地读 .env
    CHAT_KEY = os.getenv("CHAT_API_KEY")
    EMBED_KEY = os.getenv("EMBED_API_KEY")


# --- 3. 初始化 Agent (带缓存) ---
@st.cache_resource
def get_agent():
    print("🔄 正在初始化客服 Agent...")

    # A. 连接 RAG 知识库
    # 注意：确保 chroma_db 文件夹在项目根目录下
    if not os.path.exists("./chroma_db"):
        st.error("❌ 未找到知识库文件 (chroma_db)，请先在本地运行向量化脚本。")
        st.stop()

    embedding_model = OpenAIEmbeddings(
        model="embedding-2",
        api_key=EMBED_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        check_embedding_ctx_length=False
    )
    vector_db = Chroma(persist_directory="./chroma_db", embedding_function=embedding_model)
    retriever = vector_db.as_retriever(search_kwargs={"k": 3})

    # B. 定义工具集
    @tool
    def lookup_policy(query: str) -> str:
        """查阅公司内部产品手册。当用户询问产品功效、适用肤质、成分、退换货政策时必须使用。"""
        docs = retriever.invoke(query)
        if not docs: return "知识库中未找到相关信息。"
        return "\n\n".join([d.page_content for d in docs])

    @tool
    def get_stock(product_name: str) -> str:
        """查询商品库存数量。"""
        print(f"Checking stock for {product_name}")
        if "神仙水" in product_name: return "库存充足: 88瓶"
        if "清莹露" in product_name: return "库存紧张: 5瓶"
        return "暂时缺货"

    @tool
    def check_delivery(order_id: str) -> str:
        """查询订单物流状态。"""
        return f"订单 {order_id} 已发出，当前位置：杭州萧山集散中心，预计明日送达。"

    # C. 组装 LangGraph Agent
    llm = ChatOpenAI(
        model="glm-4.5-air",
        api_key=CHAT_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4/"
    )

    return create_react_agent(model=llm, tools=[lookup_policy, get_stock, check_delivery])


agent_executor = get_agent()

# --- 4. 聊天界面逻辑 ---

# 初始化历史记录
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# 侧边栏：清空
with st.sidebar:
    st.markdown("### 🛠️ 控制台")
    if st.button("🗑️ 清空对话记录"):
        st.session_state["messages"] = []
        st.rerun()

# 渲染历史消息
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# 处理用户输入
user_input = st.chat_input("请输入问题 (例如：神仙水敏感肌能用吗？还有货吗？)")

if user_input:
    # 1. 显示用户输入
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 2. AI 思考与回答
    with st.chat_message("assistant"):
        # 状态容器
        with st.status("🤖 AI 正在多步推理...", expanded=True) as status:
            inputs = {"messages": st.session_state["messages"]}
            final_response = ""

            # 流式获取每一步
            for chunk in agent_executor.stream(inputs, stream_mode="values"):
                latest_msg = chunk["messages"][-1]

                # 工具调用显示
                if latest_msg.type == "ai" and latest_msg.tool_calls:
                    tool_name = latest_msg.tool_calls[0]["name"]
                    tool_args = latest_msg.tool_calls[0]["args"]
                    st.write(f"🔨 **正在调用工具**: `{tool_name}`")
                    st.caption(f"参数: {tool_args}")

                # 工具结果显示
                elif latest_msg.type == "tool":
                    st.write(f"✅ **工具返回**: {latest_msg.content[:100]}...")

                # 最终回复
                elif latest_msg.type == "ai":
                    final_response = latest_msg.content

            status.update(label="✨ 回答完毕", state="complete", expanded=False)

        # 显示最终答案
        st.write(final_response)
        st.session_state["messages"].append({"role": "assistant", "content": final_response})