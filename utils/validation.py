# utils/validation.py
import re
import os
import urllib.parse
from typing import Optional, Dict, Any, List
import logging
import requests

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class SecurityViolationError(Exception):
    """Custom exception for security violations"""
    pass


def validate_github_url(url: str) -> str:
    """
    Validate and sanitize GitHub repository URL
    
    Args:
        url: GitHub repository URL to validate
        
    Returns:
        Sanitized URL
        
    Raises:
        ValidationError: If URL is invalid
        SecurityViolationError: If URL contains security violations
    """
    if not url or not isinstance(url, str):
        raise ValidationError("Repository URL must be a non-empty string")
    
    url = url.strip()
    
    # Basic URL format validation
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as e:
        raise ValidationError(f"Invalid URL format: {e}")
    
    # Must be HTTPS for security
    if parsed.scheme != 'https':
        raise SecurityViolationError("Only HTTPS URLs are allowed for security")
    
    # Must be GitHub
    if parsed.netloc not in ['github.com', 'www.github.com']:
        raise SecurityViolationError("Only GitHub repositories are allowed")
    
    # Basic path validation (should be /owner/repo or /owner/repo.git)
    path_parts = [p for p in parsed.path.split('/') if p]
    if len(path_parts) < 2:
        raise ValidationError("Invalid GitHub repository path. Expected format: https://github.com/owner/repo")
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'\.\./',  # Directory traversal
        r'<script',  # XSS
        r'javascript:',  # JavaScript injection
        r'[;&|`$]',  # Command injection characters
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            raise SecurityViolationError(f"URL contains suspicious pattern: {pattern}")
    
    # Check if repository is publicly accessible (but allow to proceed if check fails)
    try:
        if not _is_github_repo_accessible(url):
            logger.warning(f"Could not verify repository accessibility: {url}")
            # Don't fail validation - proceed with a warning instead
            # This allows the system to work even with network issues
    except Exception as e:
        logger.warning(f"Repository accessibility check failed due to network error: {e}")
        # Continue anyway - network issues shouldn't block valid URLs
    
    # Return sanitized URL
    return url


def _is_github_repo_accessible(url: str) -> bool:
    """
    Check if a GitHub repository is publicly accessible
    
    Args:
        url: GitHub repository URL
        
    Returns:
        True if repository is accessible, False if not accessible or check failed
    """
    try:
        # Convert github.com URL to API URL for checking
        parsed = urllib.parse.urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        
        if len(path_parts) >= 2:
            owner, repo = path_parts[0], path_parts[1]
            # Remove .git suffix if present
            repo = repo.rstrip('.git')
            
            # Use GitHub API to check if repo exists and is public
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            
            # Add headers to identify our request
            headers = {
                'User-Agent': 'Gen-Authering/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(api_url, timeout=10, headers=headers)
            
            if response.status_code == 200:
                repo_data = response.json()
                # Check if repository is public (not private)
                is_public = not repo_data.get('private', True)
                logger.info(f"Repository {owner}/{repo} accessibility check: {'public' if is_public else 'private'}")
                return is_public
            elif response.status_code == 404:
                logger.warning(f"Repository not found or private: {url}")
                return False
            elif response.status_code == 403:
                logger.warning(f"GitHub API rate limited or access denied for {url}")
                # Return True for rate limit issues - assume repo is accessible
                return True
            else:
                logger.warning(f"GitHub API error {response.status_code} for {url}")
                # For other errors, assume accessible to avoid blocking valid URLs
                return True
                
    except requests.exceptions.RequestException as e:
        logger.warning(f"Network error checking repository accessibility: {e}")
        # Network issues shouldn't block URL validation
        return True
    except Exception as e:
        logger.warning(f"Error checking repository accessibility: {e}")
        return True
    
    return True  # Default to accessible if we can't determine otherwise


def validate_file_path(file_path: str, allowed_extensions: Optional[List[str]] = None) -> str:
    """
    Validate file path for security
    
    Args:
        file_path: File path to validate
        allowed_extensions: List of allowed file extensions
        
    Returns:
        Sanitized file path
        
    Raises:
        ValidationError: If path is invalid
        SecurityViolationError: If path contains security violations
    """
    if not file_path or not isinstance(file_path, str):
        raise ValidationError("File path must be a non-empty string")
    
    file_path = file_path.strip()
    
    # Check for directory traversal
    if '..' in file_path or file_path.startswith('/'):
        raise SecurityViolationError("Directory traversal detected in file path")
    
    # Check for suspicious characters
    if re.search(r'[;&|`$<>]', file_path):
        raise SecurityViolationError("File path contains suspicious characters")
    
    # Validate extension if specified
    if allowed_extensions:
        _, ext = os.path.splitext(file_path.lower())
        ext = ext.lstrip('.')
        if ext not in [e.lstrip('.') for e in allowed_extensions]:
            raise ValidationError(f"File extension '{ext}' not allowed. Allowed: {allowed_extensions}")
    
    return file_path


def validate_conversation_id(conv_id: str) -> str:
    """
    Validate conversation ID format
    
    Args:
        conv_id: Conversation ID to validate
        
    Returns:
        Sanitized conversation ID
        
    Raises:
        ValidationError: If ID is invalid
    """
    if not conv_id or not isinstance(conv_id, str):
        raise ValidationError("Conversation ID must be a non-empty string")
    
    conv_id = conv_id.strip()
    
    # Should be UUID-like format
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if not re.match(uuid_pattern, conv_id, re.IGNORECASE):
        raise ValidationError("Conversation ID must be in UUID format")
    
    return conv_id.lower()


def sanitize_user_input(user_input: str, max_length: int = 10000) -> str:
    """
    Sanitize user input for markdown content
    
    Args:
        user_input: User-provided markdown content
        max_length: Maximum allowed length
        
    Returns:
        Sanitized input
        
    Raises:
        ValidationError: If input is invalid
    """
    if not isinstance(user_input, str):
        raise ValidationError("User input must be a string")
    
    if len(user_input) > max_length:
        raise ValidationError(f"Input too long. Maximum {max_length} characters allowed")
    
    # Remove potentially dangerous patterns
    dangerous_patterns = [
        (r'<script[^>]*>.*?</script>', ''),  # Script tags
        (r'javascript:', ''),  # JavaScript URLs
        (r'on\w+\s*=', ''),  # Event handlers
        (r'<iframe[^>]*>.*?</iframe>', ''),  # Iframes
        (r'<object[^>]*>.*?</object>', ''),  # Objects
        (r'<embed[^>]*>.*?</embed>', ''),  # Embeds
    ]
    
    sanitized = user_input
    for pattern, replacement in dangerous_patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE | re.DOTALL)
    
    return sanitized


