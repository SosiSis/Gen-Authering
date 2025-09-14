# mcp.py
import time, uuid
from typing import Any, Dict

def create_mcp_message(role: str, name: str, content: Dict[str, Any], conversation_id: str = None):
    return {
        "type": "message",
        "role": role,            # "agent" | "user" | "system"
        "name": name,            # agent name
        "content": content,      # structured payload
        "metadata": {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "conversation_id": conversation_id or str(uuid.uuid4())
        }
    }

def get_conversation_id(msg):
    return msg.get("metadata", {}).get("conversation_id")
