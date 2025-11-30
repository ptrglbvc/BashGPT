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
    change_model,
    update_chat_ids,
    export_chat_by_id,
    export_all_chats,
    import_chat_data,
)
from bashgpt.api import get_response
from bashgpt.data_loader import data_loader
from bashgpt.load_defaults import load_defaults
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
    sanitized_images = []

    for _, image in enumerate(images):
        sanitized_image = image.copy()

        if 'message_idx' not in sanitized_image:
            continue

        try:
            sanitized_image['message_idx'] = int(sanitized_image['message_idx'])
        except (ValueError, TypeError):
            continue

        content = image.get('content', '')
        try:
            if not content:
                continue

            base64.b64decode(content)
            sanitized_image['content'] = content
        except Exception as _:
            try:
                if isinstance(content, bytes):
                    sanitized_image['content'] = base64.b64encode(content).decode('utf-8')
                else:
                    sanitized_image['content'] = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            except Exception:
                continue

        if 'extension' not in sanitized_image or not sanitized_image['extension']:
            sanitized_image['extension'] = 'png'

        sanitized_images.append(sanitized_image)

    return sanitized_images

def prepare_messages_for_template(messages):
    prepared_messages = []
    for idx, message in enumerate(messages):
        prepared_message = message.copy()
        prepared_message["message_id"] = idx
        # Ensure cache_control is present for template
        if "cache_control" not in prepared_message:
            prepared_message["cache_control"] = False
        prepared_messages.append(prepared_message)
    return prepared_messages

