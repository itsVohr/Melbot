import discord
import os
import dotenv
import signal
import sys
import asyncio
import random
from discord.ext import commands
from db_stuff.db_helper import DBHelper

# Goals for this bot:
"""
Assign a virtual currency to each user based on their server activity.
-- Done for messages. Which other activities should be tracked?
-- Should there be a daily limit?
-- Should we exclude commands?
-- Should be exclude messages in certain channels?
Users can use this currency to buy items from a shop.
-- Done.
-- Wat should happen when someone buys an item? Should admins be notified? If so, how?
The bot can display the current currency of each user.
-- Done.
The admin can add or remove currency from a user.
-- Done.
The admin can add or remove items from the shop using a command.
-- Done.
When an item is bought, dm the buyer and post in a specific channel.
Sanitize inputs.
Optional: Refactor code to move bot stuff to another file.
Optional: There is a web interface to manage the shop.
Optional: There is a web interface to manage currency.
Optional: Users can also gamble their currency.
-- Done.
Optional: Users can also gift currency to other users?
Optional: Add a help command. Display only the commands that the user can use.
Optional: Add logging.
Optional: Create a table with aggregated currency data for each user.
"""

dotenv.load_dotenv()

# bot initial setup
intents = discord.Intents.default()
intents.message_content = True
discord_token = os.environ['DISCORD_TOKEN']
bot = commands.Bot(command_prefix='!', intents=intents)
db = DBHelper()
db.create_db()

class SafeMember(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            member = await commands.MemberConverter().convert(ctx, argument)
            return member
        except commands.MemberNotFound:
            # Send message to Discord before raising exception
            message = await ctx.send(f"Cannot find user {argument}.")
            
            def check(m):
                return m.id == message.id and m.channel == ctx.channel

            try:
                await bot.wait_for('message', check=check, timeout=5.0)
            except asyncio.TimeoutError:
                pass  # Handle timeout if needed
            
            raise commands.BadArgument(f'Member "{argument}" not found.')


def gamba(value: int) -> int:
    # 50% chance of returning twice the value
    if random.random() < 0.45:
        return 2 * value
    else:
        return 0

# bot events
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    db.add_event(message.author.id, 1, 'message')
    await bot.process_commands(message)

@bot.command()
async def points(ctx, user: SafeMember = None):
    if user is None:
        user = ctx.author
    user_id = str(user.id)
    total_currency = db.get_total_currency(user_id)
    await ctx.send(f'{user.name} has {total_currency} points')

# Command to buy an item from the shop
@bot.command()
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
        item_price = db.buy_items_by_id(item_id)
    elif type(item_id) == str:
        item_price = db.buy_items_by_name(item_id)
    else:
        await ctx.send("Wrong syntax, it should be like this '!buy 1', or '!buy gen'")
        return

    if item_price is None:
        await ctx.send("The item does not exist.")
        return

    user_points = db.get_total_currency(user_id)
    
    if user_points < item_price:
        await ctx.send(f"You do not have enough points to buy this item. You have {user_points} points but need {item_price} points.")
        return

    db.add_event(user_id, item_price * -1, f"bought item {item_id}")
    await ctx.send(f"You have successfully bought the item with ID {item_id} for {item_price} points.")

@bot.command()
@commands.has_permissions(administrator=True)
async def add_item(ctx, item_name: str = None, item_price: int = None):
    if item_name is None or item_price is None:
        await ctx.send("Please provide an item name and price.")
        return
    if type(item_price) != int or type(item_name) != str:
        await ctx.send("Wrong syntax, it should be like this ""!add_item gen 500")
        return
    db.add_item(item_name, item_price)
    await ctx.send(f"Item {item_name} added to the shop with price {item_price} points.")

@bot.command()
async def shop(ctx):
    items = db.get_shop_items()
    if len(items) == 0:
        await ctx.send("The shop is empty.")
        return
    shop_str = "Shop items:\n"
    for item in items:
        shop_str += f"ID: {item[0]}, Name: {item[1]}, Price: {item[2]}\n"
    await ctx.send(shop_str)

@bot.command()
@commands.has_permissions(administrator=True)
async def add(ctx, user: SafeMember, points: int):
    user_id = str(user.id)
    db.add_event(user_id, points, 'admin added')
    await ctx.send(f"{points} points added to {user.name}'s account.")

@bot.command()
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
        rows_deleted = db.remove_item_by_id(item_id)
    elif type(item_id) == str:
        rows_deleted = db.remove_item_by_name(item_id)
    else:
        await ctx.send("Wrong syntax, it should be like this '!remove_item 1' or '!remove_item gen'")
        return
    if rows_deleted == 0:
        await ctx.send(f"The item {item_id} does not exist.")
        return
    else:
        await ctx.send(f"Item with ID {item_id} removed from the shop.")

@bot.command()
@commands.has_permissions(administrator=True)
async def remove(ctx, user: SafeMember, points: int):
    user_id = str(user.id)
    db.add_event(user_id, points * -1, 'admin removed')
    await ctx.send(f"{points} points removed from {user.name}'s account.")

@bot.command()
async def gamble(ctx, points: int):
    user_id = str(ctx.author.id)
    user_points = db.get_total_currency(user_id)
    if points > user_points:
        await ctx.send(f"You do not have enough points to gamble {points} points. You have {user_points} points.")
        return
    if points < 0:
        await ctx.send("You cannot gamble a negative number of points.")
        return
    earned_points = gamba(points)
    db.add_event(user_id, earned_points - points, 'gamble')
    if earned_points == 0:
        await ctx.send(f"You lost {points} points.")
    else:
        await ctx.send(f"You won {earned_points} points.")


# Function to handle graceful shutdown
def shutdown_handler(signum, frame):
    print("Shutting down...")
    db.close()
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, shutdown_handler)  # Handle keyboard interrupt
signal.signal(signal.SIGTERM, shutdown_handler)  # Handle termination signal


# run the bot
try:
    bot.run(discord_token)
finally:
    db.close()