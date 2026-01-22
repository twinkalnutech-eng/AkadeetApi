import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    host = os.getenv("DB_SERVER")
    port = int(os.getenv("DB_PORT", 3306))
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USERNAME")
    password = os.getenv("DB_PASSWORD")

    conn = mysql.connector.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        database=database
    )
    return conn
