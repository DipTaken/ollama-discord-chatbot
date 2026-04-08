import os
import asyncio
from dotenv import load_dotenv
from discord.ext import commands
import discord

load_dotenv()  #loads .env before anything else imports config

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


async def main():
    """entry point — loads cogs and starts the bot"""
    async with bot:
        await bot.load_extension("cogs.commands")  #slash commands
        await bot.load_extension("cogs.events")    #event listeners
        await bot.start(os.getenv("DISCORD_TOKEN"))


asyncio.run(main())
