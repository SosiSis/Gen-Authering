# utils/logging_config.py
import logging
import logging.handlers
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
import traceback


class SecurityAuditLogger:
    """Logger for security-related events"""
    
    def __init__(self, log_file: str = "logs/security_audit.log"):
        self.logger = logging.getLogger("security_audit")
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # File handler for security events
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        
        # JSON formatter for structured logging
        formatter = JsonFormatter()
        file_handler.setFormatter(formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
    
    def log_validation_error(self, error: str, user_input: str, user_id: Optional[str] = None):
        """Log validation errors"""
        self.logger.warning("validation_error", extra={
            "event_type": "validation_error",
            "error": error,
            "user_input_preview": user_input[:100] + "..." if len(user_input) > 100 else user_input,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_security_violation(self, violation: str, details: Dict[str, Any], user_id: Optional[str] = None):
        """Log security violations"""
        self.logger.error("security_violation", extra={
            "event_type": "security_violation",
            "violation": violation,
            "details": details,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_rate_limit_exceeded(self, action: str, user_id: str):
        """Log rate limit violations"""
        self.logger.warning("rate_limit_exceeded", extra={
            "event_type": "rate_limit_exceeded", 
            "action": action,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })


class SystemLogger:
    """Logger for system operations and errors"""
    
    def __init__(self, log_file: str = "logs/system.log"):
        self.logger = logging.getLogger("system")
        self.logger.setLevel(logging.INFO)
        
        # Create logs directory
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # File handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=10
        )
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        
        # Formatters
        file_formatter = JsonFormatter()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)
        
        if not self.logger.handlers:
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
    
    def log_agent_execution(self, agent_name: str, conversation_id: str, 
                           execution_time: float, success: bool, error: Optional[str] = None):
        """Log agent execution details"""
        level = logging.INFO if success else logging.ERROR
        self.logger.log(level, "agent_execution", extra={
            "event_type": "agent_execution",
            "agent_name": agent_name,
            "conversation_id": conversation_id,
            "execution_time_ms": round(execution_time * 1000, 2),
            "success": success,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_llm_call(self, model: str, tokens_used: int, cost: float, 
                     response_time: float, conversation_id: str):
        """Log LLM API calls for monitoring and billing"""
        self.logger.info("llm_call", extra={
            "event_type": "llm_call",
            "model": model,
            "tokens_used": tokens_used,
            "estimated_cost_usd": cost,
            "response_time_ms": round(response_time * 1000, 2),
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_external_api_call(self, service: str, endpoint: str, 
                             response_code: int, response_time: float):
        """Log external API calls"""
        level = logging.INFO if 200 <= response_code < 300 else logging.WARNING
        self.logger.log(level, "external_api_call", extra={
            "event_type": "external_api_call",
            "service": service,
            "endpoint": endpoint,
            "response_code": response_code,
            "response_time_ms": round(response_time * 1000, 2),
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def log_error(self, error: Exception, context: Dict[str, Any]):
        """Log errors with full context"""
        self.logger.error("system_error", extra={
            "event_type": "system_error",
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context,
            "timestamp": datetime.utcnow().isoformat()
        })


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields if present
        if hasattr(record, 'event_type'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                              'pathname', 'filename', 'module', 'lineno', 
                              'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process',
                              'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


# Global logger instances
security_logger = SecurityAuditLogger()
system_logger = SystemLogger()


def setup_logging(log_level: str = "INFO"):
    """Setup application-wide logging configuration"""
    
    # Set root logger level
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))
    
    # Disable noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("git").setLevel(logging.WARNING)
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    system_logger.logger.info("logging_initialized", extra={
        "event_type": "system_startup",
        "log_level": log_level,
        "timestamp": datetime.utcnow().isoformat()
    })