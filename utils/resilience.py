# utils/resilience.py
import time
import random
import functools
from typing import Callable, Any, Optional, Dict, List, Union
import logging
from enum import Enum

from .logging_config import system_logger

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy options"""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"


class CircuitBreakerState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class TimeoutError(Exception):
    """Raised when operation times out"""
    pass


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


def retry_with_backoff(
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    timeout: Optional[float] = None
):
    """
    Decorator for retrying functions with configurable backoff strategies
    
    Args:
        max_attempts: Maximum number of retry attempts
        strategy: Retry strategy to use
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        jitter: Add random jitter to delays
        exceptions: Tuple of exceptions to retry on
        timeout: Optional timeout in seconds for the entire operation
    """
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            last_exception = None
            
            for attempt in range(max_attempts):
                # Check timeout
                if timeout and (time.time() - start_time) > timeout:
                    system_logger.log_error(
                        TimeoutError(f"Operation timed out after {timeout}s"),
                        {"function": func.__name__, "attempt": attempt + 1}
                    )
                    raise TimeoutError(f"Operation timed out after {timeout} seconds")
                
                try:
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Log successful retry if we had previous failures
                    if attempt > 0:
                        system_logger.logger.info("retry_success", extra={
                            "event_type": "retry_success",
                            "function": func.__name__,
                            "attempt": attempt + 1,
                            "total_time": time.time() - start_time
                        })
                    
                    return result
                
                except exceptions as e:
                    last_exception = e
                    
                    # Don't wait after the last attempt
                    if attempt == max_attempts - 1:
                        break
                    
                    # Calculate delay
                    delay = _calculate_delay(strategy, attempt, base_delay, max_delay, jitter)
                    
                    # Log retry attempt
                    system_logger.logger.warning("retry_attempt", extra={
                        "event_type": "retry_attempt",
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "error": str(e),
                        "delay": delay
                    })
                    
                    time.sleep(delay)
                
                except Exception as e:
                    # Don't retry on unexpected exceptions
                    system_logger.log_error(e, {
                        "function": func.__name__,
                        "attempt": attempt + 1,
                        "retry_failed": True
                    })
                    raise
            
            # All retries exhausted
            system_logger.log_error(last_exception, {
                "function": func.__name__,
                "max_attempts_reached": True,
                "total_time": time.time() - start_time
            })
            
            raise last_exception
        
        return wrapper
    return decorator


def _calculate_delay(strategy: RetryStrategy, attempt: int, base_delay: float, 
                    max_delay: float, jitter: bool) -> float:
    """Calculate delay based on strategy"""
    
    if strategy == RetryStrategy.FIXED_DELAY:
        delay = base_delay
    elif strategy == RetryStrategy.LINEAR_BACKOFF:
        delay = base_delay * (attempt + 1)
    elif strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        delay = base_delay * (2 ** attempt)
    else:
        delay = base_delay
    
    # Apply maximum delay
    delay = min(delay, max_delay)
    
    # Add jitter to avoid thundering herd
    if jitter:
        delay = delay * (0.5 + random.random() * 0.5)
    
    return delay


class CircuitBreaker:
    """Circuit breaker pattern implementation"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: tuple = (Exception,)
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
    
    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self._call(func, *args, **kwargs)
        return wrapper
    
    def _call(self, func: Callable, *args, **kwargs) -> Any:
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                system_logger.logger.info("circuit_breaker_half_open", extra={
                    "event_type": "circuit_breaker_state_change",
                    "function": func.__name__,
                    "state": "half_open"
                })
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is open for {func.__name__}"
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success(func)
            return result
        
        except self.expected_exception as e:
            self._on_failure(func, e)
            raise
    
    def _should_attempt_reset(self) -> bool:
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self, func: Callable):
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            system_logger.logger.info("circuit_breaker_closed", extra={
                "event_type": "circuit_breaker_state_change",
                "function": func.__name__,
                "state": "closed"
            })
        
        self.failure_count = 0
    
    def _on_failure(self, func: Callable, exception: Exception):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            system_logger.logger.error("circuit_breaker_opened", extra={
                "event_type": "circuit_breaker_state_change",
                "function": func.__name__,
                "state": "open",
                "failure_count": self.failure_count,
                "error": str(exception)
            })


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, max_tokens: int, refill_rate: float):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = max_tokens
        self.last_refill = time.time()
    
    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens"""
        now = time.time()
        
        # Refill tokens
        time_passed = now - self.last_refill
        self.tokens = min(
            self.max_tokens,
            self.tokens + (time_passed * self.refill_rate)
        )
        self.last_refill = now
        
        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False


def with_timeout(timeout_seconds: float):
    """Decorator to add timeout to functions"""
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds} seconds")
            
            # Set the signal handler
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout_seconds))
            
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                # Restore the old handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
        
        return wrapper
    return decorator


def limit_execution_time(max_iterations: int = 1000):
    """Decorator to limit loop iterations and prevent infinite loops"""
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Store original builtins
            original_range = __builtins__.get('range') if isinstance(__builtins__, dict) else getattr(__builtins__, 'range')
            original_while = None  # While is a statement, not a function
            
            iteration_count = [0]  # Use list for mutable reference
            
            def limited_range(*range_args):
                """Limited range function"""
                for i, val in enumerate(original_range(*range_args)):
                    iteration_count[0] += 1
                    if iteration_count[0] > max_iterations:
                        raise RuntimeError(f"Maximum iterations ({max_iterations}) exceeded in {func.__name__}")
                    yield val
            
            # Replace range temporarily
            if isinstance(__builtins__, dict):
                __builtins__['range'] = limited_range
            else:
                setattr(__builtins__, 'range', limited_range)
            
            try:
                return func(*args, **kwargs)
            finally:
                # Restore original range
                if isinstance(__builtins__, dict):
                    __builtins__['range'] = original_range
                else:
                    setattr(__builtins__, 'range', original_range)
        
        return wrapper
    return decorator


# Predefined circuit breakers for different services
llm_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=30.0,
    expected_exception=(Exception,)
)

git_circuit_breaker = CircuitBreaker(
    failure_threshold=2,
    recovery_timeout=60.0,
    expected_exception=(Exception,)
)

pdf_circuit_breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=30.0,
    expected_exception=(Exception,)
)