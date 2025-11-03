# tools/git_tool.py
import tempfile
import os
import shutil
import time
from typing import List, Optional
from git import Repo, GitCommandError

from utils.validation import validate_github_url, SecurityViolationError, ValidationError
from utils.resilience import retry_with_backoff, git_circuit_breaker, RetryStrategy
from utils.logging_config import system_logger, security_logger

@git_circuit_breaker
@retry_with_backoff(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=5.0,
    max_delay=60.0,
    exceptions=(GitCommandError, ConnectionError, OSError),
    timeout=300.0  # 5 minute timeout for git operations
)
def clone_repo(repo_url: str, dest_dir: Optional[str] = None) -> str:
    """
    Securely clone a GitHub repository with validation and resilience
    
    Args:
        repo_url: GitHub repository URL to clone
        dest_dir: Optional destination directory
        
    Returns:
        Path to cloned repository
        
    Raises:
        ValidationError: If repo URL is invalid
        SecurityViolationError: If repo URL is suspicious
        GitCommandError: If git operations fail
    """
    start_time = time.time()
    
    try:
        # Validate repository URL
        validated_url = validate_github_url(repo_url)
        
        # Create destination directory
        dest = dest_dir or tempfile.mkdtemp(prefix="multiagent_repo_")
        
        # Ensure destination directory exists
        os.makedirs(dest, exist_ok=True)
        
        # Log the clone attempt
        system_logger.logger.info("git_clone_start", extra={
            "event_type": "git_clone_start",
            "repo_url": validated_url,
            "dest_dir": dest
        })
        
        # Clone the repository with security options
        repo = Repo.clone_from(
            validated_url, 
            dest,
            # Security options
            depth=1,  # Shallow clone to reduce attack surface
            single_branch=True,  # Only clone default branch
            config='http.sslVerify=true'  # Ensure SSL verification
        )
        
        clone_time = time.time() - start_time
        
        # Log successful clone
        system_logger.logger.info("git_clone_success", extra={
            "event_type": "git_clone_success",
            "repo_url": validated_url,
            "dest_dir": dest,
            "clone_time": clone_time,
            "repo_size_mb": _get_directory_size(dest) / (1024 * 1024)
        })
        
        return dest
        
    except (ValidationError, SecurityViolationError) as e:
        # Log security/validation errors
        security_logger.log_validation_error(str(e), repo_url)
        raise
        
    except GitCommandError as e:
        # Log git-specific errors
        system_logger.log_error(e, {
            "function": "clone_repo",
            "repo_url": repo_url,
            "dest_dir": dest_dir,
            "clone_time": time.time() - start_time
        })
        raise
        
    except Exception as e:
        # Log unexpected errors
        system_logger.log_error(e, {
            "function": "clone_repo",
            "repo_url": repo_url,
            "dest_dir": dest_dir,
            "clone_time": time.time() - start_time
        })
        raise


def list_files(root: str, max_files: int = 10000, 
               allowed_extensions: Optional[List[str]] = None) -> List[str]:
    """
    Safely list files in a directory with security constraints
    
    Args:
        root: Root directory to scan
        max_files: Maximum number of files to return (security limit)
        allowed_extensions: Optional list of allowed file extensions
        
    Returns:
        List of relative file paths
        
    Raises:
        ValidationError: If root directory is invalid
        ValueError: If too many files found
    """
    if not root or not os.path.exists(root):
        raise ValidationError("Root directory does not exist")
    
    # Security check: ensure root is an absolute path within allowed directories
    root = os.path.abspath(root)
    if not (root.startswith('/tmp/') or root.startswith(tempfile.gettempdir())):
        # In production, you might want to be more restrictive
        system_logger.logger.warning("file_listing_suspicious_path", extra={
            "event_type": "security_warning",
            "root_path": root,
            "message": "File listing outside temporary directory"
        })
    
    files = []
    file_count = 0
    
    try:
        for dir_path, dir_names, file_names in os.walk(root):
            # Security: Skip hidden directories and common sensitive directories
            dir_names[:] = [d for d in dir_names if not d.startswith('.') and 
                           d not in ['.git', '.env', '.secret', 'node_modules', '__pycache__']]
            
            for filename in file_names:
                file_count += 1
                
                # Security limit on number of files
                if file_count > max_files:
                    system_logger.logger.warning("file_listing_limit_exceeded", extra={
                        "event_type": "security_warning",
                        "root_path": root,
                        "max_files": max_files,
                        "message": "File listing limit exceeded"
                    })
                    raise ValueError(f"Too many files found (>{max_files}). Possible security issue.")
                
                # Skip hidden and sensitive files
                if filename.startswith('.') or filename in ['secrets', 'private_key', '.env']:
                    continue
                
                # Filter by extension if specified
                if allowed_extensions:
                    _, ext = os.path.splitext(filename.lower())
                    ext = ext.lstrip('.')
                    if ext not in [e.lstrip('.') for e in allowed_extensions]:
                        continue
                
                relative_path = os.path.relpath(os.path.join(dir_path, filename), root)
                files.append(relative_path)
        
        # Log file listing
        system_logger.logger.info("file_listing_completed", extra={
            "event_type": "file_listing_completed",
            "root_path": root,
            "file_count": len(files),
            "total_scanned": file_count
        })
        
        return files
        
    except Exception as e:
        system_logger.log_error(e, {
            "function": "list_files",
            "root_path": root,
            "file_count": file_count
        })
        raise


def cleanup_repo(repo_path: str) -> bool:
    """
    Safely cleanup a cloned repository
    
    Args:
        repo_path: Path to repository to cleanup
        
    Returns:
        True if cleanup successful
    """
    try:
        if os.path.exists(repo_path) and repo_path.startswith(tempfile.gettempdir()):
            shutil.rmtree(repo_path)
            
            system_logger.logger.info("repo_cleanup_success", extra={
                "event_type": "repo_cleanup",
                "repo_path": repo_path,
                "success": True
            })
            
            return True
        else:
            system_logger.logger.warning("repo_cleanup_skipped", extra={
                "event_type": "repo_cleanup",
                "repo_path": repo_path,
                "success": False,
                "reason": "Path not in temp directory or doesn't exist"
            })
            return False
            
    except Exception as e:
        system_logger.log_error(e, {
            "function": "cleanup_repo",
            "repo_path": repo_path
        })
        return False


def _get_directory_size(path: str) -> int:
    """Get the total size of a directory in bytes"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except (OSError, IOError):
        pass  # Ignore errors for individual files
    return total_size
