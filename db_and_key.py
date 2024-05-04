import os
import sqlite3
from cs50 import SQL


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
        db.execute(
            ("CREATE TABLE chat_messages "
                "(chat_id INTEGER,"
                "message_id INTEGER PRIMARY KEY,"
                "user_name TEXT,"
                "message TEXT,"
                "has_images INTEGER"
                "description TEXT);")
            )
        db.execute(
            ("CREATE TABLE images ("
                "id INTEGER PRIMARY KEY,"
                "url TEXT,"
                "name TEXT,"
                "extension TEXT,"
                "chat_id INTEGER,"
                "message_idx INTEGER")
        );
        db.execute(
            ("CREATE TABLE files ("
                "id INTEGER PRIMARY KEY,"
                "content TEXT,"
                "name TEXT,"
                "extension TEXT,"
                "chat_id INTEGER,"
                "message_idx INTEGER")
        );
    else:
        db = SQL("sqlite:///" + db_location)
    return db

def setup_key():
    if key:=os.environ.get('OPENAI_API_KEY'):
        return key
        
    else:
        print("Environment variable for key not found, please add one.")
        exit()