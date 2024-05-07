import os
import sqlite3

def setup_db(path):
    db_location = path + "history.db"
    #checks if the user already has a db file in the directory, if not, creates it.
    #replace the file path with yours here
    if not os.path.isfile(db_location):
        try:
            con = sqlite3.connect(db_location)
            cur = con.cursor()
            cur.execute(
                ("CREATE TABLE chat_messages "
                    "(chat_id INTEGER,"
                    "message_id INTEGER PRIMARY KEY,"
                    "role TEXT,"
                    "message TEXT,"
                    "description TEXT);")
                )
            cur.execute(
                ("CREATE TABLE images ("
                    "id INTEGER PRIMARY KEY,"
                    "content TEXT,"
                    "name TEXT,"
                    "extension TEXT,"
                    "chat_id INTEGER,"
                    "message_idx INTEGER);")
            );
            cur.execute(
                ("CREATE TABLE files ("
                    "id INTEGER PRIMARY KEY,"
                    "content TEXT,"
                    "name TEXT,"
                    "extension TEXT,"
                    "chat_id INTEGER,"
                    "message_idx INTEGER);")
            );
            return (con, cur)

        except sqlite3.Error as e:
            print(e)
            exit()
    else:
        con = sqlite3.connect(db_location)
        cur = con.cursor()
        return (con, cur)

def setup_key():
    if key:=os.environ.get('OPENAI_API_KEY'):
        return key
        
    else:
        print("Environment variable for key not found, please add one.")
        exit()