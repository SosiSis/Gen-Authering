# tests/test_agents.py
import pytest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock, call
import uuid

from agents.nodes import (
    repo_node, analyzer_node, writer_node, 
    pdf_node, evaluator_node, create_mcp_message
)
from agents.langgraph_coordinator import LangGraphCoordinator
from agents.graph_spec import build_graph


class TestMCPMessage:
    """Test MCP message creation and handling"""
    
    def test_create_mcp_message_basic(self):
        """Test basic MCP message creation"""
        msg = create_mcp_message(
            role="agent",
            name="TestAgent", 
            content={"test": "data"}
        )
        
        assert msg["type"] == "message"
        assert msg["role"] == "agent"
        assert msg["name"] == "TestAgent"
        assert msg["content"] == {"test": "data"}
        assert "metadata" in msg
        assert "timestamp" in msg["metadata"]
        assert "conversation_id" in msg["metadata"]
    
    def test_create_mcp_message_with_conversation_id(self):
        """Test MCP message creation with specific conversation ID"""
        conv_id = "test-conversation-123"
        msg = create_mcp_message(
            role="user",
            name="UserAgent",
            content={"action": "test"},
            conversation_id=conv_id
        )
        
        assert msg["metadata"]["conversation_id"] == conv_id


class TestAgentNodes:
    """Test suite for agent node functions"""
    
    def test_repo_node_success(self):
        """Test successful repository node execution"""
        # Mock coordinator send function
        coordinator_send = MagicMock()
        
        # Create test message
        test_msg = {
            "content": {"repo_url": "https://github.com/test/repo"},
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('agents.nodes.clone_repo') as mock_clone, \
             patch('agents.nodes.list_files') as mock_list:
            
            mock_clone.return_value = "/tmp/test_repo"
            mock_list.return_value = ["file1.py", "file2.txt"]
            
            result = repo_node(test_msg, coordinator_send)
            
            # Verify function calls
            mock_clone.assert_called_once_with("https://github.com/test/repo")
            mock_list.assert_called_once_with("/tmp/test_repo")
            
            # Verify coordinator message
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["name"] == "AnalyzerNode"
            assert sent_msg["content"]["repo_path"] == "/tmp/test_repo"
            assert sent_msg["content"]["files"] == ["file1.py", "file2.txt"]
            
            # Verify return value
            assert result["status"] == "ok"
            assert result["repo_path"] == "/tmp/test_repo"
    
    def test_analyzer_node_success(self):
        """Test successful analyzer node execution"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "content": {"repo_path": "/test/repo", "files": ["test.py"]},
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('agents.nodes.extract_metrics') as mock_extract, \
             patch('agents.nodes.summarize_text_for_academic') as mock_summarize, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_extract.return_value = {
                "num_files": 2,
                "num_py": 1,
                "top_functions": ["func1", "func2"]
            }
            mock_summarize.return_value = "Academic summary of the repository"
            mock_exists.return_value = True
            mock_open.return_value.__enter__.return_value.read.return_value = "# Test Repo\nDescription"
            
            result = analyzer_node(test_msg, coordinator_send)
            
            # Verify function calls
            mock_extract.assert_called_once_with("/test/repo")
            mock_summarize.assert_called_once()
            
            # Verify coordinator message
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["name"] == "WriterNode"
            assert "repo_path" in sent_msg["content"]
            assert "metrics" in sent_msg["content"]
            assert "abstract" in sent_msg["content"]
            
            assert result["status"] == "ok"
    
    def test_analyzer_node_missing_repo_path(self):
        """Test analyzer node with missing repo path"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "content": {},  # Missing repo_path
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        result = analyzer_node(test_msg, coordinator_send)
        
        # Verify error handling
        coordinator_send.assert_called_once()
        sent_msg = coordinator_send.call_args[0][0]
        assert sent_msg["name"] == "Coordinator"
        assert "error" in sent_msg["content"]
        
        assert "error" in result
        assert "No repo_path provided" in result["error"]
    
    def test_analyzer_node_exception_handling(self):
        """Test analyzer node exception handling"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "content": {"repo_path": "/test/repo"},
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('agents.nodes.extract_metrics') as mock_extract:
            mock_extract.side_effect = Exception("Test error")
            
            result = analyzer_node(test_msg, coordinator_send)
            
            # Verify error handling
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["name"] == "Coordinator"
            assert "error" in sent_msg["content"]
            
            assert "error" in result
            assert "Test error" in result["error"]
    
    def test_writer_node_auto_generate(self):
        """Test writer node automatic generation"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "role": "agent",
            "content": {
                "repo_path": "/test/repo",
                "metrics": {"num_files": 5},
                "abstract": "Test abstract"
            },
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('agents.nodes.groq_chat') as mock_groq, \
             patch('builtins.open', create=True) as mock_open, \
             patch('os.path.join') as mock_join:
            
            mock_groq.return_value = "# Generated Paper\n\nContent here"
            mock_join.return_value = "/output/test-conv-123.md"
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = writer_node(test_msg, coordinator_send)
            
            # Verify Groq call
            mock_groq.assert_called_once()
            call_args = mock_groq.call_args[0][0]
            assert len(call_args) == 2  # system and user messages
            assert call_args[0]["role"] == "system"
            assert call_args[1]["role"] == "user"
            
            # Verify file writing
            mock_file.write.assert_called_once_with("# Generated Paper\n\nContent here")
            
            # Verify coordinator message
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["name"] == "Coordinator"
            assert sent_msg["content"]["status"] == "draft_ready"
            
            assert result["status"] == "draft_ready"
    
    def test_writer_node_user_edits(self):
        """Test writer node handling user edits"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "role": "user",
            "content": {"user_md": "# Edited content\n\nUser modifications"},
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('builtins.open', create=True) as mock_open, \
             patch('os.path.join') as mock_join:
            
            mock_join.return_value = "/output/test-conv-123.md"
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            result = writer_node(test_msg, coordinator_send)
            
            # Verify file writing
            mock_file.write.assert_called_once_with("# Edited content\n\nUser modifications")
            
            # Verify coordinator message
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["name"] == "Coordinator"
            assert sent_msg["content"]["status"] == "user_updated"
            
            assert result["status"] == "user_updated"
    
    def test_pdf_node_success(self):
        """Test successful PDF node execution"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "content": {"md_path": "/test/input.md"},
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('agents.nodes.md_to_pdf') as mock_pdf, \
             patch('os.path.join') as mock_join:
            
            mock_join.return_value = "/output/test-conv-123.pdf"
            mock_pdf.return_value = "/output/test-conv-123.pdf"
            
            result = pdf_node(test_msg, coordinator_send)
            
            # Verify PDF generation
            mock_pdf.assert_called_once_with("/test/input.md", "/output/test-conv-123.pdf")
            
            # Verify coordinator message
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["name"] == "Coordinator"
            assert sent_msg["content"]["status"] == "pdf_ready"
            assert sent_msg["content"]["pdf_path"] == "/output/test-conv-123.pdf"
            
            assert result["status"] == "pdf_ready"
            assert result["pdf_path"] == "/output/test-conv-123.pdf"
    
    def test_evaluator_node_success(self):
        """Test successful evaluator node execution"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "content": {"md_path": "/test/document.md"},
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('builtins.open', create=True) as mock_open, \
             patch('textstat.flesch_reading_ease') as mock_flesch:
            
            mock_open.return_value.__enter__.return_value.read.return_value = "Sample text content"
            mock_flesch.return_value = 65.5
            
            result = evaluator_node(test_msg, coordinator_send)
            
            # Verify text analysis
            mock_flesch.assert_called_once_with("Sample text content")
            
            # Verify coordinator message
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["name"] == "Coordinator"
            assert sent_msg["content"]["status"] == "eval_done"
            assert sent_msg["content"]["flesch_reading_ease"] == 65.5
            
            assert result["flesch"] == 65.5
    
    def test_evaluator_node_missing_md_path(self):
        """Test evaluator node with missing markdown path"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "content": {},  # Missing md_path
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        result = evaluator_node(test_msg, coordinator_send)
        
        assert result["error"] == "no_md_path"
    
    def test_evaluator_node_exception_handling(self):
        """Test evaluator node exception handling"""
        coordinator_send = MagicMock()
        
        test_msg = {
            "content": {"md_path": "/test/document.md"},
            "metadata": {"conversation_id": "test-conv-123"}
        }
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.side_effect = Exception("File not found")
            
            result = evaluator_node(test_msg, coordinator_send)
            
            # Should still send a message to coordinator
            coordinator_send.assert_called_once()
            sent_msg = coordinator_send.call_args[0][0]
            assert sent_msg["content"]["flesch_reading_ease"] is None


class TestLangGraphCoordinator:
    """Test suite for LangGraphCoordinator"""
    
    def test_coordinator_initialization(self):
        """Test coordinator initialization"""
        coordinator = LangGraphCoordinator()
        
        assert len(coordinator.nodes) == 0
        assert len(coordinator.edges) == 0
        assert len(coordinator.consumers_log) == 0
        assert not coordinator.running
    
    def test_register_node(self):
        """Test node registration"""
        coordinator = LangGraphCoordinator()
        test_func = lambda msg, send: {"status": "ok"}
        
        coordinator.register_node("TestNode", test_func)
        
        assert "TestNode" in coordinator.nodes
        assert coordinator.nodes["TestNode"] == test_func
    
    def test_add_edge(self):
        """Test edge addition"""
        coordinator = LangGraphCoordinator()
        
        coordinator.add_edge("NodeA", "NodeB")
        coordinator.add_edge("NodeA", "NodeC")
        
        assert "NodeA" in coordinator.edges
        assert coordinator.edges["NodeA"] == ["NodeB", "NodeC"]
    
    def test_send_message(self):
        """Test message sending"""
        coordinator = LangGraphCoordinator()
        
        test_msg = {"type": "message", "content": "test"}
        coordinator.send(test_msg)
        
        assert not coordinator.msg_queue.empty()
        received_msg = coordinator.msg_queue.get()
        assert received_msg["type"] == "message"
        assert received_msg["content"] == "test"
        assert "metadata" in received_msg
    
    def test_run_once_with_registered_node(self):
        """Test run_once with registered node"""
        coordinator = LangGraphCoordinator()
        
        # Register a test node
        test_results = []
        def test_node(msg, send):
            test_results.append(msg)
            return {"status": "processed"}
        
        coordinator.register_node("TestNode", test_node)
        
        # Send a message
        test_msg = {"name": "TestNode", "content": "test"}
        coordinator.send(test_msg)
        coordinator.run_once()
        
        # Verify execution
        assert len(test_results) == 1
        assert test_results[0]["content"] == "test"
        assert len(coordinator.consumers_log) == 1
    
    def test_get_conversation_events(self):
        """Test conversation event retrieval"""
        coordinator = LangGraphCoordinator()
        
        # Add some test messages
        msg1 = {"metadata": {"conversation_id": "conv1"}, "content": "message1"}
        msg2 = {"metadata": {"conversation_id": "conv2"}, "content": "message2"}
        msg3 = {"metadata": {"conversation_id": "conv1"}, "content": "message3"}
        
        coordinator.consumers_log.extend([msg1, msg2, msg3])
        
        # Test filtering by conversation ID
        conv1_events = coordinator.get_conversation_events("conv1")
        assert len(conv1_events) == 2
        assert conv1_events[0]["content"] == "message1"
        assert conv1_events[1]["content"] == "message3"
        
        # Test getting all events
        all_events = coordinator.get_conversation_events()
        assert len(all_events) == 3


class TestGraphSpec:
    """Test suite for graph_spec.py"""
    
    def test_build_graph(self):
        """Test graph building"""
        coordinator = build_graph()
        
        # Verify nodes are registered
        expected_nodes = [
            "Coordinator", "RepoNode", "AnalyzerNode", "WriterNode", 
            "PDFNode", "EvaluatorNode", "RepoAgent", "AnalyzerAgent", 
            "WriterAgent", "PDFAgent", "EvaluatorAgent"
        ]
        
        for node_name in expected_nodes:
            assert node_name in coordinator.nodes
        
        # Verify some edges exist
        assert "RepoNode" in coordinator.edges
        assert "AnalyzerNode" in coordinator.edges["RepoNode"]
    
    def test_coordinator_node_function(self):
        """Test coordinator node function"""
        from agents.graph_spec import coordinator_node
        
        test_msg = {"content": {"status": "test"}}
        coordinator_send = MagicMock()
        
        result = coordinator_node(test_msg, coordinator_send)
        
        assert result["status"] == "coordinator_handled"


if __name__ == "__main__":
    pytest.main([__file__])