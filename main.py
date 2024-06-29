import discord
import os
import dotenv
import signal
import sys
from discord.ext import commands
from db_stuff.db_helper import DBHelper

# Goals for this bot:
"""
Assign a virtual currency to each user based on their server acrtivity.
-- Done for messages. Which other activities should be tracked?
Users can use this currency to buy items from a shop.
-- Done.
The bot can display the current currency of each user.
-- Done.
The admin can add or remove currency from a user.
The admin can add or remove items from the shop using a command.
-- Add done. Remove pending.
Optional: There is a web interface to manage the shop.
Optional: There is a web interface to manage currency.
Optional: Users can also gamble their currency.
"""

dotenv.load_dotenv()

# bot initial setup
intents = discord.Intents.default()
intents.message_content = True
discord_token = os.environ['DISCORD_TOKEN']
bot = commands.Bot(command_prefix='!', intents=intents)
db = DBHelper()
db.create_db()

# bot events
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    db.add_event(message.author.id, 1, 'message')
    await bot.process_commands(message)

@bot.command()
async def points(ctx, user: commands.MemberConverter = None):
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
        print(item_price)
        print(item_id)
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