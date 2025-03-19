from flask import Flask, render_template, jsonify, request
from bashgpt.main import path
import os
import sqlite3

def get_chat_data(chat_id):
    db_location = path + "history.db"
    con = sqlite3.connect(db_location)
    con.row_factory = sqlite3.Row  # This enables column access by name
    cur = con.cursor()
    
    # Get chat info
    cur.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,))
    chat_info = dict(cur.fetchone() or {})
    
    # Get chat messages
    cur.execute("SELECT * FROM chat_messages WHERE chat_id = ? ORDER BY message_id", (chat_id,))
    messages = [dict(row) for row in cur.fetchall()]
    
    # Get any images associated with this chat
    cur.execute("SELECT * FROM images WHERE chat_id = ?", (chat_id,))
    images = [dict(row) for row in cur.fetchall()]
    
    # Get any files associated with this chat
    cur.execute("SELECT * FROM files WHERE chat_id = ?", (chat_id,))
    files = [dict(row) for row in cur.fetchall()]
    
    con.close()
    
    return {
        "chat_info": chat_info,
        "messages": messages,
        "images": images,
        "files": files
    }

def thing():
    app = Flask(__name__, 
                template_folder=os.path.join(path, "html"),
                static_folder=os.path.join(path, "static"))
    
    @app.route("/chat/<int:chat_id>", methods=["GET"])
    def get_chat(chat_id):
        try:
            chat_data = get_chat_data(chat_id)
            return render_template("chat.html", 
                                  chat_id=chat_id,
                                  chat_info=chat_data["chat_info"],
                                  messages=chat_data["messages"],
                                  images=chat_data["images"],
                                  files=chat_data["files"])
        except Exception as e:
            return f"Error: {str(e)}", 500
    
    @app.route("/api/chat/<int:chat_id>/messages", methods=["GET"])
    def get_chat_messages(chat_id):
        try:
            chat_data = get_chat_data(chat_id)
            return jsonify(chat_data["messages"])
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/chat/<int:chat_id>/send", methods=["POST"])
    def send_message(chat_id):
        """Endpoint to send a new message (for future implementation)"""
        # This is a placeholder for future functionality
        return jsonify({"status": "not implemented"}), 501
    
    # List all chats
    @app.route("/", methods=["GET"])
    def list_chats():
        db_location = path + "history.db"
        con = sqlite3.connect(db_location)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        
        cur.execute("SELECT * FROM chats ORDER BY chat_id DESC")
        chats = [dict(row) for row in cur.fetchall()]
        con.close()
        
        return render_template("chats.html", chats=chats)
    
    app.run(debug=True)

if __name__ == "__main__":
    thing()