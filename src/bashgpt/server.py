from flask import Flask, render_template, jsonify, request, Response
from bashgpt.main import path
import os
import sqlite3
from bashgpt.chat import chat, load_chat, add_message_to_chat, save_chat, reset_chat, defaults
from bashgpt.api import get_response
from bashgpt.data_loader import data_loader
from openai import OpenAI
from functools import wraps



def get_db_connection():
    con = sqlite3.connect(path + "history.db")
    con.row_factory = sqlite3.Row
    return con

def with_db(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        con = get_db_connection()
        cur = con.cursor()
        try:
            result = f(con, cur, *args, **kwargs)
            return result
        finally:
            cur.close()
            con.close()
    return decorated_function

def server():
    (modes, models, providers) = data_loader()
    app = Flask(__name__,
                template_folder=os.path.join(path, "html"),
                static_folder=os.path.join(path, "static"))


    @app.route("/chat/<int:chat_id>", methods=["GET"])
    @with_db
    def get_chat(con, cur, chat_id):
        try:
            load_chat(cur, chat_id)
            return render_template("chat.html",
                                chat_id=chat_id,
                                chat_info=chat,
                                messages=chat["all_messages"],
                                images=chat["images"],
                                files=chat["files"])
        except Exception as e:
            return f"Error: {str(e)}", 500


    @app.route("/", methods=["GET"])
    @with_db
    def list_chats(con, cur):
        reset_chat()
        cur.execute("SELECT * FROM chats ORDER BY chat_id DESC LIMIT 3")
        chats = [dict(row) for row in cur.fetchall()]
        return render_template("home.html", 
                               chat_info=chat,
                               messages=chat["all_messages"],
                               images=chat["images"],
                               files=chat["files"],
                               chats=chats)


    @app.route("/api/answer", methods=["GET","POST"])
    def answer():
        data = request.get_json()
        message = data["message"]
        if message: add_message_to_chat("user", message)
        
        # For streaming, we need to manage DB without the generator
        con = get_db_connection()
        cur = con.cursor()
        
        # Create a reference to hold the complete response
        response_complete = [False]
        
        def generate():
            try:
                text_stream = get_response()

                for char in text_stream:
                    yield char
                
                # Mark response as complete before saving
                response_complete[0] = True
            except Exception as e:
                # Mark response as complete on error
                response_complete[0] = True
                yield f"Error: {str(e)}"
                raise

        # Create the response object
        response = Response(generate(), mimetype="text/plain") # type: ignore
        
        # Add a callback to close the connection when streaming is done
        @response.call_on_close
        def on_close():
            if response_complete[0]:
                # Only save if the response completed successfully
                try:
                    save_chat(con, cur)
                except Exception as e:
                    print(f"Error saving chat: {str(e)}")
            cur.close()
            con.close()
            
        return response

    @app.route("/api/create-new-chat", methods=["POST"])
    @with_db
    def make_new_chat(con, cur):
        reset_chat()
        print(chat["all_messages"])
        
        data = request.get_json()
        message = data["message"]

        for mode in modes:
            if mode["name"] == chat["mode"]:
                add_message_to_chat("system", mode["description"])
        
        add_message_to_chat("user", message)
        save_chat(con, cur)

        chat_id = cur.execute("SELECT chat_id FROM chat_messages ORDER BY chat_id DESC LIMIT 1").fetchone()[0]

        return jsonify({"chat_id": chat_id})
        
        



    app.run(debug=True)

if __name__ == "__main__":
    server()