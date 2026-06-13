import os
import asyncio
import uuid

from flask import Flask, render_template, request, jsonify

from google.adk.runners import InMemoryRunner
from google.genai import types

if not os.environ.get('GEMINI_API_KEY'):
    key_path = os.path.expanduser('~/gemini_key.txt')
    if os.path.exists(key_path):
        with open(key_path) as f:
            os.environ['GEMINI_API_KEY'] = f.read().strip()

if not os.environ.get('OPENAI_API_KEY'):
    key_path = os.path.expanduser('~/openai_key.txt')
    if os.path.exists(key_path):
        with open(key_path) as f:
            os.environ['OPENAI_API_KEY'] = f.read().strip()

from character import root_agent

app = Flask(__name__, template_folder='templates')

runner = InMemoryRunner(agent=root_agent, app_name='ai_vivy')

APP_NAME = 'ai_vivy'
USER_ID = 'detecta_user'

# Ordered list of conversation ids (display order is computed from this + pinned flag).
CONVERSATION_ORDER = []
# session_id -> {"title": str, "pinned": bool}
CONVERSATIONS = {}
CURRENT_SESSION_ID = None


def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


async def create_conversation():
    global CURRENT_SESSION_ID
    session_id = str(uuid.uuid4())
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )
    CONVERSATIONS[session_id] = {"title": "Nueva conversacion", "pinned": False}
    CONVERSATION_ORDER.insert(0, session_id)
    CURRENT_SESSION_ID = session_id
    return session_id


async def ensure_conversation():
    global CURRENT_SESSION_ID
    if CURRENT_SESSION_ID is None:
        await create_conversation()
    return CURRENT_SESSION_ID


async def run_agent(message: str, files=None) -> str:
    session_id = await ensure_conversation()

    if CONVERSATIONS[session_id]["title"] == "Nueva conversacion" and message.strip():
        title = message.strip().replace("\n", " ")
        CONVERSATIONS[session_id]["title"] = (title[:40] + "...") if len(title) > 40 else title

    parts = []
    for file in (files or []):
        parts.append(types.Part.from_bytes(data=file.read(), mime_type=file.mimetype))
    if message.strip():
        parts.append(types.Part(text=message))
    if not parts:
        parts.append(types.Part(text=""))

    content = types.Content(role='user', parts=parts)

    final_response = ""
    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=content
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    return final_response or "Vivy no pudo generar una respuesta."


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat():
    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
            user_message = request.form.get('message', '')
            files = request.files.getlist('files')
        else:
            data = request.get_json() or {}
            user_message = data.get('message', '')
            files = []

        loop = get_event_loop()
        respuesta = loop.run_until_complete(run_agent(user_message, files))
        return jsonify({'response': respuesta})
    except Exception as e:
        return jsonify({'response': f"Error en Vivy: {str(e)}"}), 500


@app.route('/conversations', methods=['GET'])
def list_conversations():
    ordered = sorted(
        CONVERSATION_ORDER,
        key=lambda cid: (not CONVERSATIONS[cid]['pinned'], CONVERSATION_ORDER.index(cid)),
    )
    return jsonify({
        'current': CURRENT_SESSION_ID,
        'conversations': [
            {'id': cid, 'title': CONVERSATIONS[cid]['title'], 'pinned': CONVERSATIONS[cid]['pinned']}
            for cid in ordered
        ],
    })


@app.route('/new_chat', methods=['POST'])
def new_chat():
    try:
        loop = get_event_loop()
        session_id = loop.run_until_complete(create_conversation())
        return jsonify({'id': session_id})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/switch_chat', methods=['POST'])
def switch_chat():
    global CURRENT_SESSION_ID
    data = request.get_json() or {}
    session_id = data.get('id')
    if session_id not in CONVERSATIONS:
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404
    CURRENT_SESSION_ID = session_id
    return jsonify({'status': 'ok'})


@app.route('/rename_chat', methods=['POST'])
def rename_chat():
    data = request.get_json() or {}
    session_id = data.get('id')
    title = (data.get('title') or '').strip()
    if session_id not in CONVERSATIONS:
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404
    if title:
        CONVERSATIONS[session_id]['title'] = title
    return jsonify({'status': 'ok'})


@app.route('/pin_chat', methods=['POST'])
def pin_chat():
    data = request.get_json() or {}
    session_id = data.get('id')
    if session_id not in CONVERSATIONS:
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404
    CONVERSATIONS[session_id]['pinned'] = not CONVERSATIONS[session_id]['pinned']
    return jsonify({'status': 'ok', 'pinned': CONVERSATIONS[session_id]['pinned']})


@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    global CURRENT_SESSION_ID
    data = request.get_json() or {}
    session_id = data.get('id')
    if session_id not in CONVERSATIONS:
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404

    CONVERSATIONS.pop(session_id)
    CONVERSATION_ORDER.remove(session_id)

    if CURRENT_SESSION_ID == session_id:
        CURRENT_SESSION_ID = CONVERSATION_ORDER[0] if CONVERSATION_ORDER else None

    return jsonify({'status': 'ok', 'current': CURRENT_SESSION_ID})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
