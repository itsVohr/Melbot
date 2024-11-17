from discord.ext import commands

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot, db):
        self.bot = bot
        self.db = db

    @commands.Cog.listener()
    async def on_message(self, message):
        print(type(message))
        print(message)

async def setup(bot: commands.Bot, db):
    await bot.add_cog(Events(bot=bot, db=db))