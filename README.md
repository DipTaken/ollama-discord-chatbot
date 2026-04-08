# LLM-Powered Character Discord Bot

An advanced, stateful Discord bot powered by **Ollama**, designed for private fiction and roleplay. This bot features persistent memory, recursive context summarization, and fine-grained control over AI behavior to maintain long-term narrative coherence.

## Technical Architecture

### 1. Advanced Context Management
The bot implements a custom sliding-window summarization system to handle the inherent token limits of local LLMs:
* **Threshold Monitoring**: Usage is tracked in real-time, triggering a compression cycle when the context reaches 75% of the total 16,384 token limit.
* **Sliding-Window Logic**: To maintain the immediate flow of conversation, the system preserves the most recent 40% of the history as raw tokens while summarizing the older 60% into a persistent narrative recap.
* **Persistent Storage**: Every user-character pair is isolated into a dedicated JSON context file, ensuring that conversations remain private and persistent across bot restarts.

### 2. High-Performance UX and Streaming
The implementation prioritizes a responsive user experience despite the high computational cost of local inference:
* **Token Streaming**: The bot live-edits Discord messages as tokens are generated, updating every 1.5 seconds or on newlines to bypass rate limits while providing immediate feedback.
* **Reaction-Based Controls**: Every bot response includes a set of interactive controls:
    * **🔄 Regen**: Rewrites the last response with escalating temperature if the output is unsatisfactory.
    * **▶️ Continue**: Prompts the AI to extend the current scene without injecting user-prompt bloat into the context.
    * **⬅️ Back**: Deletes the last exchange from both the Discord channel and the underlying JSON context file.

### 3. Systems Integration
* **AsyncIO and Modular Cogs**: Built on a modular architecture using Discord.py cogs to separate commands, event listeners, and background tasks.
* **Dynamic Character Appearance**: The bot utilizes an appearance service that dynamically updates its global nickname and avatar to match the active persona, including rate-limit protection for API calls.
* **OOC Injection**: Supports Out-Of-Character (OOC) instructions that are injected as system messages. These are visible to the model as narrative directions but remain hidden from the chat transcript.

## Commands

| Command | Description |
| :--- | :--- |
| /start | Opens character selection and creates a private session channel. |
| /stop | Ends the current session and deletes the channel while saving history. |
| /reset | Wipes the current history file to start a scene from the beginning. |
| /recap | Generates a structured summary of the story events and current state. |
| /status | Displays a visual progress bar of current context usage and token counts. |
| /temperature | Sets the creativity level (0.1 - 2.0) for the specific user session. |
| /mood_indicators | Toggles visible meters for parsed AI state tags (e.g., mood). |

## Project Structure

* **main.py**: The entry point that initializes the bot and loads the async cogs.
* **config.py**: Centralized configuration for model selection (Llama 3.1), token limits, and mutable state.
* **services/ai.py**: Core logic for Ollama API interaction, token streaming, and the summarization engine.
* **services/context.py**: Utility functions for JSON I/O and token estimation.
* **services/views.py**: Manages the interactive UI components for character selection and session creation.

## Requirements

* **Ollama**: Must be running locally with the model specified in config.py.
* **Discord.py**: Utilized for the bot framework and interactive components.
* **Assets**: Character-specific images must be placed in the assets directory to enable dynamic avatar switching.
