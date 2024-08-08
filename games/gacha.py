import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import json
import logging
import random
from datetime import datetime
from helpers.db_helper import DBHelper
from discord.ext.commands import Bot
from helpers.gdrive_helper import GDriveHelper

class Gacha:
    def __init__(self, db: DBHelper, user: int) -> None:
        self.db = db
        self.user = user
        self.config = json.load(open('Melbot/games/gacha.json'))

    async def _get_pity(self):
        (self.pity_4, self.pity_5) = await self.db.get_pity(self.user)

    async def _update_db(self, reward_name: str, reward: int):
        await self.db.add_event(self.user, self.config['pull_price'] * -1, 'gacha')
        await self.db.add_gacha_event(self.user, reward_name, reward, datetime.now().timestamp())

    async def _five_star_pity(self, pulls: int) -> float:
        soft_pity = self.config['five_star_soft_pity']
        hard_pity = self.config['five_star_pity']
        premium_rate = self.config['five_star_rate']
        if pulls < soft_pity:
            return self.config['five_star_rate']
        elif soft_pity <= pulls < hard_pity:
            return (pulls - soft_pity - 1) * (1 - premium_rate) / (hard_pity - soft_pity - 1) + premium_rate
        else:
            return 1.0
        
    async def get_reward(self, rarity: int) -> str:
        files = GDriveHelper().get_files()
        for file in files:
            if file['name'] == f"{rarity} Stars":
                parent_folder = file["id"]
                break
        if not parent_folder:
            logging.error(f"Folder for {rarity} stars not found.")
            return "Parent folder not found."
        potential_rewards = [file for file in files if parent_folder in file.get("parents", [])]
        if not potential_rewards or len(potential_rewards) == 0:
            logging.error(f"No rewards found for {rarity} stars.")
            return "No rewards found."
        reward = random.choice(potential_rewards)
        return reward["webViewLink"], reward["name"]

    async def pull(self):
        await self._get_pity()
        roll = random.random()
        if roll <= await self._five_star_pity(self.pity_5):
            reward = 5
        elif roll <= self.config['four_star_rate'] or self.pity_4 == self.config['four_star_pity']:
            reward = 4
        else:
            reward = 3
            reward_link, reward_name = await self.get_reward(reward)
        await self._update_db(reward_name, reward)
        return (reward, reward_link)

def add_bot_commands(bot: Bot, db: DBHelper):
    @bot.command(help="Pull from the gacha. You can use !pull to pull from the gacha.")
    async def gacha(ctx, amt: int|str = 1):
        user_id = str(ctx.author.id)
        gacha = Gacha(db, user_id)
        user_points = await db.get_total_currency(user_id)
        if amt == 'max':
            amt = user_points // gacha.config['pull_price']
        if user_points < gacha.config['pull_price'] * amt:
            await ctx.send(f"{ctx.author} - You don't have enough points to pull from the gacha.")
            return
        (reward, reward_link) = await gacha.pull()
        await ctx.send(f"{ctx.author} - You pulled and got a {reward} stars reward.")
        await ctx.author.send(f"Congratulations! You just got a {reward} stars pull!"+reward_link)


if __name__ == '__main__':
    db = DBHelper("gacha_test.db")
    gacha = Gacha(db, 1)
    for i in range(gacha.config['five_star_pity']):
        print(f"Chances to get a 5 star on pull number {i}: {gacha._five_star_pity(i)}")