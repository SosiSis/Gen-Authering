# config/environment.py
"""
Production environment configuration with validation and security
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from dotenv import load_dotenv
import logging

from utils.validation import ValidationError

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Database configuration settings"""
    host: str = "localhost"
    port: int = 5432
    name: str = "multiagent"
    user: str = "multiagent_user"
    password: str = ""
    ssl_mode: str = "require"
    connection_timeout: int = 30
    max_connections: int = 20


@dataclass
class LLMConfig:
    """Language model configuration"""
    provider: str = "groq"
    api_key: str = ""
    model: str = "llama-3.3-70b-versatile"
    fallback_models: List[str] = field(default_factory=lambda: [
        "llama-3.1-70b-versatile", 
        "mixtral-8x7b-32768", 
        "gemma-7b-it"
    ])
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout: int = 120
    max_retries: int = 3
    rate_limit_rpm: int = 100


@dataclass
class SecurityConfig:
    """Security configuration settings"""
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    allowed_origins: List[str] = field(default_factory=lambda: ["localhost", "127.0.0.1"])
    max_file_size_mb: int = 100
    max_repo_size_mb: int = 500
    session_timeout_minutes: int = 60
    rate_limit_per_hour: int = 1000
    enable_ssl: bool = True
    ssl_cert_path: str = ""
    ssl_key_path: str = ""


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: str = "logs"
    max_file_size_mb: int = 10
    backup_count: int = 5
    enable_console: bool = True
    enable_file: bool = True
    enable_json: bool = True


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration"""
    enable_metrics: bool = True
    metrics_port: int = 9090
    enable_tracing: bool = False
    jaeger_endpoint: str = ""
    enable_health_checks: bool = True
    health_check_interval: int = 30


@dataclass
class ApplicationConfig:
    """Main application configuration"""
    # Environment
    environment: str = "development"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8501
    
    # Directories
    data_dir: str = "data"
    output_dir: str = "output"
    temp_dir: str = "tmp"
    logs_dir: str = "logs"
    
    # Component configs
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    # Feature flags
    enable_caching: bool = True
    enable_rate_limiting: bool = True
    enable_audit_logging: bool = True
    enable_user_analytics: bool = False


class ConfigurationManager:
    """Manages application configuration with validation and security"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or ".env"
        self.config = ApplicationConfig()
        self._load_configuration()
        self._validate_configuration()
        self._setup_directories()
    
    def _load_configuration(self):
        """Load configuration from environment and files"""
        # Load from .env file
        if os.path.exists(self.config_file):
            load_dotenv(self.config_file)
            logger.info(f"Loaded configuration from {self.config_file}")
        
        # Environment-specific overrides
        env = os.getenv("ENVIRONMENT", "development").lower()
        self.config.environment = env
        
        # Load environment variables
        self._load_from_environment()
        
        # Load environment-specific configs
        env_config_file = f".env.{env}"
        if os.path.exists(env_config_file):
            load_dotenv(env_config_file, override=True)
            self._load_from_environment()
            logger.info(f"Loaded environment-specific config from {env_config_file}")
    
    def _load_from_environment(self):
        """Load configuration values from environment variables"""
        # Application settings
        self.config.debug = self._get_bool("DEBUG", self.config.debug)
        self.config.host = os.getenv("HOST", self.config.host)
        self.config.port = self._get_int("PORT", self.config.port)
        
        # Directories
        self.config.data_dir = os.getenv("DATA_DIR", self.config.data_dir)
        self.config.output_dir = os.getenv("OUTPUT_DIR", self.config.output_dir)
        self.config.temp_dir = os.getenv("TEMP_DIR", self.config.temp_dir)
        self.config.logs_dir = os.getenv("LOGS_DIR", self.config.logs_dir)
        
        # LLM configuration
        self.config.llm.api_key = os.getenv("GROQ_API_KEY", "")
        self.config.llm.model = os.getenv("LLM_MODEL", self.config.llm.model)
        self.config.llm.temperature = self._get_float("LLM_TEMPERATURE", self.config.llm.temperature)
        self.config.llm.max_tokens = self._get_int("LLM_MAX_TOKENS", self.config.llm.max_tokens)
        self.config.llm.timeout = self._get_int("LLM_TIMEOUT", self.config.llm.timeout)
        
        # Security configuration
        self.config.security.secret_key = os.getenv("SECRET_KEY", self.config.security.secret_key)
        self.config.security.max_file_size_mb = self._get_int("MAX_FILE_SIZE_MB", self.config.security.max_file_size_mb)
        self.config.security.enable_ssl = self._get_bool("ENABLE_SSL", self.config.security.enable_ssl)
        
        # Logging configuration
        self.config.logging.level = os.getenv("LOG_LEVEL", self.config.logging.level)
        self.config.logging.log_dir = os.getenv("LOG_DIR", self.config.logging.log_dir)
        
        # Feature flags
        self.config.enable_caching = self._get_bool("ENABLE_CACHING", self.config.enable_caching)
        self.config.enable_rate_limiting = self._get_bool("ENABLE_RATE_LIMITING", self.config.enable_rate_limiting)
        self.config.enable_audit_logging = self._get_bool("ENABLE_AUDIT_LOGGING", self.config.enable_audit_logging)
    
    def _validate_configuration(self):
        """Validate configuration values and constraints"""
        errors = []
        
        # Validate LLM configuration
        if not self.config.llm.api_key:
            errors.append("GROQ_API_KEY is required")
        
        if not 0 <= self.config.llm.temperature <= 2:
            errors.append("LLM temperature must be between 0 and 2")
        
        if not 1 <= self.config.llm.max_tokens <= 4000:
            errors.append("LLM max_tokens must be between 1 and 4000")
        
        # Validate network configuration
        if not 1024 <= self.config.port <= 65535:
            errors.append("Port must be between 1024 and 65535")
        
        # Validate security configuration
        if self.config.environment == "production":
            if not self.config.security.secret_key:
                errors.append("SECRET_KEY is required in production")
            
            if len(self.config.security.secret_key) < 32:
                errors.append("SECRET_KEY must be at least 32 characters in production")
            
            if self.config.debug:
                errors.append("DEBUG must be False in production")
        
        # Validate file size limits
        if self.config.security.max_file_size_mb <= 0:
            errors.append("Max file size must be positive")
        
        if self.config.security.max_repo_size_mb <= 0:
            errors.append("Max repository size must be positive")
        
        # Validate logging configuration
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.config.logging.level.upper() not in valid_log_levels:
            errors.append(f"Log level must be one of: {valid_log_levels}")
        
        if errors:
            raise ValidationError(f"Configuration validation failed: {'; '.join(errors)}")
        
        logger.info("Configuration validation successful")
    
    def _setup_directories(self):
        """Create required directories"""
        directories = [
            self.config.data_dir,
            self.config.output_dir,
            self.config.temp_dir,
            self.config.logs_dir
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created directories: {directories}")
    
    def _get_bool(self, key: str, default: bool) -> bool:
        """Get boolean value from environment"""
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    def _get_int(self, key: str, default: int) -> int:
        """Get integer value from environment"""
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            logger.warning(f"Invalid integer value for {key}, using default: {default}")
            return default
    
    def _get_float(self, key: str, default: float) -> float:
        """Get float value from environment"""
        try:
            return float(os.getenv(key, str(default)))
        except ValueError:
            logger.warning(f"Invalid float value for {key}, using default: {default}")
            return default
    
    def get_config(self) -> ApplicationConfig:
        """Get the application configuration"""
        return self.config
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.config.environment == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.config.environment == "development"
    
    def export_config(self, include_sensitive: bool = False) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        config_dict = {
            "environment": self.config.environment,
            "debug": self.config.debug,
            "host": self.config.host,
            "port": self.config.port,
            "directories": {
                "data": self.config.data_dir,
                "output": self.config.output_dir,
                "temp": self.config.temp_dir,
                "logs": self.config.logs_dir
            },
            "llm": {
                "provider": self.config.llm.provider,
                "model": self.config.llm.model,
                "temperature": self.config.llm.temperature,
                "max_tokens": self.config.llm.max_tokens,
                "timeout": self.config.llm.timeout
            },
            "features": {
                "caching": self.config.enable_caching,
                "rate_limiting": self.config.enable_rate_limiting,
                "audit_logging": self.config.enable_audit_logging
            }
        }
        
        if include_sensitive:
            config_dict["llm"]["api_key"] = self.config.llm.api_key[:10] + "..." if self.config.llm.api_key else ""
            config_dict["security"] = {
                "secret_key": "***REDACTED***" if self.config.security.secret_key else "",
                "max_file_size_mb": self.config.security.max_file_size_mb,
                "enable_ssl": self.config.security.enable_ssl
            }
        
        return config_dict


# Global configuration instance
_config_manager: Optional[ConfigurationManager] = None


def get_config() -> ApplicationConfig:
    """Get the global application configuration"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager.get_config()


def initialize_config(config_file: Optional[str] = None) -> ConfigurationManager:
    """Initialize the global configuration manager"""
    global _config_manager
    _config_manager = ConfigurationManager(config_file)
    return _config_manager


def is_production() -> bool:
    """Check if running in production environment"""
    return get_config().environment == "production"


def is_development() -> bool:
    """Check if running in development environment"""
    return get_config().environment == "development"