"""
Configuració central de la connexió a MongoDB Atlas.
Llegeix credencials del fitxer .env a l'arrel del projecte.
Importar get_db() des de qualsevol mòdul del projecte.
"""

import os
from pathlib import Path

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

load_dotenv(Path(__file__).parent.parent.parent / '.env')

MONGO_URI = os.environ['MONGO_URI']
DB_NAME   = os.environ.get('MONGO_DB', 'damm-base')

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=8000, tlsAllowInvalidCertificates=True, tlsCAFile=certifi.where())
    return _client


def get_db() -> Database:
    return get_client()[DB_NAME]
