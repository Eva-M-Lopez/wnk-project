import os, pymysql
from dotenv import load_dotenv
load_dotenv()

DB_HOST = "127.0.0.1"
DB_PORT = 3307  # use the port you confirmed (3307 or 3306)
DB_NAME = "wnk_dev"
DB_USER = "root"
DB_PASS = ""    # XAMPP default is empty


def get_db():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )