import json
import random

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
        self.config = json.load(open('Melbot/games/blackjack.json'))
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
    