def map_message_idx_to_id(images, messages):
    mapped_images = []
    for image in images:
        img_copy = image.copy()
        message_idx = img_copy.get('message_idx', -1)

        if message_idx >= len(messages) or message_idx < 0:
            continue

        img_copy['message_idx'] = message_idx
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
            modes, models, providers = data_loader()
            defaults_data = load_defaults(path)
            load_chat(cur, chat_id)
            prepared_messages = prepare_messages_for_template(chat["all_messages"])
            sanitized_images = sanitize_images(chat["images"])
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
        modes, models, providers = data_loader()
        defaults_data = load_defaults(path)
        reset_chat()
        cur.execute("SELECT * FROM chats ORDER BY chat_id DESC LIMIT 3")
        chats = [dict(row) for row in cur.fetchall()]
        prepared_messages = prepare_messages_for_template(chat["all_messages"])
        sanitized_images = sanitize_images(chat["images"])
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

        con = get_db_connection()
        cur = con.cursor()

        response_complete = [False]
        add_message_to_chat("assistant", "")
        def generate():
            try:
                text_stream = get_response()

                for char in text_stream:
                    chat["all_messages"][-1]["content"] += char
                    yield char

                response_complete[0] = True
            except Exception as e:
                try:
                    if chat["all_messages"] and chat["all_messages"][-1]["role"] == "assistant":
                        if not chat["all_messages"][-1]["content"]:
                            chat["all_messages"].pop()
                except Exception:
                    pass
                response_complete[0] = False
                yield f"__ERROR__:{str(e)}"

        response = Response(generate(), mimetype="text/plain")

        @response.call_on_close
        def on_close():
            if response_complete[0]:
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

    @app.route("/api/import", methods=["POST"])
    @with_db
    def import_route(con, cur):
        try:
            import json
            if "file" in request.files:
                file = request.files["file"]
                text = file.read().decode("utf-8")
                data = json.loads(text)
            else:
                data = request.get_json(force=True, silent=False)

            new_ids = import_chat_data(con, cur, data)
            return jsonify({"success": True, "chat_ids": new_ids})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 400

    @app.route("/api/regenerate", methods=["GET","POST"])
    def regenerate():
        data = request.get_json()
        idx = data["index"]

        con = get_db_connection()
        cur = con.cursor()

        response_complete = [False]

        def generate():
            try:
                old_content = chat["all_messages"][idx]["content"]
                chat["all_messages"][idx]["content"] = ""
                text_stream = get_response(messages=chat["all_messages"][:idx])

                for char in text_stream:
                    chat["all_messages"][idx]["content"] += char
                    yield char

                response_complete[0] = True
            except Exception as e:
                try:
                    chat["all_messages"][idx]["content"] = old_content
                except Exception:
                    pass
                response_complete[0] = False
                yield f"__ERROR__:{str(e)}"

        response = Response(generate(), mimetype="text/plain")

        @response.call_on_close
        def on_close():
            if response_complete[0]:
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

        con = get_db_connection()
        cur = con.cursor()

        response_complete = [False]

        def generate():
            try:
                current_content = chat["all_messages"][idx]["content"]
                messages_so_far = chat["all_messages"][:idx+1]

                text_stream = get_response(messages=messages_so_far)

                for char in text_stream:
                    chat["all_messages"][idx]["content"] += char
                    yield char

                response_complete[0] = True
            except Exception as e:
                try:
                    chat["all_messages"][idx]["content"] = current_content
                except Exception:
                    pass
                response_complete[0] = False
                yield f"__ERROR__:{str(e)}"

        response = Response(generate(), mimetype="text/plain")

        @response.call_on_close
        def on_close():
            if response_complete[0]:
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
        modes, models, providers = data_loader()
        defaults_data = load_defaults(path)
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

        if 'chat_id' in data:
            load_chat(cur, data['chat_id'])

        chat["all_messages"][idx]["content"] = new_content

        save_chat(con, cur)

        return jsonify({"success": True})
        
    @app.route("/api/toggle_cache", methods=["POST"])
    @with_db
    def toggle_cache(con, cur):
        data = request.get_json()
        idx = data["index"]
        
        if 'chat_id' in data:
            load_chat(cur, data['chat_id'])
            
        if idx < len(chat["all_messages"]):
            # Toggle the boolean
            current_val = chat["all_messages"][idx].get("cache_control", False)
            chat["all_messages"][idx]["cache_control"] = not current_val
            
            save_chat(con, cur)
            
            return jsonify({
                "success": True, 
                "new_value": chat["all_messages"][idx]["cache_control"]
            })
        else:
            return jsonify({"success": False, "error": "Index out of range"}), 400

    @app.route("/api/delete_message", methods=["POST"])
    @with_db
    def delete_message(con, cur):
        data = request.get_json()
        idx = data["index"]

        if 'chat_id' in data:
            load_chat(cur, data['chat_id'])

        if idx < len(chat["all_messages"]):
            del chat["all_messages"][idx]

            save_chat(con, cur)

            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Message index out of range"}), 400

    @app.route("/api/branch", methods=["POST"])
    @with_db
    def branch_chat(con, cur):
        try:
            data = request.get_json()
            chat_id = data.get("chat_id")
            message_idx = data.get("index")

            if chat_id is None or message_idx is None:
                return jsonify({"success": False, "error": "Missing parameters"}), 400

            load_chat(cur, chat_id)

            cutoff = message_idx + 1
            if cutoff > len(chat["all_messages"]):
                return jsonify({"success": False, "error": "Invalid message index"}), 400

            chat["all_messages"] = chat["all_messages"][:cutoff]

            chat["images"] = [img for img in chat["images"] if img["message_idx"] < cutoff]
            chat["files"] = [f for f in chat["files"] if f["message_idx"] < cutoff]

            chat["id"] = None
            chat["is_loaded"] = False
            chat["description"] = (chat["description"] or "Chat") + " (Branch)"

            save_chat(con, cur)

            new_id = cur.execute("SELECT MAX(chat_id) FROM chats").fetchone()[0]

            return jsonify({"success": True, "chat_id": new_id})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/change_settings", methods=["POST"])
    @with_db
    def change_settings(con, cur):
        modes, models, providers = data_loader()
        defaults_data = load_defaults(path)
        data = request.get_json()

        if "theme" in data:
            theme = data["theme"].strip().lower()
            if theme not in ["chatgpt", "erp"]:
                return jsonify({"success": False, "error": "Invalid theme"}), 400
            defaults_path = path + "/defaults.json"
            defaults_data.setdefault("web", {})["theme"] = theme
            import json
            with open(defaults_path, "w") as f:
                json.dump(defaults_data, f, indent=4)
            return jsonify({"success": True})

        if "model" in data:
            model_name = data["model"]

            selected_model = None
            for model in models:
                if model["name"] == model_name or model["shortcut"] == model_name:
                    selected_model = model
                    break

            if selected_model:
                change_model(selected_model, providers)

                if chat["is_loaded"]:
                    save_chat(con, cur)

                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "error": "Model not found"}), 400

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
        modes, models, providers = data_loader()
        return jsonify(models)

    @app.route("/api/get_chats", methods=["GET"])
    @with_db
    def get_chats(con, cur):
        try:
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
        if not chat["is_loaded"] or not chat["all_messages"]:
            return jsonify({"message": "", "success": True})

        system_message = ""
        cache_status = False
        for message in chat["all_messages"]:
            if message["role"] == "system":
                system_message = message["content"]
                cache_status = message.get("cache_control", False)
                break

        return jsonify({"message": system_message, "cache_control": cache_status, "success": True})

    @app.route("/api/update_system_message", methods=["POST"])
    @with_db
    def update_system_message(con, cur):
        data = request.get_json()
        new_content = data["content"]
        # System message cache is usually handled separately in UI logic if needed,
        # but here we preserve existing unless explicit flag sent
        
        if not chat["is_loaded"]:
            return jsonify({"success": False, "error": "No active chat"}), 400

        system_found = False
        for i, message in enumerate(chat["all_messages"]):
            if message["role"] == "system":
                chat["all_messages"][i]["content"] = new_content
                system_found = True
                break

        if not system_found:
            chat["all_messages"].insert(0, {"role": "system", "content": new_content, "cache_control": False})

        save_chat(con, cur)

        return jsonify({"success": True})

    @app.route("/api/delete_chat/<int:chat_id>", methods=["DELETE"])
    @with_db
    def delete_chat_route(con, cur, chat_id):
        try:
            cur.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat_id,))
            cur.execute("DELETE FROM chats WHERE chat_id=?", (chat_id,))
            cur.execute("DELETE FROM images WHERE chat_id=?", (chat_id,))
            cur.execute("DELETE FROM files WHERE chat_id=?", (chat_id,))
            con.commit()

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
            cur.execute("UPDATE chats SET description = ? WHERE chat_id = ?", (new_name, chat_id))
            con.commit()

            return jsonify({"success": True})
        except Exception as e:
            con.rollback()
            return jsonify({"success": False, "message": str(e)}), 500

    app.run(debug=False, host='127.0.0.1', port=5000)

if __name__ == "__main__":
    server()

