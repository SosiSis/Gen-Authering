# tools/llm_tool_groq.py
import os
from typing import List
from groq import Groq
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", None)
if not GROQ_API_KEY:
    raise EnvironmentError("Set GROQ_API_KEY env var")

def get_groq_client():
    return Groq(api_key=GROQ_API_KEY)

def groq_chat(messages: List[dict], model="llama-3.3-70b-versatile", temperature: float = 0.2, max_tokens: int = 800):
    """
    messages: list of {"role": "user"/"system"/"assistant", "content": "..."}
    returns text string
    """
    client = get_groq_client()
    
    # Try with the primary model first
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    except Exception as e:
        print(f"Error with model {model}: {e}")
        
        # Try with a different model as fallback
        fallback_models = ["llama-3.1-70b-versatile", "mixtral-8x7b-32768", "gemma-7b-it"]
        for fallback_model in fallback_models:
            try:
                print(f"Trying fallback model: {fallback_model}")
                resp = client.chat.completions.create(
                    model=fallback_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content
            except Exception as fallback_error:
                print(f"Fallback model {fallback_model} also failed: {fallback_error}")
                continue
        
        # If all models fail, return a default response
        return f"Error: Unable to generate response. API Error: {str(e)}"

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
