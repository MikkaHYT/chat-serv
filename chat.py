from flask import Flask, request, jsonify, render_template
import os
import base64
import uuid
import sqlite3
import time

app = Flask(__name__)

# Directory to store uploaded images
image_upload_dir = 'static/uploads'
os.makedirs(image_upload_dir, exist_ok=True)

# Initialize SQLite databases
db_file = 'chat.db'
private_db_file = 'private_chat.db'

def init_db():
    """Initialize the public chat database."""
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                profilePic TEXT,
                message TEXT NOT NULL,
                image TEXT,
                reactions TEXT
            )
        ''')
        conn.commit()

def init_private_db():
    """Initialize the private chat database."""
    with sqlite3.connect(private_db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                profilePic TEXT,
                message TEXT NOT NULL,
                image TEXT,
                reactions TEXT
            )
        ''')
        conn.commit()

# Initialize both databases
init_db()
init_private_db()

# Function to save a message to a database
def save_message_to_db(db_path, username, profilePic, message, image):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (username, profilePic, message, image)
            VALUES (?, ?, ?, ?)
        ''', (username, profilePic, message, image))
        conn.commit()
        return cursor.lastrowid

# Function to load messages from a database
def load_messages_from_db(db_path, last_id=None):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        if last_id is not None:
            cursor.execute('SELECT * FROM messages WHERE id > ? ORDER BY id ASC', (last_id,))
        else:
            cursor.execute('SELECT * FROM messages ORDER BY id ASC')
        rows = cursor.fetchall()
        return [{'id': row[0], 'username': row[1], 'profilePic': row[2], 'message': row[3], 'image': row[4]} for row in rows]

# Route to serve the public chat page
@app.route('/beta')
def chat():
    return render_template('chat.html')

# Route to serve the alt public chat page
@app.route('/')
def alt_chat():
    return render_template('chat-working-but-old.html')

# Route to serve the private chat page
@app.route('/private')
def private_chat():
    return render_template('private_chat.html')


# Long polling route to fetch edited messages for the public chat
@app.route('/poll-edited-messages', methods=['GET'])
def poll_edited_messages():
        last_check_time = request.args.get('last_check_time', None)
        try:
            if last_check_time is not None:
                last_check_time = float(last_check_time)
            else:
                return jsonify({'status': 'error', 'message': 'Invalid last_check_time'}), 400

            timeout = 30  # Maximum time to hold the request (in seconds)
            start_time = time.time()
            while time.time() - start_time < timeout:
                with sqlite3.connect(db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT id, username, profilePic, message, image
                        FROM messages
                        WHERE strftime('%s', last_updated) > ?
                    ''', (last_check_time,))
                    rows = cursor.fetchall()
                    if rows:
                        edited_messages = [
                            {'id': row[0], 'username': row[1], 'profilePic': row[2], 'message': row[3], 'image': row[4]}
                            for row in rows
                        ]
                        return jsonify(edited_messages)
                time.sleep(1)  # Wait for 1 second before checking again
            return jsonify([])  # Return an empty list if no edited messages
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid last_check_time'}), 400
### Rock Paper Scissors Game ###
# Route to handle starting a game
@app.route('/start-game', methods=['POST'])
def start_game():
        data = request.get_json(force=True)
        username = data.get('username')
        if username:
            # Save the player to a temporary in-memory list
            if not hasattr(app, 'waiting_players'):
                app.waiting_players = []
            app.waiting_players.append(username)
            return jsonify({'status': 'waiting'}), 200
        return jsonify({'status': 'error', 'message': 'Invalid username'}), 400

# Route to check for an opponent
@app.route('/check-opponent', methods=['GET'])
def check_opponent():
        if hasattr(app, 'waiting_players') and len(app.waiting_players) > 1:
            # Match the first two players in the waiting list
            player1 = app.waiting_players.pop(0)
            player2 = app.waiting_players.pop(0)
            return jsonify({'opponent': player2}), 200
        return jsonify({'opponent': None}), 200

