import dotenv
import signal
import sys
from bot import Melbot

# Goals for this bot:
"""
Assign a virtual currency to each user based on their server activity.
Change points to melpoints.
Add daily login reward and daily streak.
Add cooldown for point allocation.
-- Done for messages. Which other activities should be tracked?
-- Should there be a daily limit?
-- Should we exclude commands?
-- Should be exclude messages in certain channels?
Users can use this currency to buy items from a shop.
-- Done.
-- Wat should happen when someone buys an item? Should admins be notified? If so, how?
The bot can display the current currency of each user.
-- Done.
The admin can add or remove currency from a user.
-- Done.
The admin can add or remove items from the shop using a command.
-- Done.
When an item is bought, dm the buyer and post in a specific channel.
Sanitize inputs.
Optional: Refactor code to move bot stuff to another file.
Optional: There is a web interface to manage the shop.
Optional: There is a web interface to manage currency.
Optional: Users can also gamble their currency.
-- Done.
Optional: Users can also gift currency to other users?
Optional: Add a help command. Display only the commands that the user can use.
Optional: Add logging.
Optional: Create a table with aggregated currency data for each user.
"""

dotenv.load_dotenv()
melbot = Melbot()

# Function to handle graceful shutdown
def shutdown_handler(signum, frame):
    print("Shutting down...")
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