import os
import discord
import asyncio
import logging
from utils import gamba
from discord.ext import commands
from db_stuff.db_helper import DBHelper

class SafeMember(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            return member
        except commands.MemberNotFound:
            message = await ctx.send(f"Cannot find user {argument}.")
            
            def check(m):
                return m.id == message.id and m.channel == ctx.channel

            try:
                await ctx.wait_for('message', check=check, timeout=5.0)
            except asyncio.TimeoutError:
                pass
            
            raise commands.BadArgument(f'Member "{argument}" not found.')


class Melbot():
    def __init__(self, command_prefix:str='!'):
        self.discord_token = os.environ['DISCORD_TOKEN']
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.bot = commands.Bot(command_prefix=command_prefix, intents=self.intents)
        self.db = DBHelper()
        self.db.create_db()

    def run(self):
        logging.info("Initating Melbot...") 
        self.add_bot_events()
        self.bot.run(self.discord_token)

    def db_close(self):
        self.db.close()

    # bot events
    def add_bot_events(self):
        @self.bot.event
        async def on_message(message):
            if message.author == self.bot.user:
                return
            if not message.content.startswith(self.bot.command_prefix):
                self.db.add_event(message.author.id, 1, 'message')
            await self.bot.process_commands(message)

        @self.bot.command()
        async def points(ctx, user: SafeMember = None):
            if user is None:
                user = ctx.author
            user_id = str(user.id)
            total_currency = self.db.get_total_currency(user_id)
            await ctx.send(f'{user.name} has {total_currency} points')

        @self.bot.command()
        async def buy(ctx, item_id = None):
            if item_id is None:
                await ctx.send("Please provide an item ID.")
                return
            
            user_id = str(ctx.author.id)
            try:
                item_id = int(item_id)
            except ValueError:
                print("Conversion to int failed")

            if type(item_id) == int:
                item_price = self.db.buy_items_by_id(item_id)
            elif type(item_id) == str:
                item_price = self.db.buy_items_by_name(item_id)
            else:
                await ctx.send("Wrong syntax, it should be like this '!buy 1', or '!buy gen'")
                return

            if item_price is None:
                await ctx.send("The item does not exist.")
                return

            user_points = self.db.get_total_currency(user_id)
            
            if user_points < item_price:
                await ctx.send(f"You do not have enough points to buy this item. You have {user_points} points but need {item_price} points.")
                return

            self.db.add_event(user_id, item_price * -1, f"bought item {item_id}")
            await ctx.send(f"You have successfully bought the item with ID {item_id} for {item_price} points.")

        @self.bot.command()
        async def shop(ctx):
            items = self.db.get_shop_items()
            if len(items) == 0:
                await ctx.send("The shop is empty.")
                return
            shop_str = "Shop items:\n"
            for item in items:
                shop_str += f"ID: {item[0]}, Name: {item[1]}, Price: {item[2]}\n"
            await ctx.send(shop_str)

        @self.bot.command()
        async def gamble(ctx, points: int):
            user_id = str(ctx.author.id)
            user_points = self.db.get_total_currency(user_id)
            if points > user_points:
                await ctx.send(f"You do not have enough points to gamble {points} points. You have {user_points} points.")
                return
            if points < 0:
                await ctx.send("You cannot gamble a negative number of points.")
                return
            earned_points = gamba(points)
            self.db.add_event(user_id, earned_points - points, 'gamble')
            if earned_points == 0:
                await ctx.send(f"You lost {points} points.")
            else:
                await ctx.send(f"You won {earned_points} points.")

        # admin commands
        @self.bot.command()
        @commands.has_permissions(administrator=True)
        async def add_item(ctx, item_name: str = None, item_price: int = None):
            if item_name is None or item_price is None:
                await ctx.send("Please provide an item name and price.")
                return
            if type(item_price) != int or type(item_name) != str:
                await ctx.send("Wrong syntax, it should be like this ""!add_item gen 500")
                return
            self.db.add_item(item_name, item_price)
            await ctx.send(f"Item {item_name} added to the shop with price {item_price} points.")

        @self.bot.command()
        @commands.has_permissions(administrator=True)
        async def add(ctx, user: SafeMember, points: int):
            user_id = str(user.id)
            self.db.add_event(user_id, points, 'admin added')
            await ctx.send(f"{points} points added to {user.name}'s account.")

        @self.bot.command()
        @commands.has_permissions(administrator=True)
        async def remove_item(ctx, item_id: str):
            if item_id is None:
                await ctx.send("Please provide an item ID.")
                return
            try:
                item_id = int(item_id)
            except ValueError:
                print("Conversion to int failed")
            if type(item_id) == int:
                rows_deleted = self.db.remove_item_by_id(item_id)
            elif type(item_id) == str:
                rows_deleted = self.db.remove_item_by_name(item_id)
            else:
                await ctx.send("Wrong syntax, it should be like this '!remove_item 1' or '!remove_item gen'")
                return
            if rows_deleted == 0:
                await ctx.send(f"The item {item_id} does not exist.")
                return
            else:
                await ctx.send(f"Item with ID {item_id} removed from the shop.")

        @self.bot.command()
        @commands.has_permissions(administrator=True)
        async def remove(ctx, user: SafeMember, points: int):
            user_id = str(user.id)
            self.db.add_event(user_id, points * -1, 'admin removed')
            await ctx.send(f"{points} points removed from {user.name}'s account.")