# Route to handle playing the Rock-Paper-Scissors game
@app.route('/play-game', methods=['POST'])
def play_game():
            data = request.get_json()
            username = data.get('username')
            user_choice = data.get('choice')
            print(user_choice)
            choices = ['rock', 'paper', 'scissors']

            if username and user_choice in choices:
                
                opponent_choice = choices[uuid.uuid4().int % 3]

                # Determine the result
                if user_choice == opponent_choice:
                    result = 'It\'s a tie!'
                elif (user_choice == 'Rock' and opponent_choice == 'Scissors') or \
                     (user_choice == 'Paper' and opponent_choice == 'Rock') or \
                     (user_choice == 'Scissors' and opponent_choice == 'Paper'):
                    result = 'You win!'
                else:
                    result = 'You lose!'

                return jsonify({
                    'opponentChoice': opponent_choice,
                    'result': result
                }), 200

            return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
            # Route to handle syncing opponent choices and play stages
@app.route('/sync-game', methods=['POST'])
def sync_game():
                data = request.get_json()
                username = data.get('username')
                user_choice = data.get('choice')
                if not hasattr(app, 'game_sessions'):
                    app.game_sessions = {}

                # Check if the user is already in a game session
                for session_id, session in app.game_sessions.items():
                    if username in session['players']:
                        session['choices'][username] = user_choice
                        if len(session['choices']) == 2:
                            # Both players have made their choices, determine the result
                            player1, player2 = session['players']
                            choice1 = session['choices'][player1]
                            choice2 = session['choices'][player2]

                            if choice1 == choice2:
                                result = 'It\'s a tie!'
                            elif (choice1 == 'rock' and choice2 == 'scissors') or \
                                 (choice1 == 'paper' and choice2 == 'rock') or \
                                 (choice1 == 'scissors' and choice2 == 'paper'):
                                result = f'{player1} wins!'
                            else:
                                result = f'{player2} wins!'

                            # Return the results to both players
                            session['result'] = {
                                player1: {'opponentChoice': choice2, 'result': result},
                                player2: {'opponentChoice': choice1, 'result': result}
                            }
                            return jsonify(session['result'][username]), 200

                        # Wait for the opponent's choice
                        return jsonify({'status': 'waiting'}), 200

                # Create a new game session if no existing session is found
                session_id = str(uuid.uuid4())
                app.game_sessions[session_id] = {
                    'players': [username],
                    'choices': {}
                }
                return jsonify({'status': 'waiting'}), 200
