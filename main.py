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
Sanitize inputs.
Optional: There is a web interface to manage the shop.
Optional: There is a web interface to manage currency.
Optional: Users can also gift currency to other users?
Optional: Improve logging.
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