import os
import json
from prompts import SystemPrompts


def get_active_persona(user_id) -> str:
    """reads the user's metadata file and returns their currently selected character"""
    meta_path = f"data/{user_id}_metadata.json"
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            return json.load(f).get("active_persona", "").lower()
    return ""


def load_context(user_id, persona) -> list:
    """loads the conversation context from disk, or creates a fresh one with the system prompt"""
    file_path = f"data/{user_id}_{persona}_context.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    #no history yet — start with just the system prompt
    return [{"role": "system", "content": SystemPrompts().get_system_prompt(persona)}]


def save_context(user_id, persona, context: list):
    """writes the conversation context to disk"""
    os.makedirs("data", exist_ok=True)
    file_path = f"data/{user_id}_{persona}_context.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=4)


def context_file_path(user_id, persona) -> str:
    """returns the file path for a user's character context"""
    return f"data/{user_id}_{persona}_context.json"


def trim_last_exchange(file_path):
    """removes the last user+assistant exchange from context. used by regen and back."""
    if not os.path.exists(file_path):
        return
    with open(file_path, "r", encoding="utf-8") as f:
        context = json.load(f)
    #pop assistant first, then user — they're always paired at the end
    if len(context) > 1 and context[-1].get('role') == 'assistant':
        context.pop()
    if len(context) > 1 and context[-1].get('role') == 'user':
        context.pop()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(context, f, indent=4)


def estimate_tokens(messages: list) -> int:
    """rough token count — approximately 4 characters per token"""
    return sum(len(m.get("content", "")) for m in messages) // 4
