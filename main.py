import dotenv
import signal
import sys
import logging
import datetime
import asyncio
from bot import Melbot

# Set up logging
current_date = datetime.datetime.now().strftime("%Y-%m-%d")
logging.basicConfig(
    filename = f'melbot-{current_date}.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
dotenv.load_dotenv()


# Function to handle graceful shutdown
def shutdown_handler(signum, frame):
    logging.info("Process termination requested, shutting down Melbot...")
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, shutdown_handler)  # Handle keyboard interrupt
signal.signal(signal.SIGTERM, shutdown_handler)  # Handle termination signal


async def main():
    melbot = Melbot()
    await melbot.run()

def run_main():
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if str(e) == "asyncio.run() cannot be called from a running event loop":
            loop = asyncio.get_running_loop()  # Changed from get_event_loop to get_running_loop
            loop.run_until_complete(main())
        else:
            raise

if __name__ == "__main__":
    run_main()