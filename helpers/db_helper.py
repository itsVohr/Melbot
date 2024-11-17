import aiosqlite
import asyncio
import logging
from datetime import datetime, timezone


class DBHelper:
    def __init__(self, db_name):
        self.db_name = db_name + ".db"
        self.conn = None
        
    async def initialize(self):
        self.conn = await aiosqlite.connect(self.db_name)
        self.c = await self.conn.cursor()

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def __aenter__(self):
        self.conn = await aiosqlite.connect(self.db_name)
        self.c = await self.conn.cursor()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.conn.close()

    async def create_db(self):
        if self.conn is None:
            raise RuntimeError("Database connection is not initialized.")
        
        await self.c.execute('''
            CREATE TABLE IF NOT EXISTS events
            (
                userid text,
                event_timestamp integer,
                currency_change integer,
                reason text
            )
        ''')
        await self.c.execute('CREATE INDEX IF NOT EXISTS idx_userid ON events(userid)')
        await self.c.execute('''
            CREATE TABLE IF NOT EXISTS shop
            (
                item_id integer PRIMARY KEY,
                item_name text,
                item_price integer,
                item_file text,
                item_description text
            )
        ''')
        await self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_item_id ON shop(item_id)')
        await self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_item_name ON shop(item_name)')
        await self.conn.commit()
        await self.c.execute('''
            CREATE TABLE IF NOT EXISTS points_agg
            (
                userid text PRIMARY KEY,
                total_points integer,
                last_update integer
            )
        ''')
        await self.c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_userid_agg ON points_agg(userid)')
        await self.conn.commit()
        await self.c.execute('''
            CREATE TABLE IF NOT EXISTS gacha_events
            (
                userid text,
                reward_rarity integer,
                reward_name text,
                event_timestamp integer
            )
        ''')
        await self.c.execute('CREATE INDEX IF NOT EXISTS idx_gacha_userid ON gacha_events(userid)')
        await self.conn.commit()
        await self.c.execute("DROP TABLE IF EXISTS users")
        await self.c.execute('''
            CREATE TABLE IF NOT EXISTS users
            (
                userid text
            )
        ''')
        await self.c.execute('CREATE INDEX IF NOT EXISTS idx_userid ON users(userid)')
        await self.conn.commit()

    async def aggregate_points(self, cutoff_timestamp):
        async with self.conn.execute('''
            CREATE TEMP TABLE total_points AS
                SELECT userid, SUM(currency_change) AS currency_change
                FROM (SELECT * FROM events WHERE event_timestamp < ?)
                GROUP BY userid;
        ''', (cutoff_timestamp,)) as cursor:
            await cursor.close()
        async with self.conn.execute('''
            UPDATE points_agg
            SET total_points = points_agg.total_points + (SELECT currency_change FROM total_points WHERE points_agg.userid = total_points.userid),
                last_update = ?
            WHERE EXISTS (
                SELECT 1
                FROM total_points
                WHERE points_agg.userid = total_points.userid
            );
        ''', (cutoff_timestamp,)) as cursor:
            await cursor.close()
        async with self.conn.execute('''
            INSERT INTO points_agg (userid, total_points, last_update)
            SELECT userid, currency_change, ?
            FROM total_points
            WHERE NOT EXISTS (
                SELECT 1
                FROM points_agg
                WHERE points_agg.userid = total_points.userid
            );
        ''', (cutoff_timestamp,)) as cursor:
            await cursor.close()
        async with self.conn.execute('DROP TABLE total_points;') as cursor:
            await cursor.close()
        async with self.conn.execute('DELETE FROM events WHERE event_timestamp < ?', (cutoff_timestamp,)) as cursor:
            await cursor.close()
        await self.conn.commit()

    async def add_event(self, userid: str, currency_change: int, reason: str):
        try:
            event_timestamp = int(datetime.now(timezone.utc).timestamp())
            query = 'INSERT INTO events VALUES (?, ?, ?, ?)'
            async with self.conn.execute(query, (userid, event_timestamp, currency_change, reason)) as cursor:
                await cursor.close()
            await self.conn.commit()
        except Exception as e:
            logging.error(f"Failed to add event: {e}")

    async def _add_event_test(self, userid: str, event_timestamp:int, currency_change: int, reason: str):
        try:
            query = 'INSERT INTO events VALUES (?, ?, ?, ?)'
            async with self.conn.execute(query, (userid, event_timestamp, currency_change, reason)) as cursor:
                await cursor.close()
            await self.conn.commit()
        except Exception as e:
            logging.error(f"Failed to add event: {e}")

    async def add_item(self, item_name: str, item_price: int, item_description: str, item_file: str):
        query = 'INSERT INTO shop (item_name, item_price, item_description, item_file) VALUES (?, ?, ?, ?)'
        await self.c.execute(query, (item_name, item_price, item_description, item_file))
        await self.conn.commit()

    async def remove_item_by_id(self, item_id: int):
        query = 'DELETE FROM shop WHERE item_id=?'
        await self.c.execute(query, (item_id,))
        rows_deleted = self.c.rowcount
        await self.conn.commit()
        return rows_deleted

    async def remove_item_by_name(self, item_name: str) -> int:
        query = 'DELETE FROM shop WHERE item_name=?'
        await self.c.execute(query, (item_name,))
        rows_deleted = self.c.rowcount
        await self.conn.commit()
        return rows_deleted
    
    async def get_live_currency(self, userid: str):
        query = 'SELECT SUM(currency_change) FROM events WHERE userid=?'
        async with self.conn.execute(query, (userid,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result[0] is not None else 0

    async def get_aggregated_currency(self, userid: str):
        query = 'SELECT total_points FROM points_agg WHERE userid=?'
        async with self.conn.execute(query, (userid,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_total_currency(self, userid: str):
        live_currency = await self.get_live_currency(userid)
        aggregated_currency = await self.get_aggregated_currency(userid)
        return live_currency + aggregated_currency

    async def buy_items_by_id(self, item_id: int):
        query = "SELECT item_price, coalesce(item_file, '') as item_file FROM shop WHERE item_id=?"
        async with self.conn.execute(query, (item_id,)) as cursor:
            result = await cursor.fetchone()
            return result if result else None
        
    async def buy_items_by_name(self, item_name: str):
        query = "SELECT item_price, coalesce(item_file, '') as item_file FROM shop WHERE item_name=?"
        async with self.conn.execute(query, (item_name,)) as cursor:
            result = await cursor.fetchone()
            return result if result else (None, None)
        
    async def get_shop_items(self):
        async with self.conn.execute('SELECT item_id, item_name, item_price, item_description FROM shop') as cursor:
            return await cursor.fetchall()
    
    async def get_leaderboard(self, limit: int = 10):
        query = '''
            SELECT sq2.userid, sq2.total_points
            FROM (
                SELECT sq.userid, SUM(sq.total_points) AS total_points
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
                ) sq
                GROUP BY sq.userid
            ) sq2
            JOIN users u
                ON sq2.userid = u.userid
            ORDER BY sq2.total_points DESC
            LIMIT ?;
        '''
        async with self.conn.execute(query, (limit,)) as cursor:
            return await cursor.fetchall()
    
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

    async def add_gacha_event(self, userid: str, reward_rarity: int, reward_name: str, event_timestamp: int):
        query = 'INSERT INTO gacha_events VALUES (?, ?, ?, ?)'
        await self.c.execute(query, (userid, reward_rarity, reward_name, event_timestamp))
        await self.conn.commit()

    async def get_pity(self, userid: str):
        query = """WITH last_rewards AS (
                SELECT
                    userid,
                    MAX(CASE WHEN reward_rarity = 4 THEN event_timestamp ELSE 0 END) AS last_reward_4,
                    MAX(CASE WHEN reward_rarity = 5 THEN event_timestamp ELSE 0 END) AS last_reward_5
                FROM gacha_events
                GROUP BY userid
            )
            SELECT
                e.userid,
                SUM(CASE WHEN e.event_timestamp > lr.last_reward_4 THEN 1 ELSE 0 END) AS events_since_last_reward_4,
                SUM(CASE WHEN e.event_timestamp > lr.last_reward_5 THEN 1 ELSE 0 END) AS events_since_last_reward_5
            FROM gacha_events e
            JOIN last_rewards lr ON e.userid = lr.userid
            WHERE e.userid = ?
            GROUP BY e.userid;"""
        async with self.conn.execute(query, (userid,)) as cursor:
            result = await cursor.fetchone()
            if result is None:
                return 0, 0
            else:
                return result[1], result[2]
    
    async def replace_users(self, user_list: list, batch_size: int = -1):
        if batch_size == -1:
            batch_size = len(user_list)
        for i in range(0, len(user_list), batch_size):
            batch = user_list[i:i+batch_size]
            batch_ids = [member.id for member in batch]
            sql = f"INSERT INTO users (userid) VALUES (?)"
            await self.c.executemany(sql, [(userid,) for userid in batch_ids])
            await self.conn.commit()

    async def delete_user(self, userid:str):
        query = """DELETE FROM events WHERE userid = ?"""
        await self.c.execute(query, (userid,))
        await self.conn.commit()

if __name__ == "__main__":
    import os

    async def test_db():
        db = DBHelper("test_melbot")
        await db.initialize()
        await db.create_db()
        await db._add_event_test("u1", 100, 100, "")
        await db._add_event_test("u1", 200, 200, "")
        await db._add_event_test("u2", 200, 200, "")
        await db._add_event_test("u2", 300, 300, "")
        await db._add_event_test("u3", 300, 300, "")
        await db._add_event_test("u3", 900, 900, "")
        await db._add_event_test("u2", 900, 900, "")
        await db.aggregate_points(250)
        t1 = await db.get_aggregated_currency("u1")
        t2 = await db.get_aggregated_currency("u2")
        print(t1,t2)
        # expected: u1: 300, u2: 200
        await db.aggregate_points(500)
        t1 = await db.get_aggregated_currency("u1")
        t2 = await db.get_aggregated_currency("u2")
        t3 = await db.get_aggregated_currency("u3")
        print(t1,t2, t3)
        # expected: u1: 300, u2: 500, u3: 300
        await db.aggregate_points(1000)
        t1 = await db.get_aggregated_currency("u1")
        t2 = await db.get_aggregated_currency("u2")
        t3 = await db.get_aggregated_currency("u3")
        print(t1,t2, t3)
        # expected: u1: 300, u2: 1400, u3: 1200

        os._exit(0)

    if os.path.exists("test_melbot.db"):
        os.remove("test_melbot.db")

    async def test_pity():
        db = DBHelper("melbot")
        await db.initialize()
        await db.create_db()
        p1, p2 = await db.get_pity("267036881038999553")
        print(p1, p2)
    
    #asyncio.run(test_db())
    asyncio.run(test_pity())