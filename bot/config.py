import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).parent.parent / '.env')

DISCORD_TOKEN: str = os.getenv('DISCORD_TOKEN', '')
FFMPEG_PATH: str = os.getenv('FFMPEG_PATH', 'ffmpeg')
DATABASE_PATH: str = os.getenv('DATABASE_PATH', './data/bot.db')
YOUTUBE_API_KEY: str = os.getenv('YOUTUBE_API_KEY', '')
BACKGROUNDS_PATH: str = os.getenv('BACKGROUNDS_PATH', './assets/backgrounds')

PANEL_SECRET_KEY: str = os.getenv('PANEL_SECRET_KEY', 'changeme')
PANEL_USERNAME: str = os.getenv('PANEL_USERNAME', 'admin')
PANEL_PASSWORD: str = os.getenv('PANEL_PASSWORD', 'admin')
PANEL_HOST: str = os.getenv('PANEL_HOST', '0.0.0.0')
PANEL_PORT: int = int(os.getenv('PANEL_PORT', '8080'))

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN tidak ditemukan di file .env!")
