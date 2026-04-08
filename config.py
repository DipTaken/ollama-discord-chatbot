import os

#model and context settings
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

NUM_CTX = 16384
REGEN_OFFSETS = [0.0, 0.075, 0.2, 0.3, 0.45]  #added to session temp on each regen, capped at 2.0
SUMMARIZE_AT = int(NUM_CTX * 0.75)   #trigger summarization at 75% context usage
TARGET_TOKENS = int(NUM_CTX * 0.40)  #compress down to 40% after summarizing

#shared mutable state — imported by other modules
active_sessions = {}        #{user_id: channel_id}
regen_counts = {}           #{bot_message_id: regen_count}
current_avatar = None       #which character's avatar is currently loaded (avoids redundant api calls)
session_temperatures = {}   #{user_id: float} — per-session temperature override

DEFAULT_TEMPERATURE = 0.8
