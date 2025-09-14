# graph_spec.py
from agents.nodes import repo_node, analyzer_node, writer_node, pdf_node, evaluator_node
from agents.langgraph_coordinator import LangGraphCoordinator

def coordinator_node(msg, coordinator_send):
    """Handle coordinator messages - just log them for now"""
    content = msg.get("content", {})
    print(f"Coordinator received: {content}")
    return {"status": "coordinator_handled"}

def build_graph():
    """Builds and returns a configured LangGraphCoordinator with all nodes and edges."""
    coordinator = LangGraphCoordinator()

    # Register coordinator node to handle coordinator messages
    coordinator.register_node("Coordinator", coordinator_node)

    # Register nodes
    coordinator.register_node("RepoNode", repo_node)
    coordinator.register_node("AnalyzerNode", analyzer_node)
    coordinator.register_node("WriterNode", writer_node)
    coordinator.register_node("PDFNode", pdf_node)
    coordinator.register_node("EvaluatorNode", evaluator_node)

    # Aliases (for MCP naming consistency)
    coordinator.register_node("RepoAgent", repo_node)
    coordinator.register_node("AnalyzerAgent", analyzer_node)
    coordinator.register_node("WriterAgent", writer_node)
    coordinator.register_node("PDFAgent", pdf_node)
    coordinator.register_node("EvaluatorAgent", evaluator_node)

    # Example edges (you can expand/modify as needed)
    coordinator.add_edge("RepoNode", "AnalyzerNode")
    coordinator.add_edge("AnalyzerNode", "WriterNode")
    coordinator.add_edge("WriterNode", "PDFNode")
    coordinator.add_edge("WriterNode", "EvaluatorNode")

    return coordinator
