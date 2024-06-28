import discord
import os
import dotenv
from discord.ext import commands

dotenv.load_dotenv()

# bot initial setup
intents = discord.Intents.default()
intents.message_content = True
discord_token = os.environ['DISCORD_TOKEN']
bot = commands.Bot(command_prefix='!', intents=intents)

# bot events
#TODO

# run the bot
bot.run(discord_token)