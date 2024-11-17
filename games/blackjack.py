import json
import random
import asyncio
from discord.ext.commands import Bot
from helpers.db_helper import DBHelper
from datetime import datetime

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        if self.rank == 1:
            return f"ace of {self.suit}"
        elif self.rank == 11:
            return f"jack of {self.suit}"
        elif self.rank == 12:
            return f"queen of {self.suit}"
        elif self.rank == 13:
            return f"king of {self.suit}"
        else:
            return f"{self.rank} of {self.suit}"
    
class Deck:
    def __init__(self):
        self.cards = []
        self.build()

    def build(self):
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = range(1, 14)
        for suit in suits:
            for rank in ranks:
                self.cards.append(Card(suit, rank))
    
    def shuffle(self):
        random.shuffle(self.cards)
    
    def draw(self):
        return self.cards.pop()
    
class Player:
    def __init__(self) -> None:
        self.hand = []

class Blackjack:
    def __init__(self, initial_player_id: int) -> None:
        self.config = json.load(open('games/blackjack.json'))
        self.deck = Deck()
        self.deck.shuffle()
        self.players = {}
        self.players.update({"dealer": Player()}) 
        self.players.update({initial_player_id: Player()}) 

    def calculate_score(self, player_id: int):
        score = 0
        for card in self.players[player_id].hand:
            if card.rank == 1:
                if score + 11 > 21:
                    score += 1
                else:
                    score += 11
            elif card.rank >= 10:
                score += 10
            else:
                score += card.rank
        return score

    def deal(self):
        for player in self.players:
            self.players[player].hand.append(self.deck.draw())
            self.players[player].hand.append(self.deck.draw())

    def hit(self, player_id: int):
        self.players[player_id].hand.append(self.deck.draw())


def add_bot_commands(bot: Bot, playing_blackjack: dict, db: DBHelper):
    @bot.command(help="Play a game of blackjack for melpoints. Syntax: !blackjack <melpoints>")
    async def blackjack(ctx, points: int = None):
        user_id = ctx.author.id
        blackjack = Blackjack(user_id)
        user_points = await db.get_total_currency(str(user_id))

        # Validate points
        if points is None or type(points) != int:
            await ctx.send("Please provide a number of melpoints to bet. Syntax: !blackjack <melpoints>")
            return
        if points > user_points:
            await ctx.send(f"You do not have enough melpoints to bet {points} points. You have {user_points} melpoints.")
            return
        if points < blackjack.config['min_bet']:
            await ctx.send(f"The minimum bet is {blackjack.config['min_bet']} points.")
            return
        if points > blackjack.config['max_bet']:
            await ctx.send(f"The maximum bet is {blackjack.config['max_bet']} points.")
            return

        if user_id in playing_blackjack:
            await ctx.send("You are already playing a game of blackjack.")
            return

        blackjack.deal()

        await ctx.send(f"""{ctx.author.name} - you drew: {blackjack.players[user_id].hand[0]} and {blackjack.players[user_id].hand[1]}\nI drew: {blackjack.players["dealer"].hand[0]} and something else.\n\nYou have {blackjack.calculate_score(user_id)} points. Do you want to !hit or !stand?""")
        playing_blackjack.update({user_id: {"bet": points, "game": blackjack, "ctx": ctx,"start_time": datetime.now().timestamp()}})

    @bot.command()
    async def hit(ctx):
        user_id = ctx.author.id
        if user_id not in playing_blackjack:
            await ctx.send("You are not playing blackjack.")
            return
        blackjack = playing_blackjack[user_id]["game"]
        blackjack.hit(user_id)
        score = blackjack.calculate_score(user_id)
        if score > 21:
            await ctx.send(f"{ctx.author.name} - you drew: {blackjack.players[user_id].hand[-1]}\n\nYou have {score} points. You busted!")
            await db.add_event(user_id, playing_blackjack[user_id]["bet"] * -1, 'blackjack')
            playing_blackjack.pop(user_id)
            return
        await ctx.send(f"{ctx.author.name} - you drew: {blackjack.players[user_id].hand[-1]}\n\nYou have {score} points. Do you want to !hit or !stand?")
        playing_blackjack[user_id].update({"game": blackjack})

    @bot.command()
    async def stand(ctx):
        user_id = ctx.author.id
        if user_id not in playing_blackjack:
            await ctx.send("You are not playing blackjack.")
            return
        blackjack = playing_blackjack[user_id]["game"]
        user_score = blackjack.calculate_score(user_id)
        dealer_score = blackjack.calculate_score("dealer")
        while dealer_score < 17:
            blackjack.hit("dealer")
            await ctx.send(f"The dealer drew: {blackjack.players['dealer'].hand[-1]}")
            dealer_score = blackjack.calculate_score("dealer")
            await asyncio.sleep(0.5)
        if dealer_score > 21:
            await ctx.send(f"{ctx.author.name} - you have {user_score} points. The dealer busted with {dealer_score} points. You win!")
            await db.add_event(user_id, playing_blackjack[user_id]["bet"] * (blackjack.config["payout"] - 1), 'blackjack')
        elif user_score > dealer_score:
            await ctx.send(f"{ctx.author.name} - you have {user_score} points. The dealer has {dealer_score} points. You win!")
            await db.add_event(user_id, playing_blackjack[user_id]["bet"] * (blackjack.config["payout"] - 1), 'blackjack')
        elif user_score < dealer_score:
            await ctx.send(f"{ctx.author.name} - you have {user_score} points. The dealer has {dealer_score} points. You lose!")
            await db.add_event(user_id, playing_blackjack[user_id]["bet"] * -1, 'blackjack')
        elif user_score == 21 and len(blackjack.players[user_id].hand) == 2 and user_score > dealer_score:
            await ctx.send(f"{ctx.author.name} - you have {user_score} points. You got a blackjack! You win!")
            await db.add_event(user_id, playing_blackjack[user_id]["bet"] * (blackjack.config["payout"] - 1), 'blackjack')
        else:
            await ctx.send(f"{ctx.author.name} - you have {user_score} points. The dealer has {dealer_score} points. It's a tie! But the house always wins.")
            await db.add_event(user_id, playing_blackjack[user_id]["bet"] * -1, 'blackjack')
        playing_blackjack.pop(user_id)