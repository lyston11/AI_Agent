# 🚀 AI Agent Portfolio | lyston的实战项目集

👋 你好！我是lyston，一名专注于 **AI Agent** 和 **大模型应用落地** 的开发者（浙江工商大学硕士在读）。
本仓库包含了我在 **LangGraph**、**RAG** 和 **Multi-Agent** 领域的三个核心实战项目源码。

> **在线演示地址 (Live Demo):**
> * 🛡️ **DevSecOps 代码审计 Agent**: [lyston-devsec-ops.streamlit.app](https://lyston-devsec-ops.streamlit.app)
> * ⚖️ **智能合同风控系统**: [lyston-legal-audit.streamlit.app](https://lyston-legal-audit.streamlit.app)
> * 🛍️ **电商智能导购助手**: [lyston-shop-agent.streamlit.app](https://lyston-shop-agent.streamlit.app)

---

## 📂 项目结构说明 (Project Structure)

本仓库采用 Monorepo 结构，包含三个独立的 Streamlit 应用：

### 1. 🛡️ DevSecOps 智能代码审计系统 (Multi-Agent)
* **入口文件**: `app_devsec.py`
* **核心技术**:
    * **LangGraph**: 构建 `Scanner` -> `Patcher` -> `Reviewer` 状态机。
    * **Self-Correction**: 通过 Conditional Edges 实现自动修复循环。
    * **DeepSeek API**: 底层推理模型。

### 2. ⚖️ 企业级智能合同风控审核 (Legal Tech)
* **入口文件**: `app_audit.py`
* **测试数据**: `霸王条款合同示例.pdf`
* **核心技术**:
    * **Structured Output**: 利用 Pydantic + Function Calling 输出标准 JSON 风险报告。
    * **OCR**: 处理非结构化 PDF/扫描件。

### 3. 🛍️ 电商全链路智能导购 (RAG + Tools)
* **入口文件**: `app_chat.py`
* **向量库**: `chroma_db/` (预置产品知识库)
* **核心技术**:
    * **Advanced RAG**: 混合检索 + 重排序。
    * **Tools**: 模拟库存查询 API 调用。

---

## 🛠️ 本地运行指南 (How to Run)

如果你希望在本地运行这些项目：

1. **克隆仓库**
   ```bash
   git clone https://github.com/lyston11/AI_Agent.git
   cd AI_Agent