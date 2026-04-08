import random
from characters import _BASE, _PROMPTS, _MENU_DESCS, _SCENARIOS

class SystemPrompts:
    """loads and serves character prompt data from characters.py"""

    def get_system_prompt(self, character) -> str:
        """returns the full system prompt: character-specific + base rules"""
        return _PROMPTS.get(character, "") + _BASE

    def get_char_prompt(self, character) -> str:
        """returns just the character-specific prompt without base"""
        return _PROMPTS.get(character, "")

    def get_scenario(self, character) -> str:
        """returns the opening scenario text. picks randomly if the character has multiple."""
        result = _SCENARIOS.get(character, "")
        if isinstance(result, list):
            return random.choice(result)
        return result

    def get_menu_desc(self, character) -> str:
        """returns the short description shown in the character selection menu"""
        return _MENU_DESCS.get(character, "")
