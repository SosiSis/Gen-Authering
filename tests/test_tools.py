# tests/test_tools.py
import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock, mock_open
import ast

from tools.git_tool import clone_repo, list_files
from tools.static_analysis import extract_metrics
from tools.pdf_tool import md_to_pdf
from tools.llm_tool_groq import groq_chat, summarize_text_for_academic, get_groq_client


class TestGitTool:
    """Test suite for git_tool.py"""
    
    def test_clone_repo_success(self):
        """Test successful repository cloning"""
        with patch('tools.git_tool.Repo') as mock_repo:
            mock_repo.clone_from.return_value = None
            with patch('tempfile.mkdtemp') as mock_mkdtemp:
                mock_mkdtemp.return_value = "/tmp/test_repo"
                
                result = clone_repo("https://github.com/test/repo")
                
                assert result == "/tmp/test_repo"
                mock_repo.clone_from.assert_called_once_with("https://github.com/test/repo", "/tmp/test_repo")
    
    def test_clone_repo_with_custom_dest(self):
        """Test repository cloning with custom destination"""
        with patch('tools.git_tool.Repo') as mock_repo:
            mock_repo.clone_from.return_value = None
            
            result = clone_repo("https://github.com/test/repo", "/custom/path")
            
            assert result == "/custom/path"
            mock_repo.clone_from.assert_called_once_with("https://github.com/test/repo", "/custom/path")
    
    def test_list_files(self):
        """Test file listing functionality"""
        # Create a temporary directory structure for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test files
            os.makedirs(os.path.join(temp_dir, "subdir"))
            with open(os.path.join(temp_dir, "file1.py"), 'w') as f:
                f.write("test content")
            with open(os.path.join(temp_dir, "subdir", "file2.txt"), 'w') as f:
                f.write("test content")
            
            files = list_files(temp_dir)
            
            assert len(files) == 2
            assert "file1.py" in files
            assert os.path.join("subdir", "file2.txt") in files


