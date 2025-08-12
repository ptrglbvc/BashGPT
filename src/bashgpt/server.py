from flask import Flask, render_template, jsonify, request, Response
from bashgpt.main import path
import os
import sqlite3
import base64
from bashgpt.chat import (
    chat,
    load_chat,
    add_message_to_chat,
    save_chat,
    reset_chat,
    defaults,
    change_model,
    update_chat_ids,
    export_chat_by_id,
    export_all_chats,
    import_chat_data,
)
from bashgpt.api import get_response
from bashgpt.data_loader import data_loader
from bashgpt.load_defaults import load_defaults # Import load_defaults
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

def sanitize_images(images):
    """
    Ensure all images are properly formatted before sending to frontend.
    This checks if the image content is properly base64 encoded and formats accordingly.
    """
    sanitized_images = []
    
    for idx, image in enumerate(images):
        # Create a copy of the image dict to avoid modifying the original
        sanitized_image = image.copy()
        
        # Ensure message_idx exists and is an integer
        if 'message_idx' not in sanitized_image:
            continue
            
        # Convert message_idx to integer if it's not already
        try:
            sanitized_image['message_idx'] = int(sanitized_image['message_idx'])
        except (ValueError, TypeError):
            continue
        
        # Ensure content is a valid base64 string
        content = image.get('content', '')
        try:
            # Try to decode the content to check if it's valid base64
            if not content:
                continue
                
            # Try base64 decoding (this will fail if not valid base64)
            base64.b64decode(content)
            # If we get here, the content is valid base64
            sanitized_image['content'] = content
        except Exception as e:
            # If there's an error, try to re-encode the content properly
            try:
                # If it's bytes, encode to base64
                if isinstance(content, bytes):
                    sanitized_image['content'] = base64.b64encode(content).decode('utf-8')
                # If it's a string that's not base64, try to encode it
                else:
                    sanitized_image['content'] = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            except Exception:
                # If all else fails, skip this image
                continue
        
        # Ensure extension is valid
        if 'extension' not in sanitized_image or not sanitized_image['extension']:
            sanitized_image['extension'] = 'png'  # Default to PNG if no extension
            
        # Add the sanitized image to our list
        sanitized_images.append(sanitized_image)
    
    return sanitized_images

def prepare_messages_for_template(messages):
    """
    Add message_id to each message based on its position in the array.
    This ensures that images can correctly reference their associated message.
    """
    prepared_messages = []
    for idx, message in enumerate(messages):
        # Create a copy of the message
        prepared_message = message.copy()
        # Add message_id field that matches the index
        prepared_message["message_id"] = idx
        prepared_messages.append(prepared_message)
    return prepared_messages

def map_message_idx_to_id(images, messages):
    """
    Create a mapping from message_idx (from database) to message_id (for template).
    This handles cases where message indexes might not be sequential or aligned.
    
    In the database, message_idx often refers to the length of all_messages 
    at the time the image was added, while in the template, message_id is 
    the sequential position in the current messages array.
    """
    mapped_images = []
    for image in images:
        img_copy = image.copy()
        # message_idx is already validated as an integer in sanitize_images
        message_idx = img_copy.get('message_idx', -1)
        
        # If message_idx is out of range, skip this image
        if message_idx >= len(messages) or message_idx < 0:
            continue
            
        # Assign the correct message_id from the template's perspective
        img_copy['message_idx'] = message_idx  # message_id in template corresponds to index
        mapped_images.append(img_copy)
    
    return mapped_images

