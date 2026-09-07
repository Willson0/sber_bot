import os
from dotenv import load_dotenv

load_dotenv(override=True)

BOT_TOKEN = os.getenv('BOT_TOKEN')
HYDRAI_TOKEN = os.getenv('HYDRAI_TOKEN')
