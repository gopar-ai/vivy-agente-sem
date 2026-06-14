import os
import socket
import asyncio
import json
import time
import uuid

# Railway resuelve DNS via IPv6 primero, lo que rompe la conexion a la API
# de OpenAI ("Connection error"). Forzamos resolucion solo IPv4.
_orig_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_ipv4(host, *args, **kwargs):
    return [
        ai for ai in _orig_getaddrinfo(host, *args, **kwargs)
        if ai[0] == socket.AF_INET
    ]


socket.getaddrinfo = _getaddrinfo_ipv4

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

if not os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN'):
    ads_env_path = os.path.expanduser('~/.google_ads_credentials.env')
    if os.path.exists(ads_env_path):
        with open(ads_env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip())

from character import root_agent, execute_confirmed_action
import memory
import conversations_db

app = Flask(__name__, template_folder='templates')

memory.init_db()
conversations_db.init_db()

runner = InMemoryRunner(agent=root_agent, app_name='ai_vivy')

APP_NAME = 'ai_vivy'
USER_ID = 'detecta_user'


def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


async def create_conversation():
    session_id = str(uuid.uuid4())
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id,
        state=memory.get_all_preferences(),
    )
    conversations_db.create_conversation(session_id, "Nueva conversacion")
    conversations_db.set_current_session(session_id)
    return session_id


async def ensure_conversation():
    session_id = conversations_db.get_current_session()
    if session_id is None:
        session_id = await create_conversation()
    return session_id


async def load_conversations():
    for conv in conversations_db.get_all():
        await runner.session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=conv['id'],
            state=memory.get_all_preferences(),
        )


get_event_loop().run_until_complete(load_conversations())


async def run_agent(message: str, files=None) -> str:
    session_id = await ensure_conversation()

    if conversations_db.get_title(session_id) == "Nueva conversacion" and message.strip():
        title = message.strip().replace("\n", " ")
        title = (title[:40] + "...") if len(title) > 40 else title
        conversations_db.update_title(session_id, title)

    parts = []
    for file in (files or []):
        parts.append(types.Part.from_bytes(data=file.read(), mime_type=file.mimetype))
    if message.strip():
        parts.append(types.Part(text=message))
    if not parts:
        parts.append(types.Part(text=""))

    content = types.Content(role='user', parts=parts)

    final_response = ""
    tool_calls = []
    metrics = None
    confirmation = None

    METRIC_TOOLS = ('get_campaign_metrics', 'get_keyword_performance')

    async for event in runner.run_async(
        user_id=USER_ID, session_id=session_id, new_message=content
    ):
        for fc in event.get_function_calls():
            tool_calls.append(fc.name)

        for fr in event.get_function_responses():
            response = fr.response or {}
            if response.get('type') == 'confirmation':
                confirmation = response
            elif fr.name in METRIC_TOOLS:
                try:
                    parsed = json.loads(response.get('result', ''))
                    if isinstance(parsed, list) and parsed and 'error' not in parsed[0]:
                        metrics = parsed
                except (ValueError, TypeError):
                    pass

        if event.is_final_response() and event.content and event.content.parts:
            final_response = event.content.parts[0].text

    final_response = final_response or "Vivy no pudo generar una respuesta."

    if message.strip():
        conversations_db.save_message(str(uuid.uuid4()), session_id, 'user', message)
    conversations_db.save_message(str(uuid.uuid4()), session_id, 'model', final_response)

    return {
        'text': final_response,
        'tool_calls': tool_calls,
        'metrics': metrics,
        'confirmation': confirmation,
    }


CACHE_BUST = str(int(time.time()))


@app.route('/')
def index():
    return render_template('index.html', cache_bust=CACHE_BUST)


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
        result = loop.run_until_complete(run_agent(user_message, files))
        return jsonify({
            'response': result['text'],
            'tool_calls': result['tool_calls'],
            'metrics': result['metrics'],
            'confirmation': result['confirmation'],
        })
    except Exception as e:
        return jsonify({'response': f"Error en Vivy: {str(e)}"}), 500


@app.route('/messages', methods=['GET'])
def get_messages():
    session_id = request.args.get('session_id') or request.args.get('id')
    if not conversations_db.exists(session_id):
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404

    return jsonify({'messages': conversations_db.get_messages(session_id)})


@app.route('/confirm_action', methods=['POST'])
def confirm_action():
    data = request.get_json() or {}
    action_id = data.get('action_id')
    message = execute_confirmed_action(action_id)
    return jsonify({'status': 'ok', 'message': message})


@app.route('/preferences', methods=['GET'])
def get_preferences():
    return jsonify(memory.get_all_preferences())


@app.route('/preferences', methods=['POST'])
def update_preferences():
    data = request.get_json() or {}
    for key, value in data.items():
        memory.set_preference(key, value)
    return jsonify({'status': 'ok'})


@app.route('/conversations', methods=['GET'])
def list_conversations():
    return jsonify({
        'current': conversations_db.get_current_session(),
        'conversations': conversations_db.get_all(),
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
    data = request.get_json() or {}
    session_id = data.get('id')
    if not conversations_db.exists(session_id):
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404
    conversations_db.set_current_session(session_id)
    return jsonify({'status': 'ok'})


@app.route('/rename_chat', methods=['POST'])
def rename_chat():
    data = request.get_json() or {}
    session_id = data.get('id')
    title = (data.get('title') or '').strip()
    if not conversations_db.exists(session_id):
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404
    if title:
        conversations_db.update_title(session_id, title)
    return jsonify({'status': 'ok'})


@app.route('/pin_chat', methods=['POST'])
def pin_chat():
    data = request.get_json() or {}
    session_id = data.get('id')
    if not conversations_db.exists(session_id):
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404
    pinned = conversations_db.toggle_pinned(session_id)
    return jsonify({'status': 'ok', 'pinned': pinned})


@app.route('/delete_chat', methods=['POST'])
def delete_chat():
    data = request.get_json() or {}
    session_id = data.get('id')
    if not conversations_db.exists(session_id):
        return jsonify({'status': 'error', 'message': 'unknown conversation'}), 404

    conversations_db.delete_conversation(session_id)
    conversations_db.delete_messages(session_id)

    current = conversations_db.get_current_session()
    if current == session_id:
        remaining = conversations_db.get_all()
        current = remaining[0]['id'] if remaining else None
        conversations_db.set_current_session(current)

    return jsonify({'status': 'ok', 'current': current})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host='0.0.0.0', port=port, debug=debug)
