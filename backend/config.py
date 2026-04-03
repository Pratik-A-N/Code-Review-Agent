import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./reviews.db")
