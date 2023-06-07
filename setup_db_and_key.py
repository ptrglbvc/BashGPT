import os
import sqlite3
from cs50 import SQL
import openai


def setup_db(path):
    db_location = path + "history.db"
    #checks if the user already has a db file in the directory, if not, creates it.
    #replace the file path with yours here
    if not os.path.isfile(db_location):
        try:
            conn = sqlite3.connect(db_location)
        except sqlite3.Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
        #replace the file path with your file path here
        db = SQL("sqlite:///" + db_location)
        db.execute(("CREATE TABLE chat_messages ("
        "chat_id INTEGER,"
        "message_id INTEGER PRIMARY KEY,"
        "user_name TEXT,"
        "message TEXT,"
        "description TEXT);"))
    else:
        db = SQL("sqlite:///" + db_location)
    return db

def setup_key(path):
    key_location = path + "key.txt"
    if not os.path.isfile(key_location):
        key = input("What is your OpenAI API key? ")
        with open(key_location, "w") as key_file:
            key_file.write(key)

    with open(key_location, 'r') as key:
        openai.api_key = key.read().strip()