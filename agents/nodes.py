# agents/nodes.py
import os, uuid, time, json
from typing import Dict, Any, Callable
from mcp import create_mcp_message, get_conversation_id
from tools.git_tool import clone_repo, list_files, cleanup_repo
from tools.static_analysis import extract_metrics
from tools.llm_tool_groq import summarize_text_for_academic, groq_chat
from tools.pdf_tool import md_to_pdf
from utils.validation import (
    validate_mcp_message, validate_github_url, 
    ValidationError, SecurityViolationError
)
from utils.logging_config import system_logger, security_logger, setup_logging
from utils.resilience import limit_execution_time, with_timeout

# Initialize logging
setup_logging()

TMP_OUT = os.path.join(os.getcwd(), "output")
os.makedirs(TMP_OUT, exist_ok=True)

def repo_node(msg: Dict[str, Any], coordinator_send: Callable) -> Dict[str, Any]:
    """
    Clone repository and emit Analyzer message with enhanced validation and logging
    
    Args:
        msg: MCP message containing repo_url
        coordinator_send: Function to send messages to coordinator
        
    Returns:
        Status dictionary with repo_path or error information
    """
    start_time = time.time()
    conversation_id = get_conversation_id(msg)
    
    try:
        # Validate incoming message
        validated_msg = validate_mcp_message(msg)
        content = validated_msg["content"]
        repo_url = content.get("repo_url")
        
        if not repo_url:
            raise ValidationError("repo_url is required")
        
        # Log agent execution start
        system_logger.logger.info("agent_execution_start", extra={
            "event_type": "agent_execution_start",
            "agent_name": "RepoNode",
            "conversation_id": conversation_id
        })
        
        # Clone repository with validation
        repo_path = clone_repo(repo_url)
        
        # List files with security constraints
        files = list_files(repo_path, max_files=5000, 
                          allowed_extensions=['.py', '.js', '.ts', '.md', '.txt', '.json', '.yaml', '.yml'])
        
        # Prepare payload for next agent
        payload = {
            "repo_path": repo_path, 
            "files": files,
            "file_count": len(files),
            "repo_url": repo_url
        }
        
        # Send to next agent
        out = create_mcp_message(
            role="agent", 
            name="AnalyzerNode", 
            content=payload, 
            conversation_id=conversation_id
        )
        coordinator_send(out)
        
        # Log successful execution
        execution_time = time.time() - start_time
        system_logger.log_agent_execution(
            agent_name="RepoNode",
            conversation_id=conversation_id,
            execution_time=execution_time,
            success=True
        )
        
        return {
            "status": "ok", 
            "repo_path": repo_path,
            "file_count": len(files),
            "execution_time": execution_time
        }
        
    except (ValidationError, SecurityViolationError) as e:
        # Log validation/security errors
        execution_time = time.time() - start_time
        security_logger.log_validation_error(str(e), str(msg), conversation_id)
        system_logger.log_agent_execution(
            agent_name="RepoNode",
            conversation_id=conversation_id,
            execution_time=execution_time,
            success=False,
            error=str(e)
        )
        
        # Send error to coordinator
        error_msg = create_mcp_message(
            role="agent", 
            name="Coordinator", 
            content={"error": f"Validation error: {str(e)}", "error_type": "validation"},
            conversation_id=conversation_id
        )
        coordinator_send(error_msg)
        
        return {"error": str(e), "error_type": "validation"}
        
    except Exception as e:
        # Log unexpected errors
        execution_time = time.time() - start_time
        system_logger.log_agent_execution(
            agent_name="RepoNode",
            conversation_id=conversation_id,
            execution_time=execution_time,
            success=False,
            error=str(e)
        )
        
        # Send error to coordinator
        error_msg = create_mcp_message(
            role="agent",
            name="Coordinator",
            content={"error": f"Repository error: {str(e)}", "error_type": "system"},
            conversation_id=conversation_id
        )
        coordinator_send(error_msg)
        
        return {"error": str(e), "error_type": "system"}

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
        # Generate markdown filename starting with "Gen-Authering"  
        md_filename = f"Gen-Authering-{conversation_id}.md"
        md_path = os.path.join(TMP_OUT, md_filename)
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
    # Generate PDF filename starting with "Gen-Authering"
    pdf_filename = f"Gen-Authering-{conversation_id}.pdf"
    pdf_out = os.path.join(TMP_OUT, pdf_filename)
    md_to_pdf(md_path, pdf_out)
    out = create_mcp_message(role="agent", name="Coordinator", content={"status":"pdf_ready", "pdf_path": pdf_out}, conversation_id=conversation_id)
    coordinator_send(out)
    return {"status":"pdf_ready", "pdf_path": pdf_out}

