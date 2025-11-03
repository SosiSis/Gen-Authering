# tests/test_integration.py
import pytest
import os
import tempfile
import time
from unittest.mock import patch, MagicMock

from agents.nodes import create_mcp_message
from agents.graph_spec import build_graph


class TestEndToEndWorkflow:
    """Integration tests for complete workflows"""
    
    def test_full_pipeline_mock_integration(self):
        """Test the complete pipeline with mocked external dependencies"""
        # Build the coordinator
        coordinator = build_graph()
        
        # Mock all external dependencies
        with patch('tools.git_tool.clone_repo') as mock_clone, \
             patch('tools.git_tool.list_files') as mock_list, \
             patch('tools.static_analysis.extract_metrics') as mock_metrics, \
             patch('tools.llm_tool_groq.summarize_text_for_academic') as mock_summarize, \
             patch('tools.llm_tool_groq.groq_chat') as mock_groq, \
             patch('tools.pdf_tool.md_to_pdf') as mock_pdf, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open:
            
            # Setup mocks
            mock_clone.return_value = "/tmp/test_repo"
            mock_list.return_value = ["main.py", "README.md", "utils/helper.py"]
            mock_metrics.return_value = {
                "num_files": 3,
                "num_py": 2,
                "top_functions": ["main", "helper_func", "process_data"]
            }
            mock_summarize.return_value = "# Academic Summary\n\nThis repository demonstrates..."
            mock_groq.return_value = "# Generated Publication\n\n## Abstract\nThis paper presents..."
            mock_pdf.return_value = "/output/test.pdf"
            mock_exists.return_value = True
            mock_open.return_value.__enter__.return_value.read.return_value = "# Test Repo\nDescription"
            
            # Start the pipeline
            initial_msg = create_mcp_message(
                role="agent",
                name="RepoNode",
                content={"repo_url": "https://github.com/test/repo"}
            )
            
            conversation_id = initial_msg["metadata"]["conversation_id"]
            coordinator.send(initial_msg)
            
            # Process the pipeline step by step
            coordinator.run_once()  # RepoNode -> AnalyzerNode
            coordinator.run_once()  # AnalyzerNode -> WriterNode
            coordinator.run_once()  # WriterNode -> Coordinator (draft ready)
            
            # Verify the pipeline executed correctly
            events = coordinator.get_conversation_events(conversation_id)
            
            # Check that we have the expected events
            repo_events = [e for e in events if e.get("name") == "AnalyzerNode"]
            writer_events = [e for e in events if e.get("name") == "WriterNode"]
            coordinator_events = [e for e in events if e.get("name") == "Coordinator"]
            
            assert len(repo_events) >= 1
            assert len(writer_events) >= 1
            assert len(coordinator_events) >= 1
            
            # Check for draft ready status
            draft_ready_events = [e for e in coordinator_events 
                                if e.get("content", {}).get("status") == "draft_ready"]
            assert len(draft_ready_events) >= 1
            
            # Verify external calls were made
            mock_clone.assert_called_once()
            mock_list.assert_called_once()
            mock_metrics.assert_called_once()
            mock_summarize.assert_called_once()
            mock_groq.assert_called_once()
    
    def test_error_propagation_workflow(self):
        """Test error handling and propagation in the workflow"""
        coordinator = build_graph()
        
        # Mock a failure in the analyzer node
        with patch('tools.git_tool.clone_repo') as mock_clone, \
             patch('tools.git_tool.list_files') as mock_list, \
             patch('tools.static_analysis.extract_metrics') as mock_metrics:
            
            mock_clone.return_value = "/tmp/test_repo"
            mock_list.return_value = ["main.py"]
            mock_metrics.side_effect = Exception("Analysis failed")
            
            # Start the pipeline
            initial_msg = create_mcp_message(
                role="agent",
                name="RepoNode",
                content={"repo_url": "https://github.com/test/repo"}
            )
            
            conversation_id = initial_msg["metadata"]["conversation_id"]
            coordinator.send(initial_msg)
            
            # Process the pipeline
            coordinator.run_once()  # RepoNode -> AnalyzerNode
            coordinator.run_once()  # AnalyzerNode should handle error
            
            # Verify error was handled
            events = coordinator.get_conversation_events(conversation_id)
            error_events = [e for e in events 
                          if e.get("content", {}).get("error") is not None]
            
            assert len(error_events) >= 1
            assert "Analysis failed" in str(error_events[0]["content"]["error"])
    
    def test_user_interaction_workflow(self):
        """Test user interaction and editing workflow"""
        coordinator = build_graph()
        
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            # Simulate user editing workflow
            conversation_id = "test-conversation"
            
            # User sends edited markdown
            user_edit_msg = create_mcp_message(
                role="user",
                name="WriterNode",
                content={"user_md": "# Edited Title\n\nUser modifications here"},
                conversation_id=conversation_id
            )
            
            coordinator.send(user_edit_msg)
            coordinator.run_once()
            
            # Verify file was written
            mock_file.write.assert_called_once_with("# Edited Title\n\nUser modifications here")
            
            # Check events
            events = coordinator.get_conversation_events(conversation_id)
            update_events = [e for e in events 
                           if e.get("content", {}).get("status") == "user_updated"]
            assert len(update_events) >= 1
    
    def test_pdf_generation_workflow(self):
        """Test PDF generation workflow"""
        coordinator = build_graph()
        
        with patch('tools.pdf_tool.md_to_pdf') as mock_pdf:
            mock_pdf.return_value = "/output/test.pdf"
            
            conversation_id = "test-conversation"
            
            # Send PDF generation request
            pdf_msg = create_mcp_message(
                role="agent",
                name="PDFNode",
                content={"md_path": "/test/input.md"},
                conversation_id=conversation_id
            )
            
            coordinator.send(pdf_msg)
            coordinator.run_once()
            
            # Verify PDF generation
            mock_pdf.assert_called_once_with("/test/input.md", "/output/test-conversation.pdf")
            
            # Check events
            events = coordinator.get_conversation_events(conversation_id)
            pdf_events = [e for e in events 
                         if e.get("content", {}).get("status") == "pdf_ready"]
            assert len(pdf_events) >= 1
    
    def test_evaluation_workflow(self):
        """Test evaluation workflow"""
        coordinator = build_graph()
        
        with patch('builtins.open', create=True) as mock_open, \
             patch('textstat.flesch_reading_ease') as mock_flesch:
            
            mock_open.return_value.__enter__.return_value.read.return_value = "Test document content"
            mock_flesch.return_value = 72.3
            
            conversation_id = "test-conversation"
            
            # Send evaluation request
            eval_msg = create_mcp_message(
                role="agent",
                name="EvaluatorNode",
                content={"md_path": "/test/document.md"},
                conversation_id=conversation_id
            )
            
            coordinator.send(eval_msg)
            coordinator.run_once()
            
            # Verify evaluation
            mock_flesch.assert_called_once_with("Test document content")
            
            # Check events
            events = coordinator.get_conversation_events(conversation_id)
            eval_events = [e for e in events 
                          if e.get("content", {}).get("status") == "eval_done"]
            assert len(eval_events) >= 1
            assert eval_events[0]["content"]["flesch_reading_ease"] == 72.3


