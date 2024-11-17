import random
import os
import json
from helpers.db_helper import DBHelper
from discord.ext.commands import Bot

def gamba_odds(value: int) -> int:
    if random.random() < 0.45:
        return 2 * value
    else:
        return 0

config = json.load(open('games/gamba.json'))

def add_bot_commands(bot: Bot, db: DBHelper):    
    @bot.command(help="Gamble your melpoints. You can use !gamble <number> to gamble a specific number of melpoints.")
    async def gamble(ctx, points: int|str):
        user_id = str(ctx.author.id)
        user_points = await db.get_total_currency(user_id)
        # Handle string inputs
        if type(points) == str:
            if points.lower() == 'all':
                points = user_points
            elif points.lower() == 'half':
                points = user_points // 2
            elif points.lower() == 'max':
                points = min(user_points, config.get("gamble_limit"))
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
        if points > config.get("gamble_limit"):
            await ctx.send(f"You can't bet more than {config.get("gamble_limit")} points.")
            return
        earned_points = gamba_odds(points)
        await db.add_event(user_id, earned_points - points, 'gamble')
        if earned_points == 0:
            await ctx.send(f"{ctx.author} - You lost {points} points.")
        else:
            await ctx.send(f"{ctx.author} - You won {earned_points} points.")