import dotenv
import signal
import sys
import logging
import datetime
from bot import Melbot

# Goals for this bot:
"""
Change points to melpoints.
Add daily login reward and daily streak.
Add cooldown for point allocation.
Assign a virtual currency to each user based on their server activity.
-- Done for messages. Which other activities should be tracked? --> daily logins and streaks.
-- Should there be a daily limit?
-- Should be exclude messages in certain channels?
Users can use this currency to buy items from a shop.
-- Done.
-- Wat should happen when someone buys an item? Should admins be notified? If so, how? --> dm user, post in a specific channel.
When an item is bought, dm the buyer and post in a specific channel.
Sanitize inputs.
Optional: There is a web interface to manage the shop.
Optional: There is a web interface to manage currency.
Optional: Users can also gift currency to other users?
Optional: Add a help command. Display only the commands that the user can use.
Optional: Add logging.
Optional: Create a table with aggregated currency data for each user.
"""


# Set up logging
current_date = datetime.datetime.now().strftime("%Y-%m-%d")
logging.basicConfig(
    filename = f'melbot-{current_date}.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
dotenv.load_dotenv()
melbot = Melbot()

# Function to handle graceful shutdown
def shutdown_handler(signum, frame):
    logging.info("Process termination requested, shutting down Melbot...")
    melbot.db_close()
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, shutdown_handler)  # Handle keyboard interrupt
signal.signal(signal.SIGTERM, shutdown_handler)  # Handle termination signal

# run the bot
try:
    melbot.run()
finally:
    melbot.db_close()