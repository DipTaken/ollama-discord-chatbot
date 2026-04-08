import os
import json
import discord

import config
from prompts import SystemPrompts
from services.appearance import apply_character_appearance
from services.ai import send_opening


class CharacterButton(discord.ui.Button):
    """a single button in the character selection menu"""

    def __init__(self, char: str):
        super().__init__(label=char.capitalize(), style=discord.ButtonStyle.secondary)
        self.char = char

    async def callback(self, interaction: discord.Interaction):
        #only the user who opened the menu can pick
        if interaction.user.id != self.view.original_interaction.user.id:
            await interaction.response.send_message("This isn't your menu.", ephemeral=True)
            return
        self.view.selected_char = self.char
        await interaction.response.defer()
        self.view.stop()


class CharacterSelectView(discord.ui.View):
    """a row of buttons, one per character. times out after 60s."""

    def __init__(self, original_interaction: discord.Interaction, characters: list):
        super().__init__(timeout=60.0)
        self.selected_char = None
        self.original_interaction = original_interaction
        for char in characters:
            self.add_item(CharacterButton(char))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.original_interaction.edit_original_response(
                content="*Selection timed out.*", embed=None, view=self
            )
        except Exception:
            pass


async def select_and_open_character_channel(interaction: discord.Interaction, bot):
    """shows the character selection menu, waits for a pick, then either
    links to an existing channel or creates a new private one.
    if there's no prior history, sends the character's opening message."""

    from characters import _PROMPTS
    characters = list(_PROMPTS.keys())

    prompts = SystemPrompts()
    view = CharacterSelectView(interaction, characters)

    #build the menu embed with character descriptions
    embed = discord.Embed(title="Select a Character", color=discord.Color.dark_purple())
    embed.description = "\n".join(
        f"**{char.capitalize()}** \u2014 {prompts.get_menu_desc(char)}"
        for char in characters
        if prompts.get_menu_desc(char)
    )

    await interaction.response.send_message(embed=embed, view=view)

    #block until the user picks or it times out
    timed_out = await view.wait()
    if timed_out or view.selected_char is None:
        return

    selected_char = view.selected_char

    #disable buttons and show the character's image as confirmation
    for item in view.children:
        item.disabled = True

    avatar_path = f"assets/{selected_char}.jpg"
    if os.path.exists(avatar_path):
        file = discord.File(avatar_path, filename=f"{selected_char}.jpg")
        confirm_embed = discord.Embed(
            title=selected_char.capitalize(),
            color=discord.Color.green()
        )
        confirm_embed.set_image(url=f"attachment://{selected_char}.jpg")
        await interaction.edit_original_response(embed=confirm_embed, attachments=[file], view=view)
    else:
        await interaction.edit_original_response(
            content=f"**{selected_char.capitalize()}** selected.", embed=None, view=view
        )

    #load or create user metadata
    meta_path = f"data/{interaction.user.id}_metadata.json"
    os.makedirs("data", exist_ok=True)
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)

    meta["active_persona"] = selected_char
    await apply_character_appearance(bot, interaction.guild, selected_char)
    char_channels = meta.get("channels", {})

    #check if this character already has a channel from a previous session
    existing_channel = None
    saved_channel_id = char_channels.get(selected_char)
    if saved_channel_id:
        existing_channel = bot.get_channel(saved_channel_id)

    if existing_channel:
        config.active_sessions[interaction.user.id] = existing_channel.id
        await interaction.followup.send(
            f"**{selected_char.capitalize()}** already has a channel: {existing_channel.mention}"
        )
    else:
        #create a new private channel only visible to the user and the bot
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        new_channel = await interaction.guild.create_text_channel(
            name=f"chat-with-{selected_char}",
            overwrites=overwrites,
            topic=f"Private session with {selected_char.capitalize()} for {interaction.user.name}"
        )
        char_channels[selected_char] = new_channel.id
        meta["channels"] = char_channels
        config.active_sessions[interaction.user.id] = new_channel.id

        history_path = f"data/{interaction.user.id}_{selected_char}_context.json"
        has_history = os.path.exists(history_path)
        history_note = " Previous conversation history has been loaded." if has_history else ""
        await interaction.followup.send(
            f"Created channel for **{selected_char.capitalize()}**: {new_channel.mention}{history_note}"
        )

        #only generate an opening if this is a brand new conversation
        if not has_history:
            await send_opening(new_channel, interaction.user.id, selected_char)

    with open(meta_path, "w") as f:
        json.dump(meta, f)
