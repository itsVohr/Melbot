import os
import discord
import asyncio
import logging
from utils import gamba
from discord.ext import commands, tasks
from helpers.db_helper import DBHelper
from helpers.gdrive_helper import GDriveHelper
from datetime import datetime
from discord.errors import NotFound

class NotBotAdmin(commands.CheckFailure):
    pass

class SafeMember(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            return member
        except commands.MemberNotFound:
            logging.debug(f"Member conversion failed for {argument}.")
            message = await ctx.send(f"Cannot find user {argument}.")
            
            def check(m):
                return m.id == message.id and m.channel == ctx.channel

            try:
                await ctx.wait_for('message', check=check, timeout=5.0)
            except asyncio.TimeoutError:
                logging.info("Error message timed out.")
                pass
            
            raise commands.BadArgument(f'Member "{argument}" not found.')


class Melbot():
    def __init__(self, command_prefix:str='!'):
        self.db = DBHelper(os.environ['DB_NAME'])
        self.gdrive = GDriveHelper()
        self.discord_token = os.environ['DISCORD_TOKEN']
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.bot = commands.Bot(command_prefix=command_prefix, intents=self.intents)
        self.cooldowns = {"message": {}}

    async def initialize(self):
        await self.db.initialize()
        await self.db.create_db()

    async def run(self):
        logging.info("Initating Melbot...") 
        await self.initialize()
        await self.add_bot_events()
        await self.bot.start(self.discord_token)
        self.aggregate_points_task.cancel()

    def is_bot_admin(self):
        async def predicate(ctx):
            if ctx.author.id != int(os.environ['BOT_ADMIN_ID']):
                raise NotBotAdmin()
            return True
        return commands.check(predicate)

    def _file_in_drive(self, file_name):
        files = self.gdrive.get_files()
        for file in files:
            if file['name'] == file_name:
                return True
        return False

    @tasks.loop(hours=24)
    async def aggregate_points_task(self):
        cutoff_timestamp = datetime.now().timestamp() - 24 * 60 * 60
        await self.db.aggregate_points_async(cutoff_timestamp)
        logging.info("Aggregated points successfully.")


    @aggregate_points_task.before_loop
    async def before_aggregate_points_task(self):
        await self.bot.wait_until_ready()

    async def add_bot_events(self):
        # --- bot events ---
        @self.bot.event
        async def on_ready():
            self.aggregate_points_task.start()

        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            if not message.content.startswith(self.bot.command_prefix):
                current_time = datetime.now().timestamp()
                if message.author.id in self.cooldowns["message"]:
                    if current_time - self.cooldowns["message"][message.author.id] < 2:
                        return
                self.cooldowns["message"].update({message.author.id: current_time})
                await self.db.add_event(message.author.id, 1, 'message')
            if message.channel.id == int(os.environ['BOT_COMMANDS_CHANNEL_ID']):
                await self.bot.process_commands(message)

        # --- bot commands ---
        self.bot.remove_command('help')
        @self.bot.command(help="Display the help message.")
        async def help(ctx):
            embed = discord.Embed(title="Melbot Help", description="List of available commands")
            for command in self.bot.commands:
                can_run = True
                try:
                    await command.can_run(ctx)
                except (NotBotAdmin, commands.CommandError):
                    can_run = False
                if can_run:
                    embed.add_field(name=f"{self.bot.command_prefix}{command.name}", value=command.help or "No description", inline=False)
            await ctx.send(embed=embed)

        @self.bot.command(help="Display the total melpoints of a user. You can use !points @user to check another user's points.")
        async def points(ctx, user: SafeMember = None):
            if user is None:
                user = ctx.author
            user_id = str(user.id)
            total_currency = await self.db.get_total_currency(user_id)
            await ctx.send(f'{user.name} has {total_currency} points')

        @self.bot.command(help="Buy an item from the shop. You can use !buy item_id to buy an item by its ID, or !buy item_name to buy an item by its name.")
        async def buy(ctx, item_id = None):
            if item_id is None:
                await ctx.send("Please provide an item ID.")
                return
            
            user_id = str(ctx.author.id)
            try:
                item_id = int(item_id)
            except ValueError:
                logging.debug(f"Failed to convert {item_id} to int. {item_id} is of type {type(item_id)}")

            if type(item_id) == int:
                (item_price, item_file) = await self.db.buy_items_by_id(item_id)
            elif type(item_id) == str:
                (item_price, item_file) = await self.db.buy_items_by_name(item_id)
            else:
                await ctx.send("Wrong syntax, it should be like this '!buy 1', or '!buy gen'")
                return

            if item_price is None:
                await ctx.send("The item does not exist.")
                return
            
            if item_file == '':
                link_message = ''
            else:
                if not self._file_in_drive(item_file):
                    await ctx.send(f"Item {item_id} doesn't have a valid file. Please contact an admin.")
                    return
                file_list = self.gdrive.get_files()
                for file in file_list:
                    if file['name'] == item_file:
                        file_link = file['webViewLink']
                        break             
                link_message = f"\nYou can download the file [here]({file_link})."
                

            user_points = await self.db.get_total_currency(user_id)
            
            if user_points < item_price:
                await ctx.send(f"You do not have enough melpoints to buy this item. You have {user_points} melpoints but need {item_price}.")
                return

            await self.db.add_event(user_id, item_price * -1, f"bought item {item_id}")
            await ctx.send(f"You have successfully bought the item {item_id} for {item_price} melpoints.")
            shop_channel_id = await self.bot.fetch_channel(os.environ['SHOP_CHANNEL_ID'])
            await shop_channel_id.send(f"{ctx.author.mention} has bought the item {item_id} for {item_price} melpoints.")
            await ctx.author.send(f"You have successfully bought the item {item_id} for {item_price} melpoints."+link_message)

        @self.bot.command(help="Display the shop items.")
        async def shop(ctx):
            items = await self.db.get_shop_items()
            if len(items) == 0:
                await ctx.send("The shop is empty.")
                return
            embed = discord.Embed(title="Madamme Melanie's Shop", color=discord.Color.blue())
            for item in items:
                item_details = f"> **Item ID**: {item[0]}\n> **Price**: {item[2]} melpoints\n> **Description**: {item[3]}"
                embed.add_field(name=f"**{item[1]}**", value=item_details, inline=False)
            await ctx.send(embed=embed)

        @self.bot.command(help="Gamble your melpoints. You can use !gamble <number> to gamble a specific number of melpoints.")
        async def gamble(ctx, points: int|str):
            user_id = str(ctx.author.id)
            user_points = await self.db.get_total_currency(user_id)
            # Handle string inputs
            if type(points) == str:
                if points.lower() == 'all':
                    points = user_points
                elif points.lower() == 'half':
                    points = user_points // 2
                else:
                    await ctx.send("Wrong syntax, it should be like this '!gamble 100' or '!gamble all'")
                    return
            if points > user_points:
                await ctx.send(f"You do not have enough points to gamble {points} points. You have {user_points} points.")
                return
            if points < 0:
                await ctx.send("You cannot gamble a negative number of points.")
                return
            if points == 0:
                await ctx.send("You cannot gamble 0 points.")
                return
            if points > os.getenv('GAMBLE_LIMIT'):
                await ctx.send(f"You can't bet more than {os.getenv('GAMBLE_LIMIT')} points.")
                return
            earned_points = gamba(points)
            await self.db.add_event(user_id, earned_points - points, 'gamble')
            if earned_points == 0:
                await ctx.send(f"You lost {points} points.")
            else:
                await ctx.send(f"You won {earned_points} points.")

        @self.bot.command(help="Display the leaderboard.")
        async def leaderboard(ctx):
            leaderboard = await self.db.get_leaderboard()
            if len(leaderboard) == 0:
                await ctx.send("The leaderboard is empty.")
                return
            leaderboard_str = "Leaderboard:\n"
            for idx, user in enumerate(leaderboard):
                user_id = user[0]
                points = user[1]
                try:
                    member = await ctx.guild.fetch_member(int(user_id))
                    username = member.display_name
                except NotFound:
                    username = "User not found"
                leaderboard_str += f"{idx + 1}. {username}: {points}\n"
            await ctx.send(leaderboard_str)

        @self.bot.command(help="Display information about this bot.")
        async def about(ctx):
            embed = discord.Embed(
                title="About Melbot",
                description="Madamme Melanie's custom Discord bot ♥",
                color=0x3498db
            )
            embed.add_field(
                name="Author",
                value="[Vohr](https://x.com/itsvohr)",
                inline=False
            )
            embed.add_field(
                name="Version",
                value=os.environ['VERSION'],
                inline=False
            )
            embed.add_field(
                name="Source code",
                value="[GitHub Repo](https://github.com/itsVohr/Melbot)",
                inline=False
            )
            await ctx.send(embed=embed)

        # --- admin commands ---
        @self.bot.command(help='Add an item to the shop. You can use !add_item <item_name> <item_price> <"item description"> <optional:item_file> to add an item to the shop.')
        @self.is_bot_admin()
        async def add_item(ctx, item_name: str = None, item_price: int = None, item_description: str = None, item_file: str = None):
            if item_name is None or item_price is None or item_description is None:
                await ctx.send("Please provide an item name, price, and description.")
                return
            if type(item_price) != int or type(item_name) != str or type(item_description) != str:
                await ctx.send("Wrong syntax, it should be like this ""!add_item gen 500 \"nice gen\" mel.png")
                return
            if item_file is not None:
                if not self._file_in_drive(item_file):
                    await ctx.send(f"File {item_file} not found in Google Drive.")
                    return
            else:
                item_file = ''
            await self.db.add_item(item_name, item_price, item_description, item_file)
            await ctx.send(f"Item {item_name} added to the shop with price {item_price} points.")

        @self.bot.command(help="Add melpoints to a user's account. You can use !add @user <number> to add melpoints to a user's account.")
        @self.is_bot_admin()
        async def add(ctx, user: SafeMember, points: int):
            user_id = str(user.id)
            await self.db.add_event(user_id, points, 'admin added')
            await ctx.send(f"{points} points added to {user.name}'s account.")

        @self.bot.command(help="Remove an item from the shop. You can use !remove_item <item_id> to remove an item by its ID, or !remove_item <item_name> to remove an item by its name.")
        @self.is_bot_admin()
        async def remove_item(ctx, item_id: str):
            if item_id is None:
                await ctx.send("Please provide an item ID.")
                return
            try:
                item_id = int(item_id)
            except ValueError:
                logging.debug(f"Failed to convert {item_id} to int. {item_id} is of type {type(item_id)}")
            if type(item_id) == int:
                rows_deleted = await self.db.remove_item_by_id(item_id)
            elif type(item_id) == str:
                rows_deleted = await self.db.remove_item_by_name(item_id)
            else:
                await ctx.send("Wrong syntax, it should be like this '!remove_item 1' or '!remove_item gen'")
                return
            if rows_deleted == 0:
                await ctx.send(f"The item {item_id} does not exist.")
                return
            else:
                await ctx.send(f"Item with ID {item_id} removed from the shop.")

        @self.bot.command(help="Remove melpoints from a user's account. You can use !remove @user <number> to remove melpoints from a user's account.")
        @self.is_bot_admin()
        async def remove(ctx, user: SafeMember, points: int):
            user_id = str(user.id)
            await self.db.add_event(user_id, points * -1, 'admin removed')
            await ctx.send(f"{points} points removed from {user.name}'s account.")


