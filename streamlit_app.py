# streamlit_app.py
import streamlit as st
import os
from agents.nodes import create_mcp_message
from agents.graph_spec import build_graph

# Initialize coordinator using graph_spec
coordinator = build_graph()

st.set_page_config(page_title="Multi-Agent Repo→Publication (MCP + Groq)", layout="wide")
st.title("Multi-Agent Publication Generator (MCP + Groq)")

repo_url = st.text_input("GitHub repo URL (https://github.com/owner/repo)")

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None
if "md_path" not in st.session_state:
    st.session_state.md_path = None
if "pdf_path" not in st.session_state:
    st.session_state.pdf_path = None

col1, col2 = st.columns([1,1])

with col1:
    if st.button("Start Pipeline / Generate Draft") and repo_url:
        msg = create_mcp_message(role="agent", name="RepoNode", content={"repo_url": repo_url})
        st.session_state.conversation_id = msg["metadata"]["conversation_id"]
        coordinator.send(msg)
        coordinator.run_once()
        coordinator.run_once()

        events = coordinator.get_conversation_events(st.session_state.conversation_id)
        draft = next((e for e in events if e.get("content",{}).get("status")=="draft_ready"), None)
        if draft:
            st.session_state.md_path = draft["content"]["md_path"]
            st.success("Draft generated — loaded into editor below.")
        else:
            st.warning("Draft not found yet; check logs.")

with col2:
    if st.session_state.md_path:
        if st.button("Run Evaluator on Draft"):
            ev_msg = create_mcp_message(
                role="agent",
                name="EvaluatorNode",
                content={"md_path": st.session_state.md_path},
                conversation_id=st.session_state.conversation_id
            )
            coordinator.send(ev_msg)
            coordinator.run_once()
            ev_events = coordinator.get_conversation_events(st.session_state.conversation_id)
            eval_done = next((e for e in ev_events if e.get("content",{}).get("status")=="eval_done"), None)
            if eval_done:
                st.metric("Flesch reading ease", eval_done["content"].get("flesch_reading_ease"))

st.markdown("## Draft Editor / Human-in-the-loop")
if st.session_state.md_path and os.path.exists(st.session_state.md_path):
    md_text = open(st.session_state.md_path,'r',encoding='utf-8').read()
else:
    md_text = ""

edited = st.text_area("Edit the draft here (Markdown):", value=md_text, height=400)

col3, col4 = st.columns(2)
with col3:
    if st.button("Save Edits (send to Writer as user message)"):
        user_msg = create_mcp_message(
            role="user",
            name="WriterNode",
            content={"user_md": edited},
            conversation_id=st.session_state.conversation_id
        )
        coordinator.send(user_msg)
        coordinator.run_once()
        st.success("Edits saved and sent to WriterNode. Use Approve to render PDF.")

with col4:
    if st.button("Approve & Generate PDF"):
        if st.session_state.conversation_id is None:
            st.error("No active conversation. Generate draft first.")
        else:
            md_path = os.path.join(os.getcwd(), "output", f"{st.session_state.conversation_id}.md")
            with open(md_path, "w", encoding='utf-8') as f:
                f.write(edited)
            approval_msg = create_mcp_message(
                role="agent",
                name="PDFNode",
                content={"md_path": md_path},
                conversation_id=st.session_state.conversation_id
            )
            coordinator.send(approval_msg)
            coordinator.run_once()
            events = coordinator.get_conversation_events(st.session_state.conversation_id)
            pdf_ready = next((e for e in events if e.get("content",{}).get("status")=="pdf_ready"), None)
            if pdf_ready:
                st.session_state.pdf_path = pdf_ready["content"]["pdf_path"]
                st.success("PDF ready — download link below.")
            else:
                st.warning("PDF not ready; check logs.")

if st.session_state.pdf_path and os.path.exists(st.session_state.pdf_path):
    st.markdown("### Download PDF")
    with open(st.session_state.pdf_path, "rb") as f:
        pdf_bytes = f.read()
    st.download_button(
        label="Download PDF",
        data=pdf_bytes,
        file_name=os.path.basename(st.session_state.pdf_path),
        mime="application/pdf"
    )