def evaluator_node(msg: Dict[str, Any], coordinator_send: Callable) -> Dict[str, Any]:
    """
    Enhanced readability evaluator for markdown documents with validation and logging
    
    Args:
        msg: MCP message containing md_path
        coordinator_send: Function to send messages to coordinator
        
    Returns:
        Dictionary with evaluation results or error information
    """
    start_time = time.time()
    conversation_id = get_conversation_id(msg)
    
    try:
        import textstat
    except ImportError:
        system_logger.logger.error("textstat_import_error", extra={
            "event_type": "import_error",
            "package": "textstat",
            "agent": "EvaluatorNode"
        })
        # Fallback: return basic metrics without textstat
        return {"error": "textstat package not available", "error_type": "dependency"}
    
    try:
        # Validate incoming message
        validated_msg = validate_mcp_message(msg)
        content = validated_msg["content"]
        md_path = content.get("md_path")
        
        if not md_path:
            raise ValidationError("md_path is required")
        
        # Validate file path exists and is readable
        if not os.path.exists(md_path):
            raise ValidationError(f"Markdown file not found: {md_path}")
        
        # Security check: ensure file is in allowed directory
        abs_md_path = os.path.abspath(md_path)
        if not abs_md_path.startswith(os.path.abspath("output")):
            raise SecurityViolationError("Markdown file outside allowed directory")
        
        system_logger.logger.info("evaluator_start", extra={
            "event_type": "agent_execution_start",
            "agent_name": "EvaluatorNode",
            "conversation_id": conversation_id,
            "md_path": md_path
        })
        
        # Read and analyze the markdown file
        with open(md_path, 'r', encoding='utf-8') as f:
            txt = f.read()
        
        # Basic validation of content
        if len(txt.strip()) == 0:
            raise ValidationError("Markdown file is empty")
        
        if len(txt) > 50000:  # Limit file size for security
            system_logger.logger.warning("large_file_evaluation", extra={
                "event_type": "security_warning",
                "file_size": len(txt),
                "md_path": md_path
            })
            txt = txt[:50000]  # Truncate for safety
        
        # Calculate readability metrics
        evaluation_results = {}
        
        try:
            evaluation_results["flesch_reading_ease"] = textstat.flesch_reading_ease(txt)
            evaluation_results["flesch_kincaid_grade"] = textstat.flesch_kincaid(txt)
            evaluation_results["automated_readability_index"] = textstat.automated_readability_index(txt)
            evaluation_results["word_count"] = textstat.lexicon_count(txt)
            evaluation_results["sentence_count"] = textstat.sentence_count(txt)
            evaluation_results["avg_sentence_length"] = textstat.avg_sentence_length(txt)
        except Exception as metric_error:
            system_logger.logger.warning("textstat_calculation_error", extra={
                "event_type": "calculation_error",
                "error": str(metric_error),
                "md_path": md_path
            })
            # Provide basic fallback metrics
            evaluation_results["word_count"] = len(txt.split())
            evaluation_results["char_count"] = len(txt)
            evaluation_results["flesch_reading_ease"] = None
        
        # Send results to coordinator
        out = create_mcp_message(
            role="agent", 
            name="Coordinator", 
            content={
                "status": "eval_done",
                **evaluation_results
            }, 
            conversation_id=conversation_id
        )
        coordinator_send(out)
        
        # Log successful execution
        execution_time = time.time() - start_time
        system_logger.log_agent_execution(
            agent_name="EvaluatorNode",
            conversation_id=conversation_id,
            execution_time=execution_time,
            success=True
        )
        
        return {
            "status": "completed",
            **evaluation_results,
            "execution_time": execution_time
        }
        
    except (ValidationError, SecurityViolationError) as e:
        execution_time = time.time() - start_time
        security_logger.log_validation_error(str(e), str(msg), conversation_id)
        system_logger.log_agent_execution(
            agent_name="EvaluatorNode",
            conversation_id=conversation_id,
            execution_time=execution_time,
            success=False,
            error=str(e)
        )
        
        return {"error": str(e), "error_type": "validation"}
        
    except Exception as e:
        execution_time = time.time() - start_time
        system_logger.log_agent_execution(
            agent_name="EvaluatorNode",
            conversation_id=conversation_id,
            execution_time=execution_time,
            success=False,
            error=str(e)
        )
        
        # Send error to coordinator
        error_msg = create_mcp_message(
            role="agent",
            name="Coordinator",
            content={"error": f"Evaluation error: {str(e)}", "error_type": "system"},
            conversation_id=conversation_id
        )
        coordinator_send(error_msg)
        
        return {"error": str(e), "error_type": "system"}
