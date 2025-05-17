import logging
from pymongo import MongoClient
from bson.objectid import ObjectId
import os
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logging.getLogger("pymongo").setLevel(logging.WARNING)

try:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(MONGO_URI)
    db = client['termsheets']

    users_collection = db['users']
    files_collection = db['uploaded_files']

    logger.info("✅ MongoDB connected successfully.")
except Exception as e:
    logger.error(f"❌ Error connecting to MongoDB: {e}")
    raise