class TestAgentCommunication:
    """Test inter-agent communication patterns"""
    
    def test_message_routing(self):
        """Test message routing between agents"""
        coordinator = build_graph()
        
        # Track which nodes were called
        called_nodes = []
        
        def track_calls(original_func):
            def wrapper(msg, send):
                called_nodes.append(msg.get("name", "unknown"))
                return original_func(msg, send)
            return wrapper
        
        # Wrap node functions to track calls
        for name, func in coordinator.nodes.items():
            coordinator.nodes[name] = track_calls(func)
        
        with patch('tools.git_tool.clone_repo') as mock_clone, \
             patch('tools.git_tool.list_files') as mock_list:
            
            mock_clone.return_value = "/tmp/test"
            mock_list.return_value = ["test.py"]
            
            # Send initial message
            msg = create_mcp_message("agent", "RepoNode", {"repo_url": "https://github.com/test/repo"})
            coordinator.send(msg)
            coordinator.run_once()
            
            # Verify routing occurred
            assert "RepoNode" in called_nodes
    
    def test_conversation_isolation(self):
        """Test that different conversations are isolated"""
        coordinator = build_graph()
        
        # Create two different conversations
        conv1_msg = create_mcp_message("agent", "Coordinator", {"test": "conv1"})
        conv2_msg = create_mcp_message("agent", "Coordinator", {"test": "conv2"})
        
        conv1_id = conv1_msg["metadata"]["conversation_id"]
        conv2_id = conv2_msg["metadata"]["conversation_id"]
        
        coordinator.send(conv1_msg)
        coordinator.send(conv2_msg)
        coordinator.run_once()
        
        # Verify conversations are separate
        conv1_events = coordinator.get_conversation_events(conv1_id)
        conv2_events = coordinator.get_conversation_events(conv2_id)
        
        assert len(conv1_events) >= 1
        assert len(conv2_events) >= 1
        assert conv1_events[0]["content"]["test"] == "conv1"
        assert conv2_events[0]["content"]["test"] == "conv2"
    
    def test_message_metadata_preservation(self):
        """Test that message metadata is preserved through routing"""
        coordinator = build_graph()
        
        original_time = time.time()
        
        msg = create_mcp_message("agent", "Coordinator", {"test": "metadata"})
        coordinator.send(msg)
        coordinator.run_once()
        
        events = coordinator.get_conversation_events()
        assert len(events) >= 1
        
        event = events[0]
        assert "metadata" in event
        assert "timestamp" in event["metadata"]
        assert "conversation_id" in event["metadata"]


class TestSystemResilience:
    """Test system resilience and error handling"""
    
    def test_node_failure_isolation(self):
        """Test that failure in one node doesn't crash the system"""
        coordinator = build_graph()
        
        # Register a failing node
        def failing_node(msg, send):
            raise Exception("Node failure")
        
        coordinator.register_node("FailingNode", failing_node)
        
        # Send message to failing node
        msg = create_mcp_message("agent", "FailingNode", {"test": "failure"})
        coordinator.send(msg)
        
        # Should not raise exception
        coordinator.run_once()
        
        # System should still be operational
        normal_msg = create_mcp_message("agent", "Coordinator", {"test": "normal"})
        coordinator.send(normal_msg)
        coordinator.run_once()
        
        events = coordinator.get_conversation_events()
        # Should have at least the normal message logged
        assert len(events) >= 1
    
    def test_empty_queue_handling(self):
        """Test handling of empty message queue"""
        coordinator = build_graph()
        
        # Should not raise exception when queue is empty
        coordinator.run_once()
        
        # System should still be operational
        msg = create_mcp_message("agent", "Coordinator", {"test": "after_empty"})
        coordinator.send(msg)
        coordinator.run_once()
        
        events = coordinator.get_conversation_events()
        assert len(events) >= 1


if __name__ == "__main__":
    pytest.main([__file__])