class TestStaticAnalysis:
    """Test suite for static_analysis.py"""
    
    def test_extract_metrics_empty_directory(self):
        """Test metrics extraction from empty directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics = extract_metrics(temp_dir)
            
            assert metrics["num_files"] == 0
            assert metrics["num_py"] == 0
            assert metrics["top_functions"] == []
    
    def test_extract_metrics_with_python_files(self):
        """Test metrics extraction with Python files"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test Python file with functions
            py_content = '''
def test_function():
    pass

def another_function():
    return True

class TestClass:
    def method_one(self):
        pass
'''
            with open(os.path.join(temp_dir, "test.py"), 'w') as f:
                f.write(py_content)
            
            # Create a non-Python file
            with open(os.path.join(temp_dir, "readme.txt"), 'w') as f:
                f.write("This is a readme")
            
            metrics = extract_metrics(temp_dir)
            
            assert metrics["num_files"] == 2
            assert metrics["num_py"] == 1
            assert "test_function" in metrics["top_functions"]
            assert "another_function" in metrics["top_functions"]
            assert "method_one" in metrics["top_functions"]
    
    def test_extract_metrics_invalid_python_file(self):
        """Test metrics extraction with invalid Python syntax"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create Python file with invalid syntax
            with open(os.path.join(temp_dir, "invalid.py"), 'w') as f:
                f.write("def invalid_syntax(:\n    pass")
            
            # Should not crash, should handle gracefully
            metrics = extract_metrics(temp_dir)
            
            assert metrics["num_files"] == 1
            assert metrics["num_py"] == 1
            # Functions list should still be initialized
            assert isinstance(metrics["top_functions"], list)


class TestPDFTool:
    """Test suite for pdf_tool.py"""
    
    def test_md_to_pdf_basic(self):
        """Test basic markdown to PDF conversion"""
        with tempfile.TemporaryDirectory() as temp_dir:
            md_path = os.path.join(temp_dir, "test.md")
            pdf_path = os.path.join(temp_dir, "output", "test.pdf")
            
            # Create test markdown
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write("# Test Title\n\nThis is a test document.")
            
            result = md_to_pdf(md_path, pdf_path)
            
            assert result == pdf_path
            assert os.path.exists(pdf_path)
            assert os.path.getsize(pdf_path) > 0  # PDF should not be empty
    
    def test_md_to_pdf_with_complex_markdown(self):
        """Test markdown to PDF with complex formatting"""
        with tempfile.TemporaryDirectory() as temp_dir:
            md_path = os.path.join(temp_dir, "complex.md")
            pdf_path = os.path.join(temp_dir, "complex.pdf")
            
            # Create complex markdown
            complex_md = '''
# Main Title

## Abstract
This is an abstract with **bold** and *italic* text.

## Introduction
Here's a paragraph with some code: `print("hello")`

```python
def example():
    return "code block"
```

### Subsection
- List item 1
- List item 2
- List item 3

| Table | Header |
|-------|--------|
| Cell 1| Cell 2 |
'''
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(complex_md)
            
            result = md_to_pdf(md_path, pdf_path)
            
            assert result == pdf_path
            assert os.path.exists(pdf_path)
            assert os.path.getsize(pdf_path) > 0


class TestLLMToolGroq:
    """Test suite for llm_tool_groq.py"""
    
    @patch.dict('os.environ', {'GROQ_API_KEY': 'test_api_key'})
    def test_get_groq_client(self):
        """Test Groq client creation"""
        with patch('tools.llm_tool_groq.Groq') as mock_groq:
            mock_client = MagicMock()
            mock_groq.return_value = mock_client
            
            client = get_groq_client()
            
            mock_groq.assert_called_once_with(api_key='test_api_key')
            assert client == mock_client
    
    @patch.dict('os.environ', {})
    def test_get_groq_client_missing_api_key(self):
        """Test Groq client creation without API key"""
        # Remove the import-time check by reloading the module
        with pytest.raises(EnvironmentError, match="Set GROQ_API_KEY env var"):
            # This should raise an error during module import/initialization
            import importlib
            import tools.llm_tool_groq
            importlib.reload(tools.llm_tool_groq)
    
    def test_groq_chat_success(self):
        """Test successful Groq chat completion"""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch('tools.llm_tool_groq.get_groq_client') as mock_get_client:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Hello! How can I help you?"
            mock_client.chat.completions.create.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = groq_chat(messages)
            
            assert result == "Hello! How can I help you?"
            mock_client.chat.completions.create.assert_called_once()
    
    def test_groq_chat_with_fallback(self):
        """Test Groq chat with fallback model"""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch('tools.llm_tool_groq.get_groq_client') as mock_get_client:
            mock_client = MagicMock()
            
            # First call fails, second succeeds
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Fallback response"
            mock_client.chat.completions.create.side_effect = [
                Exception("Primary model failed"),
                mock_response
            ]
            mock_get_client.return_value = mock_client
            
            result = groq_chat(messages)
            
            assert result == "Fallback response"
            assert mock_client.chat.completions.create.call_count == 2
    
    def test_groq_chat_all_models_fail(self):
        """Test Groq chat when all models fail"""
        messages = [{"role": "user", "content": "Hello"}]
        
        with patch('tools.llm_tool_groq.get_groq_client') as mock_get_client:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("All models failed")
            mock_get_client.return_value = mock_client
            
            result = groq_chat(messages)
            
            assert "Error: Unable to generate response" in result
            assert "All models failed" in result
    
    def test_summarize_text_for_academic(self):
        """Test academic text summarization"""
        test_text = "This is a technical repository with important contributions."
        
        with patch('tools.llm_tool_groq.groq_chat') as mock_groq_chat:
            mock_groq_chat.return_value = "# Academic Summary\nThis repository contains significant technical contributions..."
            
            result = summarize_text_for_academic(test_text)
            
            assert result == "# Academic Summary\nThis repository contains significant technical contributions..."
            mock_groq_chat.assert_called_once()
            # Check that the call includes the expected prompt structure
            args = mock_groq_chat.call_args[0][0]
            assert len(args) == 2
            assert args[0]["role"] == "system"
            assert args[1]["role"] == "user"
            assert test_text in args[1]["content"]
    
    def test_summarize_text_for_academic_error_handling(self):
        """Test academic text summarization error handling"""
        test_text = "This is a test text."
        
        with patch('tools.llm_tool_groq.groq_chat') as mock_groq_chat:
            mock_groq_chat.side_effect = Exception("API Error")
            
            result = summarize_text_for_academic(test_text)
            
            assert "# Academic Summary" in result
            assert "could not be fully analyzed" in result
            assert test_text[:500] in result


if __name__ == "__main__":
    pytest.main([__file__])