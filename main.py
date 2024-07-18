import dotenv
import signal
import sys
import os
import logging
import datetime
import asyncio
import threading
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


async def shutdown(loop):
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task(loop)]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await loop.shutdown_asyncgens()

async def main():
    melbot = Melbot()
    try:
        await melbot.run()
    finally:
        await melbot.shutdown()

def log_active_threads(stage):
    logging.info(f"Active threads at {stage}:")
    for thread in threading.enumerate():
        logging.info(f"Thread: {thread.name}, ID: {thread.ident}")

def join_remaining_threads():
    for thread in threading.enumerate():
        if thread is not threading.current_thread():
            print(f"Joining thread: {thread.name}")
            thread.join(timeout=5)

def run_main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        log_active_threads("start")
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("Keyboard interrupt detected, shutting down Melbot...")
        loop.run_until_complete(shutdown(loop))
    finally:
        log_active_threads("before shutdown")
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except (asyncio.CancelledError, RuntimeError):
            pass
        loop.close()
        print("Event loop closed.")
        log_active_threads("after shutdown")
        join_remaining_threads()
        log_active_threads("after joining threads")

        # If there are still threads remaining, force exit
        remaining_threads = threading.enumerate()
        if len(remaining_threads) > 1:  # More than just the main thread
            print("Remaining threads detected, forcefully exiting.")
            os._exit(1)
        else:
            sys.exit(0)

if __name__ == "__main__":
    run_main()