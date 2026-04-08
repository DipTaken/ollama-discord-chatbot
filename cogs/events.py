import os
import json
import discord
from discord.ext import commands

import config
from services.context import get_active_persona, context_file_path, trim_last_exchange
from services.appearance import apply_character_appearance
from services.ai import run_ai_streaming


class Events(commands.Cog):
    """event listeners — handles bot startup, incoming messages, and reaction controls"""

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """syncs slash commands and restores any sessions that were active before a restart"""
        await self.bot.tree.sync()
        print(f'{self.bot.user} has connected to Discord!')

        #scan metadata files to rebuild active_sessions from disk
        if os.path.exists("data"):
            for filename in os.listdir("data"):
                if not filename.endswith("_metadata.json"):
                    continue
                user_id = int(filename.split("_")[0])
                with open(f"data/{filename}", "r") as f:
                    meta = json.load(f)
                active_persona = meta.get("active_persona")
                channels = meta.get("channels", {})
                if active_persona and active_persona in channels:
                    channel = self.bot.get_channel(channels[active_persona])
                    if channel:
                        config.active_sessions[user_id] = channel.id
                        await apply_character_appearance(self.bot, channel.guild, active_persona)

        print(f"[Restored {len(config.active_sessions)} active session(s)]")

    @commands.Cog.listener()
    async def on_message(self, message):
        """routes user messages in active session channels to the ai"""
        if message.author == self.bot.user:
            return

        #ignore messages outside of active session channels
        is_session_channel = any(
            channel_id == message.channel.id
            for channel_id in config.active_sessions.values()
        )
        if not is_session_channel:
            return

        #ignore empty messages (attachments only, whitespace, etc.)
        if not message.content.strip():
            return

        await run_ai_streaming(message, self.bot)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """handles reaction-based controls on bot messages:
        🔄 regen — rewrites the response with escalating temperature
        ▶️ continue — extends the response without saving the continue prompt
        ⬅️ back — deletes the last exchange and removes it from context"""

        if payload.user_id == self.bot.user.id:
            return

        #only respond to reactions in active session channels
        if payload.channel_id not in config.active_sessions.values():
            return

        channel = self.bot.get_channel(payload.channel_id)
        if channel is None:
            return
        try:
            bot_message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        #--- REGEN (🔄) ---
        if str(payload.emoji) == "\U0001f504":
            if bot_message.reference and bot_message.reference.message_id:
                try:
                    user_message = await channel.fetch_message(bot_message.reference.message_id)
                except discord.NotFound:
                    return

                #only the original author can regen
                if payload.user_id != user_message.author.id:
                    return

                user_id = user_message.author.id
                persona = get_active_persona(user_id)
                file_path = context_file_path(user_id, persona)
                trim_last_exchange(file_path)

                await bot_message.edit(content="*Regenerating...*")
                await bot_message.clear_reactions()

                #track regen count per message and escalate temperature
                count = config.regen_counts.get(bot_message.id, 0) + 1
                config.regen_counts[bot_message.id] = count
                #cap the dict at 200 entries to avoid unbounded growth
                if len(config.regen_counts) > 200:
                    config.regen_counts.pop(next(iter(config.regen_counts)))
                temperature = config.REGEN_TEMPS[min(count, len(config.REGEN_TEMPS) - 1)]

                await run_ai_streaming(user_message, self.bot, existing_msg=bot_message, temperature=temperature)

        #--- CONTINUE (▶️) ---
        elif str(payload.emoji) == "\u25b6\ufe0f":
            if bot_message.reference and bot_message.reference.message_id:
                try:
                    user_message = await channel.fetch_message(bot_message.reference.message_id)
                except discord.NotFound:
                    return

                if payload.user_id != user_message.author.id:
                    return

                #override_content tells the model to extend, but isn't saved to context
                await run_ai_streaming(
                    user_message, self.bot,
                    temperature=0.8,
                    override_content="[Continue the scene from exactly where you left off. Extend naturally \u2014 do not repeat anything already said.]"
                )

        #--- BACK (⬅️) ---
        elif str(payload.emoji) == "\u2b05\ufe0f":
            if bot_message.reference and bot_message.reference.message_id:
                try:
                    user_message = await channel.fetch_message(bot_message.reference.message_id)
                except discord.NotFound:
                    return

                if payload.user_id != user_message.author.id:
                    return

                #remove the last exchange from context, then delete both messages
                user_id = user_message.author.id
                persona = get_active_persona(user_id)
                file_path = context_file_path(user_id, persona)
                trim_last_exchange(file_path)

                try:
                    await bot_message.delete()
                    await user_message.delete()
                except discord.Forbidden:
                    print("Missing 'Manage Messages' permission to delete user messages.")
                except discord.NotFound:
                    pass


async def setup(bot):
    """called by bot.load_extension() to register this cog"""
    await bot.add_cog(Events(bot))
