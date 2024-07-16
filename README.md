# Melbot
A Discord bot designed for Madame Melanie's community.

## Installation Steps
Follow these steps to install Melbot in your desired directory:

1. **Clone the Repository**
   - Navigate to the folder where you wish to install Melbot.
   - Run the following command:
	 ```
	 git clone https://github.com/itsVohr/Melbot/
	 ```

2. **(Optional) Create a Python Virtual Environment**
   - It's recommended to create a virtual environment for Python projects. This keeps dependencies required by different projects separate by creating isolated environments for them. You can create one using:
	 ```
	 python -m venv venv
	 ```
   - Activate the virtual environment:
	 - On Windows:
	   ```
	   .\venv\Scripts\activate
	   ```
	 - On Unix or MacOS:
	   ```
	   source venv/bin/activate
	   ```

3. **Install Dependencies**
   - Install the required Python packages by running:
	 ```
	 pip install -r requirements.txt
	 ```

4. **Configure Environment Variables**
   - Rename the `sample_dotenv` file to `.env`. This file contains environment variables crucial for running Melbot.
   - Open the `.env` file and update at least the following values:
	 - `DISCORD_TOKEN`: Your Discord bot token.
	 - `SHOP_CHANNEL_ID`: The ID of the Discord channel where the bot will post notifications about item purchases.
	 - `GDRIVE_FOLDER_ID`: The ID of the Google Drive folder Melbot will interact with.
	 - `BOT_ADMIN_ID`: The ID of the bot administrator.
	 - `BOT_COMMANDS_CHANNEL_ID`: The ID of the channel where the bot will take commands.

5. **Set Up Google Service Account**
   - Create a Google service account with the appropriate permissions to access your Google Drive.
   - Download the JSON file containing your service account's data.
   - Place the JSON file in the same directory as `main.py`. By default, the file should be named `melbot_service_account.json`. If you choose a different name or location, make sure to update the `GOOGLE_SERVICE_ACCOUNT` value in your `.env` file accordingly.
   Yes, this step is mandatory. At least for now.

By following these steps, you should have a fully functional instance of Melbot ready to serve your Discord community.