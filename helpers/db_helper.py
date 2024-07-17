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

        await self.conn.commit()

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
        await db.aggregate_points(250)
        t1 = await db.get_aggregated_currency("u1")
        t2 = await db.get_aggregated_currency("u2")
        print(t1,t2)
        # expected: u1: 300, u2: 200
        await db.aggregate_points(500)
        # expected: u1: 300, u2: 500, u3: 300
        t1 = await db.get_aggregated_currency("u1")
        t2 = await db.get_aggregated_currency("u2")
        t3 = await db.get_aggregated_currency("u3")
        print(t1,t2, t3)
        exit(0)
        
    if os.path.exists("test_melbot.db"):
        os.remove("test_melbot.db")
    asyncio.run(test_db())