
import os
from dotenv import load_dotenv

load_dotenv()


HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))



JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_SECRET_KEY_TO_SOMETHING_STRONG_AND_RANDOM")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12  



ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin1234!")  


DB_PATH = os.getenv("DB_PATH", "data/music.db")



VIRTUAL_CAMERA_DEVICE = os.getenv("VIRTUAL_CAMERA_DEVICE", "/dev/video0")


STREAM_WIDTH = int(os.getenv("STREAM_WIDTH", 1280))
STREAM_HEIGHT = int(os.getenv("STREAM_HEIGHT", 720))
STREAM_FPS = int(os.getenv("STREAM_FPS", 30))


BACKGROUND_IMAGE = os.getenv("BACKGROUND_IMAGE", "static/background.jpg")


YTDLP_COOKIES = os.getenv("YTDLP_COOKIES", "")


FRP_SERVER_ADDR = os.getenv("FRP_SERVER_ADDR", "your-vps-ip")
FRP_SERVER_PORT = int(os.getenv("FRP_SERVER_PORT", 7000))
FRP_TOKEN = os.getenv("FRP_TOKEN", "your-frp-auth-token")
FRP_SUBDOMAIN = os.getenv("FRP_SUBDOMAIN", "music")



SONG_BUFFER_SECONDS = int(os.getenv("SONG_BUFFER_SECONDS", 10))


MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", 50))
