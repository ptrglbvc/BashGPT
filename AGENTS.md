# Project Structure Overview for AI Agents

## Web Interface
- **Main server**: `src/bashgpt/server.py` - Flask-based web server handling routes and API endpoints
- **HTML templates**: `src/bashgpt/html/` - Contains `home.html`, `chat.html`, and `layout.html`
- **Static assets**: `src/bashgpt/static/` - CSS, JavaScript, and other static files

## Key Components
- **Chat management**: `src/bashgpt/chat.py` - Core chat functionality including import/export operations
- **Server routes**: Defined in `server.py` with endpoints for chat operations, import/export, and settings
- **Template structure**: Uses Jinja2 templating with a base `layout.html` extended by page-specific templates

## Import Functionality
- **Frontend**: Import handlers in `home.html` handle file uploads and API calls
- **Backend**: `/api/import` endpoint in `server.py` processes imports using `import_chat_data()` from `chat.py`
- **Response**: Import operation returns `chat_ids` of newly created chats, allowing frontend to redirect to imported content