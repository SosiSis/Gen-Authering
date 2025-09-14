# 🧑‍🔬 Multi-Agent Publication System

This project demonstrates a **multi-agent system** (built with LangGraph + MCP) that:
- Clones a GitHub repo
- Analyzes source files
- Generates a research-style publication using **Groq LLMs**
- Saves it as a **PDF**
- Provides evaluation metrics
- Offers a **Streamlit dashboard** for human-in-the-loop editing

## 🚀 Run Locally
```bash
git clone https://github.com/YOUR_USERNAME/multiagent_pub.git
cd multiagent_pub
pip install -r requirements.txt
export GROQ_API_KEY="your_api_key_here"
streamlit run streamlit_app.py
```

## 🛠 Agents
- **RepoAgent** – clone & list repo files
- **AnalyzerAgent** – extract metrics
- **WriterAgent** – generate publication
- **PDFAgent** – export PDF
- **EvaluatorAgent** – compute readability metrics

## 🔑 Features
- Uses **Model Context Protocol (MCP)** for structured messaging
- Powered by **Groq LLaMA-3 / Mixtral**
- Human-in-the-loop editing in Streamlit
