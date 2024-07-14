import sqlite3
import aiosqlite
from datetime import datetime, timezone


class DBHelper:
    def __init__(self, db_name):
        self.conn = sqlite3.connect(db_name+".db")
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
                        item_price integer,
                        item_file text
                    )
        ''')
        self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_item_id ON shop(item_id)')
        self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_item_name ON shop(item_name)')
        self.conn.commit()
        self.c.execute('''
                    CREATE TABLE IF NOT EXISTS points_agg
                    (
                        userid text PRIMARY KEY,
                        total_points integer,
                        last_update integer
                    )
        ''')
        self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_userid_agg ON points_agg(userid)')

    def aggregate_points(self, cutoff_timestamp):
        # Create a temporary table to hold the aggregated points
        self.c.execute('''
            CREATE TEMPORARY TABLE total_points AS
                SELECT userid, SUM(currency_change) AS currency_change, MAX(event_timestamp) AS event_timestamp
                FROM events
                WHERE event_timestamp < ?
                GROUP BY userid;
        ''', (cutoff_timestamp,))
        # Insert new aggregated points into points_agg
        self.c.execute('''
            INSERT INTO points_agg (userid, total_points, last_update)
            SELECT userid, currency_change, event_timestamp
            FROM total_points
            WHERE NOT EXISTS (
                SELECT 1
                FROM points_agg
                WHERE points_agg.userid = total_points.userid
            );
        ''')
        # Update existing records in points_agg with new aggregated points
        self.c.execute('''
            UPDATE points_agg
            SET total_points = (SELECT currency_change FROM total_points WHERE points_agg.userid = total_points.userid),
                last_update = (SELECT event_timestamp FROM total_points WHERE points_agg.userid = total_points.userid)
            WHERE EXISTS (
                SELECT 1
                FROM total_points
                WHERE points_agg.userid = total_points.userid
                AND points_agg.last_update < total_points.event_timestamp
            );
        ''')
        # Drop the temporary table
        self.c.execute('DROP TABLE total_points;')
        self.conn.commit()

        # Delete events that have been aggregated
        self.c.execute('DELETE FROM events WHERE event_timestamp < ?', (cutoff_timestamp,))
        self.conn.commit()

    def add_event(self, userid: str, currency_change: int, reason: str):
        event_timestamp = int(datetime.now(timezone.utc).timestamp())
        query = 'INSERT INTO events VALUES (?, ?, ?, ?)'
        self.c.execute(query, (userid, event_timestamp, currency_change, reason))
        self.conn.commit()

    def add_item(self, item_name: str, item_price: int, item_file: str):
        query = 'INSERT INTO shop (item_name, item_price, item_file) VALUES (?, ?, ?)'
        self.c.execute(query, (item_name, item_price, item_file))
        self.conn.commit()

    def remove_item_by_id(self, item_id: int):
        query = 'DELETE FROM shop WHERE item_id=?'
        self.c.execute(query, (item_id,))
        rows_deleted = self.c.rowcount
        self.conn.commit()
        return rows_deleted

    def remove_item_by_name(self, item_name: str) -> int:
        query = 'DELETE FROM shop WHERE item_name=?'
        self.c.execute(query, (item_name,))
        rows_deleted = self.c.rowcount
        self.conn.commit()
        return rows_deleted
    
    def get_live_currency(self, userid: str):
        query = 'SELECT SUM(currency_change) FROM events WHERE userid=?'
        self.c.execute(query, (userid,))
        result = self.c.fetchone()
        return result[0] if result[0] is not None else 0

    def get_aggregated_currency(self, userid: str):
        query = 'SELECT total_points FROM points_agg WHERE userid=?'
        self.c.execute(query, (userid,))
        result = self.c.fetchone()
        return result[0] if result else 0

    def get_total_currency(self, userid: str):
        live_currency = self.get_live_currency(userid)
        aggregated_currency = self.get_aggregated_currency(userid)
        return live_currency + aggregated_currency

    def buy_items_by_id(self, item_id: int):
        query = "SELECT item_price, coalesce(item_file, '') as item_file FROM shop WHERE item_id=?"
        self.c.execute(query, (item_id,))
        result = self.c.fetchone()
        return result if result else None
        
    def buy_items_by_name(self, item_name: str):
        query = "SELECT item_price, coalesce(item_file, '') as item_file FROM shop WHERE item_name=?"
        self.c.execute(query, (item_name,))
        result = self.c.fetchone()
        return result if result else None
        
    def get_shop_items(self):
        self.c.execute('SELECT item_id, item_name, item_price FROM shop')
        return self.c.fetchall()
    
    def get_leaderboard(self, limit: int = 10):
        query = '''
            SELECT userid, SUM(total_points) AS total_points
            FROM (
                SELECT
                    userid,
                    SUM(currency_change) AS total_points
                FROM events e
                GROUP BY userid
                UNION ALL
                SELECT
                    userid,
                    total_points
                FROM points_agg p
            )
            GROUP BY userid
            ORDER BY total_points DESC
            LIMIT ?;
        '''
        self.c.execute(query, (limit,))
        return self.c.fetchall()
    
    async def aggregate_points_async(self, cutoff_timestamp):
        async with aiosqlite.connect('melbot.db') as adb:
            # Create a temporary table to hold the aggregated points
            await adb.execute('''
                CREATE TEMPORARY TABLE total_points AS
                    SELECT userid, SUM(currency_change) AS currency_change, MAX(event_timestamp) AS event_timestamp
                    FROM events
                    WHERE event_timestamp < ?
                    GROUP BY userid;
            ''', (cutoff_timestamp,))
            # Insert new aggregated points into points_agg
            await adb.execute('''
                INSERT INTO points_agg (userid, total_points, last_update)
                SELECT userid, currency_change, event_timestamp
                FROM total_points
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM points_agg
                    WHERE points_agg.userid = total_points.userid
                );
            ''')
            # Update existing records in points_agg with new aggregated points
            await adb.execute('''
                UPDATE points_agg
                SET total_points = (SELECT currency_change FROM total_points WHERE points_agg.userid = total_points.userid),
                    last_update = (SELECT event_timestamp FROM total_points WHERE points_agg.userid = total_points.userid)
                WHERE EXISTS (
                    SELECT 1
                    FROM total_points
                    WHERE points_agg.userid = total_points.userid
                    AND points_agg.last_update < total_points.event_timestamp
                );
            ''')
            # Drop the temporary table
            await adb.execute('DROP TABLE total_points;')
            await adb.commit()

            # Delete events that have been aggregated
            await adb.execute('DELETE FROM events WHERE event_timestamp < ?', (cutoff_timestamp,))
            await adb.commit()

    def close(self):
        self.conn.close()


if __name__ == "__main__":
    import dotenv
    dotenv.load_dotenv()
    db = DBHelper("melbot")
    item = db.buy_items_by_id(4)
    print(item)