def server():
    app = Flask(__name__,
                template_folder=os.path.join(path, "html"),
                static_folder=os.path.join(path, "static"))


    @app.route("/chat/<int:chat_id>", methods=["GET"])
    @with_db
    def get_chat(con, cur, chat_id):
        try:
            # Reload models, modes, providers, defaults on every request
            modes, models, providers = data_loader()
            defaults_data = load_defaults(path) # Use load_defaults function
            load_chat(cur, chat_id)
            # Prepare messages by adding message_id
            prepared_messages = prepare_messages_for_template(chat["all_messages"])
            # Sanitize images before sending to template
            sanitized_images = sanitize_images(chat["images"])
            # Map message_idx to message_id
            mapped_images = map_message_idx_to_id(sanitized_images, prepared_messages)
            
            return render_template("chat.html",
                                chat_id=chat_id,
                                chat_info=chat,
                                messages=prepared_messages,
                                images=mapped_images,
                                files=chat["files"],
                                models=models,
                                modes=modes,
                                providers=providers,
                                defaults=defaults_data)
        except Exception as e:
            return f"Error: {str(e)}", 500


    @app.route("/", methods=["GET"])
    @with_db
    def list_chats(con, cur):
        # Reload models, modes, providers, defaults on every request
        modes, models, providers = data_loader()
        defaults_data = load_defaults(path) # Use load_defaults function
        reset_chat()
        cur.execute("SELECT * FROM chats ORDER BY chat_id DESC LIMIT 3")
        chats = [dict(row) for row in cur.fetchall()]
        # Prepare messages by adding message_id
        prepared_messages = prepare_messages_for_template(chat["all_messages"])
        # Sanitize images before sending to template
        sanitized_images = sanitize_images(chat["images"])
        # Map message_idx to message_id
        mapped_images = map_message_idx_to_id(sanitized_images, prepared_messages)
        
        return render_template("home.html", 
                               chat_info=chat,
                               messages=prepared_messages,
                               images=mapped_images,
                               files=chat["files"],
                               chats=chats,
                               models=models,
                               modes=modes,
                               providers=providers,
                               defaults=defaults_data)


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
        add_message_to_chat("assistant", "") 
        def generate():
            try:
                text_stream = get_response()

                for char in text_stream:
                    chat["all_messages"][-1]["content"] += char
                    yield char
                
                # Mark response as complete before saving
                response_complete[0] = True
            except Exception as e:
                # On error, if the last assistant message is empty, remove it; otherwise keep partial content
                try:
                    if chat["all_messages"] and chat["all_messages"][-1]["role"] == "assistant":
                        if not chat["all_messages"][-1]["content"]:
                            chat["all_messages"].pop()
                except Exception:
                    pass
                # Mark response as incomplete and emit error marker
                response_complete[0] = False
                yield f"__ERROR__:{str(e)}"

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

    @app.route("/api/export_chat/<int:chat_id>", methods=["GET"])
    @with_db
    def export_chat_route(con, cur, chat_id):
        try:
            data = export_chat_by_id(cur, chat_id)
            import json
            payload = json.dumps(data, indent=2)
            resp = Response(payload, mimetype="application/json")
            resp.headers["Content-Disposition"] = f"attachment; filename=chat-{chat_id}.json"
            return resp
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/export_all", methods=["GET"])
    @with_db
    def export_all_route(con, cur):
        try:
            data = export_all_chats(cur)
            import json
            payload = json.dumps(data, indent=2)
            resp = Response(payload, mimetype="application/json")
            resp.headers["Content-Disposition"] = "attachment; filename=chats-export.json"
            return resp
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/import", methods=["POST"])  # accepts multipart or json
    @with_db
    def import_route(con, cur):
        try:
            import json
            # Prefer file upload if present
            if "file" in request.files:
                file = request.files["file"]
                text = file.read().decode("utf-8")
                data = json.loads(text)
            else:
                # JSON body
                data = request.get_json(force=True, silent=False)

            new_ids = import_chat_data(con, cur, data)
            return jsonify({"success": True, "chat_ids": new_ids})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/regenerate", methods=["GET","POST"])
    def regenerate():
        data = request.get_json()
        idx = data["index"]
        
        # For streaming, we need to manage DB without the generator
        con = get_db_connection()
        cur = con.cursor()
        
        # Create a reference to hold the complete response
        response_complete = [False]
        
        def generate():
            try:
                old_content = chat["all_messages"][idx]["content"]
                chat["all_messages"][idx]["content"] = ""
                text_stream = get_response(messages=chat["all_messages"][:idx])

                for char in text_stream:
                    chat["all_messages"][idx]["content"] += char
                    yield char
                
                # Mark response as complete before saving
                response_complete[0] = True
            except Exception as e:
                # Restore previous content on error
                try:
                    chat["all_messages"][idx]["content"] = old_content
                except Exception:
                    pass
                # Mark response as incomplete and emit error marker
                response_complete[0] = False
                yield f"__ERROR__:{str(e)}"

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

    @app.route("/api/continue", methods=["GET","POST"])
    def continue_response():
        data = request.get_json()
        idx = data["index"]
        
        # For streaming, we need to manage DB without the generator
        con = get_db_connection()
        cur = con.cursor()
        
        # Create a reference to hold the complete response
        response_complete = [False]
        
        def generate():
            try:
                # Continue from this message
                current_content = chat["all_messages"][idx]["content"]
                messages_so_far = chat["all_messages"][:idx+1]
                
                text_stream = get_response(messages=messages_so_far)

                for char in text_stream:
                    chat["all_messages"][idx]["content"] += char
                    yield char
                
                # Mark response as complete before saving
                response_complete[0] = True
            except Exception as e:
                # Restore original content on error
                try:
                    chat["all_messages"][idx]["content"] = current_content
                except Exception:
                    pass
                # Mark response as incomplete and emit error marker
                response_complete[0] = False
                yield f"__ERROR__:{str(e)}"

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
        # Reload modes on every request
        modes, models, providers = data_loader()
        defaults_data = load_defaults(path) # Use load_defaults function
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
        
    @app.route("/api/update_message", methods=["POST"])
    @with_db
    def update_message(con, cur):
        data = request.get_json()
        idx = data["index"]
        new_content = data["content"]
        
        # Load the chat if not already loaded
        if 'chat_id' in data:
            load_chat(cur, data['chat_id'])
            
        # Update the message content
        chat["all_messages"][idx]["content"] = new_content
        
        # Save the updated chat
        save_chat(con, cur)
        
        return jsonify({"success": True})
        
    @app.route("/api/delete_message", methods=["POST"])
    @with_db
    def delete_message(con, cur):
        data = request.get_json()
        idx = data["index"]
        
        # Load the chat if not already loaded
        if 'chat_id' in data:
            load_chat(cur, data['chat_id'])
            
        # Remove the message from the chat
        if idx < len(chat["all_messages"]):
            del chat["all_messages"][idx]
            
            # Save the updated chat
            save_chat(con, cur)
            
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Message index out of range"}), 400

    @app.route("/api/change_settings", methods=["POST"])
    @with_db
    def change_settings(con, cur):
        # Reload models and providers on every request
        modes, models, providers = data_loader()
        defaults_data = load_defaults(path) # Use load_defaults function
        data = request.get_json()
        
        # Handle model changes
        if "model" in data:
            model_name = data["model"]
            
            # Find the model in available models
            selected_model = None
            for model in models:
                if model["name"] == model_name or model["shortcut"] == model_name:
                    selected_model = model
                    break
            
            if selected_model:
                change_model(selected_model, providers)
                
                # If chat is loaded, save the changes
                if chat["is_loaded"]:
                    save_chat(con, cur)
                
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Model not found"}), 400
        
        # Handle generation parameter changes
        settings_updated = False
        if "temperature" in data:
            chat["temperature"] = float(data["temperature"])
            settings_updated = True
            
        if "frequency_penalty" in data:
            chat["frequency_penalty"] = float(data["frequency_penalty"])
            settings_updated = True
            
        if "max_tokens" in data:
            chat["max_tokens"] = int(data["max_tokens"])
            settings_updated = True
        
        if settings_updated and chat["is_loaded"]:
            save_chat(con, cur)
            return jsonify({"success": True})
        
        return jsonify({"success": False, "error": "No settings specified"}), 400

    @app.route("/api/get_models", methods=["GET"])
    def get_models():
        # Reload models on every request
        modes, models, providers = data_loader()
        return jsonify(models)

    @app.route("/api/get_chats", methods=["GET"])
    @with_db
    def get_chats(con, cur):
        try:
            # Get all chats ordered by most recent first
            cur.execute("""
                SELECT chat_id, description, model, provider
                FROM chats 
                ORDER BY chat_id DESC
            """)
            chats = [dict(row) for row in cur.fetchall()]
            return jsonify(chats)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/get_system_message", methods=["GET"])
    @with_db
    def get_system_message(con, cur):
        # If the chat is not loaded or has no messages, return empty
        if not chat["is_loaded"] or not chat["all_messages"]:
            return jsonify({"message": "", "success": True})
        
        # Find the first system message if it exists
        system_message = ""
        for message in chat["all_messages"]:
            if message["role"] == "system":
                system_message = message["content"]
                break
                
        return jsonify({"message": system_message, "success": True})
        
    @app.route("/api/update_system_message", methods=["POST"])
    @with_db
    def update_system_message(con, cur):
        data = request.get_json()
        new_content = data["content"]
        
        # If chat is not loaded, can't update
        if not chat["is_loaded"]:
            return jsonify({"success": False, "error": "No active chat"}), 400
            
        # Check if system message exists
        system_found = False
        for i, message in enumerate(chat["all_messages"]):
            if message["role"] == "system":
                chat["all_messages"][i]["content"] = new_content
                system_found = True
                break
                
        # If no system message exists, add one at the beginning
        if not system_found:
            chat["all_messages"].insert(0, {"role": "system", "content": new_content})
        
        # Save the updated chat
        save_chat(con, cur)
        
        return jsonify({"success": True})

    @app.route("/api/delete_chat/<int:chat_id>", methods=["DELETE"])
    @with_db
    def delete_chat_route(con, cur, chat_id):
        try:
            # Delete chat messages
            cur.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat_id,))
            # Delete chat metadata
            cur.execute("DELETE FROM chats WHERE chat_id=?", (chat_id,))
            # Delete associated images
            cur.execute("DELETE FROM images WHERE chat_id=?", (chat_id,))
            # Delete associated files
            cur.execute("DELETE FROM files WHERE chat_id=?", (chat_id,))
            con.commit()
            
            # Update chat IDs to keep them sequential
            update_chat_ids(con, cur)
            
            return jsonify({"success": True})
        except Exception as e:
            con.rollback()
            return jsonify({"success": False, "message": str(e)}), 500

    @app.route("/api/rename_chat", methods=["POST"])
    @with_db
    def rename_chat(con, cur):
        data = request.get_json()
        chat_id = data.get("chat_id")
        new_name = data.get("new_name", "").strip()
        
        if not chat_id or not new_name:
            return jsonify({"success": False, "message": "Missing chat ID or name"}), 400
            
        try:
            # Update chat description
            cur.execute("UPDATE chats SET description = ? WHERE chat_id = ?", (new_name, chat_id))
            con.commit()
            
            return jsonify({"success": True})
        except Exception as e:
            con.rollback()
            return jsonify({"success": False, "message": str(e)}), 500

    # Run without debug mode when called from another thread
    # to avoid signal handling errors
    app.run(debug=False, host='127.0.0.1', port=5000)

if __name__ == "__main__":
    # Only use debug mode when run directly, not from a thread
    server()