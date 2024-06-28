import sqlite3
from datetime import datetime, timezone


class DBHelper:
    def __init__(self, db_name='melbot.db'):
        self.conn = sqlite3.connect(db_name)
        self.c = self.conn.cursor()

    def create_db(self):
        self.c.execute('''
                    CREATE TABLE IF NOT EXISTS events
                    (
                        userid text,
                        event_timestamp integer,
                        currency_change integer,
                        reason text
                    )
        ''')
        self.c.execute('CREATE INDEX IF NOT EXISTS idx_userid ON events(userid)')
        self.c.execute('''
                        CREATE TABLE IF NOT EXISTS shop
                        (
                            item_id integer PRIMARY KEY,
                            item_name text,
                            item_price integer
                        )
        ''')
        self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_item_id ON shop(item_id)')
        self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_item_name ON shop(item_name)')
        self.conn.commit()

    def add_event(self, userid:str, currency_change:int, reason:str):
        event_timestamp = int(datetime.now(timezone.utc).timestamp())
        self.c.execute(f'INSERT INTO events VALUES ("{userid}", {event_timestamp}, {currency_change}, "{reason}")')
        self.conn.commit()

    def add_item(self, item_name:str, item_price:int):
        self.c.execute(f'INSERT INTO shop (item_name, item_price) VALUES ("{item_name}", {item_price})')
        self.conn.commit()

    def get_total_currency(self, userid:str):
        self.c.execute(f'SELECT SUM(currency_change) FROM events WHERE userid="{userid}"')
        result = self.c.fetchone()
        return result[0] if result[0] is not None else 0
    
    def buy_items_by_id(self, item_id:int):
        self.c.execute(f'SELECT item_price FROM shop WHERE item_id={item_id}')
        result = self.c.fetchone()
        if result is None:
            return None
        item_price = result[0]
        return item_price
    
    def buy_items_by_name(self, item_name:str):
        self.c.execute(f"SELECT item_price FROM shop WHERE item_name='{item_name}'")
        result = self.c.fetchone()
        if result is None:
            return None
        item_price = result[0]
        return item_price
    
    def get_shop_items(self):
        self.c.execute('SELECT * FROM shop')
        return self.c.fetchall()

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    print("You are running the wrong file. Moron.")