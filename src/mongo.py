"""
Configuración central de la conexión a MongoDB Atlas.
Importar get_db() desde cualquier módulo del proyecto.
"""

from pymongo import MongoClient
from pymongo.database import Database

MONGO_URI = (
    "mongodb+srv://jportabellag_db_user:UXFUaPbdKZm92qhw"
    "@damm-base.kyubxgh.mongodb.net/?appName=damm-base"
)
DB_NAME = "damm-base"

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000)
    return _client


def get_db() -> Database:
    return get_client()[DB_NAME]
