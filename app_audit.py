# --- 1. 核心补丁 ---
import sys
import os

try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import streamlit as st
from docx import Document
from pypdf import PdfReader
from rapidocr_onnxruntime import RapidOCR
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from typing import List

# --- 2. 页面配置 ---
st.set_page_config(page_title="合同风控审计", page_icon="⚖️", layout="wide")
st.title("⚖️ 智能合同风控审计系统 (ToB)")

load_dotenv()
try:
    CHAT_KEY = st.secrets["CHAT_API_KEY"]
except:
    CHAT_KEY = os.getenv("CHAT_API_KEY")


# --- 3. 核心逻辑函数 ---

@st.cache_resource
def get_ocr():
    # 初始化 OCR 引擎
    return RapidOCR()


@st.cache_resource
def get_audit_chain():
    llm = ChatOpenAI(
        model="glm-4.5-air",
        api_key=CHAT_KEY,
        base_url="https://open.bigmodel.cn/api/paas/v4/"
    )

    class ContractReview(BaseModel):
        risk_score: int = Field(description="根据风险严重程度动态评估的总分 (0-100)")
        risk_points: List[str] = Field(description="列出具体风险条款，并标注其严重等级(高/中/低)")
        suggestion: str = Field(description="针对性的修改建议")
        is_passed: bool = Field(description="是否通过")

    parser = PydanticOutputParser(pydantic_object=ContractReview)

    prompt = PromptTemplate(
        template="""
        你是一个精通《民法典》与《劳动法》的资深法务专家。
        请审核以下合同内容，寻找所有潜在法律风险。

        请根据以下【风险严重等级标准】累加计算总分（满分100）：
        🔴 **高危风险 (+25分)**：违反法律强制性规定、霸王条款、完全免责。
        🟠 **中度风险 (+15分)**：显失公平、违约金过高、管辖权不利。
        🟡 **低度风险 (+5分)**：表述模糊、歧义。

        {format_instructions}

        待审核合同内容:
        {contract_text}
        """,
        input_variables=["contract_text"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    return prompt | llm | parser


ocr_engine = get_ocr()
audit_chain = get_audit_chain()

# --- 4. 界面交互 ---

st.markdown("### 📂 上传合同文件")
st.info("支持格式：PDF (含扫描件), Word (.docx), TXT")

uploaded_file = st.file_uploader("请拖拽文件到此处", type=["pdf", "docx", "txt"])

if uploaded_file and st.button("🚀 开始审计"):
    with st.status("🔍 正在读取并分析文件...", expanded=True) as status:

        # --- A. 文件读取 (含云端 OCR 修复) ---
        text_content = ""
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()

        try:
            if file_ext == ".pdf":
                st.write("📄 检测到 PDF，正在解析...")
                pdf_reader = PdfReader(uploaded_file)

                # 1. 先尝试直接提取文字
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text: text_content += text + "\n"

                # 2. 如果文字太少，启动 OCR (针对扫描件)
                if len(text_content) < 50:
                    st.warning("⚠️ 文本提取过少，正在启用 OCR 识别扫描件 (速度较慢，请耐心等待)...")

                    # 【核心修复】将 PDF 转为图片流进行 OCR
                    # 由于云端环境没有 pdf2image，我们尝试直接读取 PDF 中的图片流
                    # 如果 PDF 是纯图片扫描件，pypdf 可以提取图片对象

                    for page in pdf_reader.pages:
                        if page.images:
                            for img in page.images:
                                # 直接把图片二进制数据喂给 OCR
                                result, _ = ocr_engine(img.data)
                                if result:
                                    for line in result:
                                        text_content += line[1] + "\n"

                    if len(text_content) < 10:
                        st.error("❌ OCR 识别失败：可能是图片格式不支持或文件损坏。")
                        st.stop()
                    else:
                        st.success(f"✅ OCR 识别成功！提取了 {len(text_content)} 字")

            elif file_ext == ".docx":
                st.write("📄 检测到 Word，正在解析...")
                doc = Document(uploaded_file)
                for para in doc.paragraphs:
                    text_content += para.text + "\n"

            else:
                # TXT
                text_content = uploaded_file.read().decode("utf-8")

            # --- B. 提交审核 ---
            if len(text_content) < 10:
                status.update(label="❌ 文件内容为空", state="error")
                st.error("无法读取文件内容，请检查文件是否加密或损坏。")
                st.stop()

            st.write(f"✅ 读取成功 ({len(text_content)} 字)，正在进行法律推理...")

            # 调用链条
            result = audit_chain.invoke({"contract_text": text_content})

            status.update(label="✅ 审计完成", state="complete", expanded=False)

            # --- C. 结果展示 ---
            st.divider()

            # 顶部指标卡
            c1, c2 = st.columns(2)
            c1.metric("风险评分", f"{result.risk_score} 分", delta="-高危" if result.risk_score > 60 else "安全")
            if result.is_passed:
                c2.success("## ✅ 建议通过")
            else:
                c2.error("## 🚫 建议驳回")

            # 风险详情
            st.subheader("⚠️ 风险条款分析")
            if not result.risk_points:
                st.success("未发现明显法律风险。")
            else:
                for point in result.risk_points:
                    st.warning(point)

            # 修改建议
            with st.expander("💡 查看专家修改建议", expanded=True):
                st.info(result.suggestion)

        except Exception as e:
            st.error(f"处理过程中发生错误: {e}")