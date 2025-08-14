# Project Structure Overview for AI Agents

## Web Interface

-   **Main server**: `src/bashgpt/server.py` - Flask-based web server handling routes and API endpoints
-   **HTML templates**: `src/bashgpt/html/` - Contains `home.html`, `chat.html`, and `layout.html`
-   **Static assets**: `src/bashgpt/static/` - CSS, JavaScript, and other static files

## Key Components

-   **Chat management**: `src/bashgpt/chat.py` - Core chat functionality including import/export operations
-   **Server routes**: Defined in `server.py` with endpoints for chat operations, import/export, and settings
-   **Template structure**: Uses Jinja2 templating with a base `layout.html` extended by page-specific templates

## Import Functionality

-   **Frontend**: Import handlers in `home.html` handle file uploads and API calls
-   **Backend**: `/api/import` endpoint in `server.py` processes imports using `import_chat_data()` from `chat.py`
-   **Response**: Import operation returns `chat_ids` of newly created chats, allowing frontend to redirect to imported content

## Web Interface Commands

The web interface supports several slash commands that can be entered in the chat input field:

-   **/model [model_name]** - Change the current AI model (supports both full model names and shortcuts)

    -   Implementation: Shared `changeModelCommand()` function in `layout.html`
    -   Backend: `/api/change_settings` endpoint in `server.py`

-   **/temp [value]** or **/temperature [value]** - Set the temperature parameter (0.0 to 2.0)

    -   Implementation: Shared `changeTemperatureCommand()` function in `layout.html`
    -   Backend: `/api/change_settings` endpoint in `server.py`

-   **/rg** - Regenerate the last assistant message
    -   Implementation: Shared `regenerateLastMessage()` function in `layout.html`
    -   Backend: `/api/regenerate` endpoint in `server.py`
    -   Note: Only works in active chat sessions, provides appropriate error messages on home screen

## Notification System

A sliding notification system provides user feedback for various operations:

-   **Implementation**: Shared `showNotification()` function in `layout.html`
-   **Styling**: CSS in `src/bashgpt/static/css/style.css` (`.notification` class)
-   **Features**:
    -   Slides in from the upper right corner with smooth 0.2s ease-in-out transition
    -   Automatically disappears after 2 seconds by default
    -   Supports HTML content (used for colored model names and temperature values)
    -   Uses the app's primary color (`var(--primary-color)`) for important values
-   **Usage**: Called by command functions and other UI operations throughout the web interface

## Provider Error Handling → Notifications (Web)

Short overview of the error-to-notification flow implemented for model/provider failures:

-   **Backend (Flask streaming)**

    -   Endpoints affected: `/api/answer`, `/api/regenerate`, `/api/continue` in `src/bashgpt/server.py`.
    -   On provider exceptions, the server streams a single chunk starting with the marker `__ERROR__:` followed by the error message, then stops streaming.
    -   Chats are only saved when a response completes successfully. On error, nothing is persisted.
    -   Placeholder/partial content handling:
        -   New answer: if no content was produced, the placeholder assistant message is removed.
        -   Regenerate: previous message content is restored.
        -   Continue: original message content is kept; no partial error text is appended.
    -   Provider exceptions are raised by `get_response` in `src/bashgpt/api.py` (no more appending errors into messages at source).

-   **Frontend (stream consumers)**

    -   Implementation in `src/bashgpt/html/chat.html` within the stream loops for send/regenerate/continue.
    -   When a chunk starts with `__ERROR__:`, the UI:
        -   Shows a notification via `showNotification("Error: ...", 5000)` (5 seconds for errors).
        -   Cleans up the UI per operation (remove placeholder for new answers; restore previous content for regenerate; keep original for continue).
        -   Stops further processing of the stream.

-   **Notification details**

    -   Uses the shared `showNotification` from `layout.html`.
    -   Regular notifications typically use 2s; provider error notifications are explicitly 5s.

-   **CLI behavior**

    -   In `get_and_print_response` (`src/bashgpt/api.py`), CLI still alerts/prints provider errors and appends the error to the last assistant message to preserve terminal UX.

-   **Change tips**
    -   If you change the error marker string, update both `server.py` (generator error branches) and `chat.html` (stream readers) accordingly.
    -   Ensure `response_complete` stays False on error so failed generations don’t get saved.

## Command System

-   **Unified command handling**: `src/bashgpt/static/js/commands.js` - Centralized JavaScript file containing all web interface slash commands
-   **Command structure**: Commands are defined in a `COMMANDS` object with descriptions and handler functions
-   **Current commands**:
    -   `/help` - Display all available commands with descriptions (10s notification)
    -   `/model [model_name]` - Change the current AI model
    -   `/temp [value]` - Set temperature parameter (0.0 to 2.0)
    -   `/rg` - Regenerate the last assistant message (chat view only)
-   **Error handling**: Invalid commands show helpful error notifications with suggestion to use `/help`
-   **Extensibility**: New commands can be easily added to the `COMMANDS` object

## File Locations

-   **Command implementations**: `src/bashgpt/static/js/commands.js` (centralized), previously in `src/bashgpt/html/layout.html` (shared functions)
-   **Command parsing**: Individual page templates (`chat.html`, `home.html`) via `handleCommand()` function
-   **CSS styling**: `src/bashgpt/static/css/style.css`
-   **Backend endpoints**: `src/bashgpt/server.py`

## Architecture notes (brief)

-   **Chat state**: A single in-memory `chat` dict in `src/bashgpt/chat.py` holds the active session. Persistence uses SQLite via `save_chat`/`load_chat`. Images/files reference messages by `message_idx`; `server.py` sanitizes/maps for templates.
-   **Streaming pipeline**: `get_response()` (in `src/bashgpt/api.py`) yields token chunks per provider; Flask endpoints stream to the client; the frontend reads chunks to render Markdown, then applies Prism highlighting and adds copy buttons.
-   **Provider abstraction**: Selected via `chat['provider']`. Vision attachments differ per provider; file attachments are prepended to the user message content; system message may be augmented by `auto`/`bash`/`dalle`.
-   **Dynamic config**: `data_loader()` runs on requests to pick up live changes to models/providers/defaults. `change_model()` updates `chat` and persists when a chat is loaded.