# Route to handle sending a message to the public chat
@app.route('/send-message', methods=['POST'])
def send_message():
    data = request.get_json()
    if 'username' in data and 'message' in data:
        # Save the message to the public database
        new_message_id = save_message_to_db(
            db_file,
            username=data['username'],
            profilePic=data.get('profilePic', ''),
            message=data['message'],
            image=data.get('image', '')
        )
        new_message = {
            'id': new_message_id,
            'username': data['username'],
            'profilePic': data.get('profilePic', ''),
            'message': data['message'],
            'image': data.get('image', '')
        }
        return jsonify({'status': 'success', 'message': new_message}), 200
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to handle editing a message
@app.route('/edit-message', methods=['POST'])
def edit_message():
    data = request.get_json()
    if 'id' in data and 'message' in data:
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET message = ? WHERE id = ?', (data['message'], data['id']))
            conn.commit()
        return jsonify({'status': 'success', 'message': 'Message updated'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to fetch online users
@app.route('/fetch-online-users', methods=['GET'])
def fetch_online_users():
        if hasattr(app, 'online_users'):
            return jsonify({'onlineUsers': [{'username': user} for user in app.online_users]}), 200
        return jsonify({'onlineUsers': []}), 200

# Long polling route to fetch online users
@app.route('/poll-online-users', methods=['GET'])
def poll_online_users():
    timeout = 30  # Maximum time to hold the request (in seconds)
    start_time = time.time()
    initial_online_users = set(app.online_users) if hasattr(app, 'online_users') else set()

    while time.time() - start_time < timeout:
        current_online_users = set(app.online_users) if hasattr(app, 'online_users') else set()
        if current_online_users != initial_online_users:
            return jsonify({'onlineUsers': [{'username': user} for user in current_online_users]}), 200
        time.sleep(1)  # Wait for 1 second before checking again

    return jsonify({'onlineUsers': [{'username': user} for user in initial_online_users]}), 200

# Route to mark a user as online
@app.route('/mark-online', methods=['POST'])
def mark_online():
        data = request.get_json()
        if 'username' in data:
            if not hasattr(app, 'online_users'):
                app.online_users = set()
            app.online_users.add(data['username'])
            return jsonify({'status': 'success', 'message': f'{data["username"]} is now online.'}), 200
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to serve the admin page
@app.route('/admin')
def admin_page():
            return render_template('admin.html')

# Route to fetch all messages for admin management
@app.route('/admin/get-messages', methods=['GET'])
def admin_get_messages():
            with sqlite3.connect(db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM messages ORDER BY id ASC')
                rows = cursor.fetchall()
                messages = [
                    {'id': row[0], 'username': row[1], 'profilePic': row[2], 'message': row[3], 'image': row[4], 'reactions': row[5]}
                    for row in rows
                ]
            return jsonify(messages), 200

@app.route('/admin/erase-chat', methods=['POST'])
def erase_chat():
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages')
        conn.commit()
    return jsonify({'status': 'success', 'message': 'Chat erased'}), 200

# Route to delete a message by admin
@app.route('/admin/delete-message', methods=['POST'])
def admin_delete_message():
            data = request.get_json()
            if 'id' in data:
                with sqlite3.connect(db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute('DELETE FROM messages WHERE id = ?', (data['id'],))
                    conn.commit()
                return jsonify({'status': 'success', 'message': 'Message deleted by admin'}), 200
            return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to edit a message by admin
@app.route('/admin/edit-message', methods=['POST'])
def admin_edit_message():
            data = request.get_json()
            if 'id' in data and 'message' in data:
                with sqlite3.connect(db_file) as conn:
                    cursor = conn.cursor()
                    cursor.execute('UPDATE messages SET message = ? WHERE id = ?', (data['message'], data['id']))
                    conn.commit()
                return jsonify({'status': 'success', 'message': 'Message edited by admin'}), 200
            return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to mark a user as offline
@app.route('/mark-offline', methods=['POST'])
def mark_offline():
        data = request.get_json()
        if 'username' in data:
            if hasattr(app, 'online_users') and data['username'] in app.online_users:
                app.online_users.remove(data['username'])
            return jsonify({'status': 'success', 'message': f'{data["username"]} is now offline.'}), 200
        return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to handle typing indicator
@app.route('/typing', methods=['POST'])
def typing():
    data = request.get_json()
    if 'username' in data:
        username = data['username']
        if not hasattr(app, 'typing_users'):
            app.typing_users = set()
        app.typing_users.add(username)
        return jsonify({'status': 'success', 'message': f'{username} is typing...'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to handle stopping typing indicator
@app.route('/stop-typing', methods=['POST'])
def stop_typing():
    data = request.get_json()
    if 'username' in data:
        username = data['username']
        if hasattr(app, 'typing_users') and username in app.typing_users:
            app.typing_users.remove(username)
        return jsonify({'status': 'success', 'message': f'{username} stopped typing.'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to fetch typing users
@app.route('/typing-status', methods=['GET'])
def typing_status():
    if not hasattr(app, 'typing_users'):
        app.typing_users = set()
    return jsonify({'typingUsers': list(app.typing_users)}), 200
    # Long polling route to fetch typing status


@app.route('/poll-typing-status', methods=['GET'])
def poll_typing_status():
        timeout = 30  # Maximum time to hold the request (in seconds)
        start_time = time.time()
        initial_typing_users = set(app.typing_users) if hasattr(app, 'typing_users') else set()

        while time.time() - start_time < timeout:
            current_typing_users = set(app.typing_users) if hasattr(app, 'typing_users') else set()
            if current_typing_users != initial_typing_users:
                return jsonify({'typingUsers': list(current_typing_users)}), 200
            time.sleep(1)  # Wait for 1 second before checking again

        return jsonify({'typingUsers': list(initial_typing_users)}), 200
# Route to handle deleting a message
@app.route('/delete-message', methods=['POST'])
def delete_message():
    data = request.get_json()
    if 'id' in data:
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE id = ?', (data['id'],))
            conn.commit()
        return jsonify({'status': 'success', 'message': 'Message deleted'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to handle adding a reaction to a message
@app.route('/add-reaction', methods=['POST'])
def add_reaction():
    data = request.get_json()
    if 'id' in data and 'reaction' in data:
        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT reactions FROM messages WHERE id = ?', (data['id'],))
            row = cursor.fetchone()
            if row:
                reactions = row[0] or ''
                reactions += f' {data["reaction"]}'
                cursor.execute('UPDATE messages SET reactions = ? WHERE id = ?', (reactions.strip(), data['id']))
                conn.commit()
                return jsonify({'status': 'success', 'message': 'Reaction added'}), 200
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400

# Route to handle sending a private message
@app.route('/send-private-message', methods=['POST'])
def send_private_message():
    data = request.get_json()
    if 'username' in data and 'message' in data:
        new_message_id = save_message_to_db(
            private_db_file,
            username=data['username'],
            profilePic=data.get('profilePic', ''),
            message=data['message'],
            image=data.get('image', '')
        )
        new_message = {
            'id': new_message_id,
            'username': data['username'],
            'profilePic': data.get('profilePic', ''),
            'message': data['message'],
            'image': data.get('image', '')
        }
        return jsonify({'status': 'success', 'message': new_message}), 200
    return jsonify({'status': 'error', 'message': 'Invalid data'}), 400



# Long polling route to fetch new messages for the public chat
@app.route('/poll-messages', methods=['GET'])
def poll_messages():
    last_id = request.args.get('last_id', None)
    try:
        if last_id is not None:
            last_id = int(last_id)
        timeout = 30  # Maximum time to hold the request (in seconds)
        start_time = time.time()
        while time.time() - start_time < timeout:
            messages = load_messages_from_db(db_file, last_id)
            if messages:
                # Fetch reactions for each message
                with sqlite3.connect(db_file) as conn:
                    cursor = conn.cursor()
                    for message in messages:
                        cursor.execute('SELECT reactions FROM messages WHERE id = ?', (message['id'],))
                        row = cursor.fetchone()
                        message['reactions'] = row[0] if row else ''
                return jsonify(messages)
            time.sleep(1)  # Wait for 1 second before checking again
        return jsonify([])  # Return an empty list if no new messages
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid last_id'}), 400



# Long polling route to fetch new messages for the private chat
@app.route('/poll-private-messages', methods=['GET'])
def poll_private_messages():
    last_id = request.args.get('last_id', None)
    try:
        if last_id is not None:
            last_id = int(last_id)
        timeout = 30  # Maximum time to hold the request (in seconds)
        start_time = time.time()
        while time.time() - start_time < timeout:
            messages = load_messages_from_db(private_db_file, last_id)
            if messages:
                return jsonify(messages)
            time.sleep(1)  # Wait for 1 second before checking again
        return jsonify([])  # Return an empty list if no new messages
    except ValueError:
        return jsonify({'status': 'error', 'message': 'Invalid last_id'}), 400

# Run Flask App
if __name__ == '__main__':
    app.run(debug=True)