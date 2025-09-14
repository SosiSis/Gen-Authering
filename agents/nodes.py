# agents/nodes.py
import os, uuid, time, json
from mcp import create_mcp_message, get_conversation_id
from tools.git_tool import clone_repo, list_files
from tools.static_analysis import extract_metrics
from tools.llm_tool_groq import summarize_text_for_academic, groq_chat
from tools.pdf_tool import md_to_pdf

TMP_OUT = os.path.join(os.getcwd(), "output")
os.makedirs(TMP_OUT, exist_ok=True)

def repo_node(msg, coordinator_send):
    """Clone repo and emit Analyzer message"""
    content = msg["content"]
    repo_url = content.get("repo_url")
    repo_path = clone_repo(repo_url)
    files = list_files(repo_path)
    payload = {"repo_path": repo_path, "files": files}
    out = create_mcp_message(role="agent", name="AnalyzerNode", content=payload, conversation_id=get_conversation_id(msg))
    coordinator_send(out)
    return {"status":"ok", "repo_path": repo_path}

def analyzer_node(msg, coordinator_send):
    """Extract metrics and produce a short natural-language summary for WriterNode to expand"""
    content = msg["content"]
    repo_path = content.get("repo_path")
    
    if not repo_path:
        error_msg = create_mcp_message(role="agent", name="Coordinator", content={"error": "No repo_path provided"}, conversation_id=get_conversation_id(msg))
        coordinator_send(error_msg)
        return {"error": "No repo_path provided"}
    
    try:
        metrics = extract_metrics(repo_path)
        # For speed: read README or concat small files
        readme_text = ""
        for candidate in ("README.md", "README.rst"):
            p = os.path.join(repo_path, candidate)
            if os.path.exists(p):
                readme_text = open(p,'r',encoding='utf-8').read()
                break
        short_context = (readme_text or "") + "\n\nTop functions: " + ", ".join(metrics.get("top_functions", [])[:10])
        # Ask Groq to summarize into an academic abstract + bullets of contributions
        abstract = summarize_text_for_academic(short_context)
        payload = {"repo_path": repo_path, "metrics": metrics, "abstract": abstract}
        out = create_mcp_message(role="agent", name="WriterNode", content=payload, conversation_id=get_conversation_id(msg))
        coordinator_send(out)
        return {"status":"ok"}
    except Exception as e:
        error_msg = create_mcp_message(role="agent", name="Coordinator", content={"error": f"Analyzer error: {str(e)}"}, conversation_id=get_conversation_id(msg))
        coordinator_send(error_msg)
        return {"error": str(e)}

def writer_node(msg, coordinator_send):
    """Generate a Markdown draft. Supports being called with role=agent (auto) or role=user (human-edits)."""
    content = msg["content"]
    repo_path = content.get("repo_path")
    metrics = content.get("metrics", {})
    abstract = content.get("abstract", "")
    conversation_id = msg["metadata"]["conversation_id"]

    # If role == user, content may contain 'user_md' (edits). Then forward to PDFAgent on approval.
    if msg["role"] == "user" and content.get("user_md"):
        # update draft storage
        md_path = os.path.join(TMP_OUT, f"{conversation_id}.md")
        with open(md_path, "w", encoding='utf-8') as f:
            f.write(content["user_md"])
        # send status back to coordinator (Writer done with user updates)
        status_msg = create_mcp_message(role="agent", name="Coordinator", content={"status":"user_updated","md_path":md_path}, conversation_id=conversation_id)
        coordinator_send(status_msg)
        return {"status":"user_updated"}
    else:
        # auto-generate a more complete draft using Groq
        system_msg = {"role":"system","content":"You are an academic writer. Produce a paper-style markdown including Title, Abstract, Introduction, Methods and Results summary from context."}
        user_msg = {"role":"user","content": f"Abstract:\n{abstract}\n\nMetrics:\n{json.dumps(metrics)}\n\nProduce an extended paper-style markdown draft."}
        md_text = groq_chat([system_msg, user_msg], model="llama-3.3-70b-versatile", temperature=0.2, max_tokens=1200)
        md_path = os.path.join(TMP_OUT, f"{conversation_id}.md")
        with open(md_path, "w", encoding='utf-8') as f:
            f.write(md_text)
        # send draft to Coordinator so UI can pick it up
        out = create_mcp_message(role="agent", name="Coordinator", content={"status":"draft_ready", "md_path": md_path}, conversation_id=conversation_id)
        coordinator_send(out)
        return {"status":"draft_ready", "md_path": md_path}

def pdf_node(msg, coordinator_send):
    """Convert markdown to PDF (triggered on approval)"""
    content = msg["content"]
    md_path = content.get("md_path")
    conversation_id = msg["metadata"]["conversation_id"]
    pdf_out = os.path.join(TMP_OUT, f"{conversation_id}.pdf")
    md_to_pdf(md_path, pdf_out)
    out = create_mcp_message(role="agent", name="Coordinator", content={"status":"pdf_ready", "pdf_path": pdf_out}, conversation_id=conversation_id)
    coordinator_send(out)
    return {"status":"pdf_ready", "pdf_path": pdf_out}

def evaluator_node(msg, coordinator_send):
    """Simple readability evaluator for the draft markdown"""
    import textstat
    content = msg["content"]
    md_path = content.get("md_path")
    if not md_path:
        return {"error":"no_md_path"}
    try:
        txt = open(md_path,'r',encoding='utf-8').read()
        flesch = textstat.flesch_reading_ease(txt)
    except Exception as e:
        flesch = None
        print(f"Evaluator error: {e}")
    out = create_mcp_message(role="agent", name="Coordinator", content={"status":"eval_done","flesch_reading_ease": flesch}, conversation_id=msg["metadata"]["conversation_id"])
    coordinator_send(out)
    return {"flesch": flesch}
