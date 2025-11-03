# tools/llm_tool_groq.py
import os
import time
from typing import List, Dict, Any, Optional
from groq import Groq
from dotenv import load_dotenv

from utils.resilience import retry_with_backoff, llm_circuit_breaker, RetryStrategy
from utils.logging_config import system_logger
from utils.validation import sanitize_user_input

# Load environment variables from .env file
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", None)
if not GROQ_API_KEY:
    raise EnvironmentError("Set GROQ_API_KEY env var")

def get_groq_client():
    return Groq(api_key=GROQ_API_KEY)

@llm_circuit_breaker
@retry_with_backoff(
    max_attempts=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=2.0,
    max_delay=30.0,
    exceptions=(Exception,),
    timeout=120.0
)
def groq_chat(messages: List[dict], model="llama-3.3-70b-versatile", 
              temperature: float = 0.2, max_tokens: int = 800,
              conversation_id: Optional[str] = None) -> str:
    """
    Enhanced Groq chat with resilience, validation, and monitoring
    
    Args:
        messages: list of {"role": "user"/"system"/"assistant", "content": "..."}
        model: Model name to use
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        conversation_id: Optional conversation ID for logging
        
    Returns:
        Generated text string
        
    Raises:
        ValueError: If input validation fails
        Exception: If all retry attempts fail
    """
    start_time = time.time()
    
    # Validate and sanitize messages
    validated_messages = []
    for msg in messages:
        if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
            raise ValueError("Invalid message format. Must have 'role' and 'content' fields")
        
        if msg['role'] not in ['system', 'user', 'assistant']:
            raise ValueError(f"Invalid role: {msg['role']}")
        
        # Sanitize content
        sanitized_content = sanitize_user_input(msg['content'])
        validated_messages.append({
            'role': msg['role'],
            'content': sanitized_content
        })
    
    # Validate parameters
    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise ValueError("Temperature must be between 0 and 2")
    
    if not isinstance(max_tokens, int) or max_tokens <= 0 or max_tokens > 4000:
        raise ValueError("max_tokens must be between 1 and 4000")
    
    client = get_groq_client()
    
    try:
        # Make the API call
        resp = client.chat.completions.create(
            model=model,
            messages=validated_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        result = resp.choices[0].message.content
        response_time = time.time() - start_time
        
        # Log successful call
        system_logger.log_llm_call(
            model=model,
            tokens_used=resp.usage.total_tokens if hasattr(resp, 'usage') else max_tokens,
            cost=0.0,  # Calculate based on model pricing
            response_time=response_time,
            conversation_id=conversation_id or "unknown"
        )
        
        return result
        
    except Exception as e:
        response_time = time.time() - start_time
        
        # Log the error
        system_logger.log_error(e, {
            "function": "groq_chat",
            "model": model,
            "response_time": response_time,
            "conversation_id": conversation_id,
            "message_count": len(validated_messages)
        })
        
        # Try fallback models
        fallback_models = ["llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma-7b-it"]
        if model not in fallback_models:
            for fallback_model in fallback_models:
                try:
                    system_logger.logger.info("llm_fallback", extra={
                        "event_type": "llm_fallback",
                        "original_model": model,
                        "fallback_model": fallback_model,
                        "conversation_id": conversation_id
                    })
                    
                    resp = client.chat.completions.create(
                        model=fallback_model,
                        messages=validated_messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    
                    return resp.choices[0].message.content
                    
                except Exception as fallback_error:
                    system_logger.logger.warning("llm_fallback_failed", extra={
                        "event_type": "llm_fallback_failed",
                        "fallback_model": fallback_model,
                        "error": str(fallback_error),
                        "conversation_id": conversation_id
                    })
                    continue
        
        # All models failed, re-raise the original exception
        raise e

def summarize_text_for_academic(text: str) -> str:
    prompt = [
        {"role": "system", "content": "You are an assistant that summarizes technical repositories into academic sections."},
        {"role": "user", "content": f"Summarize the important contributions and write an academic abstract for the following content:\n\n{text}"}
    ]
    try:
        return groq_chat(prompt)
    except Exception as e:
        print(f"Error in summarize_text_for_academic: {e}")
        return f"# Academic Summary\n\nThis repository contains technical contributions that could not be fully analyzed due to API limitations. Please review the original repository for detailed information.\n\nContent preview: {text[:500]}..."
