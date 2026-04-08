import os
import discord
import config


async def apply_character_appearance(bot, guild: discord.Guild, persona: str):
    """updates the bot's nickname and avatar to match the active character.
    nickname changes every time, but avatar only changes if it's different
    from what's currently loaded — discord rate-limits avatar changes heavily (~2/10min)."""

    try:
        await guild.me.edit(nick=persona.capitalize())
    except discord.Forbidden:
        print(f"[Appearance] Missing permission to change nickname.")

    #only upload a new avatar if we're switching to a different character
    avatar_path = f"assets/{persona}.jpg"
    if os.path.exists(avatar_path) and config.current_avatar != persona:
        try:
            with open(avatar_path, "rb") as f:
                await bot.user.edit(avatar=f.read())
            config.current_avatar = persona
        except discord.HTTPException as e:
            print(f"[Appearance] Avatar change failed (likely rate limited): {e}")