def validate_mcp_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate MCP message structure and content
    
    Args:
        message: MCP message to validate
        
    Returns:
        Validated message
        
    Raises:
        ValidationError: If message structure is invalid
    """
    if not isinstance(message, dict):
        raise ValidationError("Message must be a dictionary")
    
    # Required fields
    required_fields = ['type', 'role', 'name', 'content', 'metadata']
    for field in required_fields:
        if field not in message:
            raise ValidationError(f"Missing required field: {field}")
    
    # Validate field types and values
    if message['type'] != 'message':
        raise ValidationError("Message type must be 'message'")
    
    if message['role'] not in ['agent', 'user', 'system']:
        raise ValidationError("Invalid role. Must be 'agent', 'user', or 'system'")
    
    if not isinstance(message['name'], str) or not message['name'].strip():
        raise ValidationError("Name must be a non-empty string")
    
    if not isinstance(message['content'], dict):
        raise ValidationError("Content must be a dictionary")
    
    if not isinstance(message['metadata'], dict):
        raise ValidationError("Metadata must be a dictionary")
    
    # Validate metadata structure
    metadata = message['metadata']
    if 'timestamp' not in metadata or 'conversation_id' not in metadata:
        raise ValidationError("Metadata missing required fields: timestamp, conversation_id")
    
    # Sanitize string values in content
    sanitized_message = message.copy()
    sanitized_content = {}
    
    for key, value in message['content'].items():
        if isinstance(value, str):
            if key in ['repo_url']:
                sanitized_content[key] = validate_github_url(value)
            elif key in ['user_md']:
                sanitized_content[key] = sanitize_user_input(value)
            elif key in ['md_path', 'pdf_path']:
                sanitized_content[key] = validate_file_path(value, ['.md', '.pdf'])
            else:
                sanitized_content[key] = value[:1000]  # Limit other strings
        else:
            sanitized_content[key] = value
    
    sanitized_message['content'] = sanitized_content
    return sanitized_message


def check_rate_limits(user_id: str, action: str, limits: Dict[str, tuple]) -> bool:
    """
    Simple rate limiting check (in production, use Redis or similar)
    
    Args:
        user_id: User identifier
        action: Action being performed
        limits: Dictionary of action -> (count, time_window) limits
        
    Returns:
        True if within limits, False otherwise
    """
    # This is a simplified implementation
    # In production, implement proper rate limiting with Redis/database
    
    if action not in limits:
        return True
    
    max_count, time_window = limits[action]
    
    # For demo purposes, always allow (implement proper logic in production)
    logger.info(f"Rate limit check: {user_id} performing {action} (limit: {max_count}/{time_window}s)")
    return True


# Rate limiting configuration
DEFAULT_RATE_LIMITS = {
    'repo_clone': (5, 3600),  # 5 repo clones per hour
    'pdf_generate': (10, 3600),  # 10 PDF generations per hour
    'llm_call': (100, 3600),  # 100 LLM calls per hour
}