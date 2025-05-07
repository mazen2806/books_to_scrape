import os
from pymongo import MongoClient


def get_books_collection():
    client = MongoClient(os.environ["CONN_STR"])

    db = client["books_db"]
    return db["books_collection"]


def save_books(data):
    collection = get_books_collection()

    result = collection.insert_many(data)

    if result:
        print("Books collection is saved successfully")
