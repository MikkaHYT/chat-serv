from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import sqlite3

app = Flask(__name__)
app.config['mikka'] = 'your_secret_key'  # Replace with a secure key
socketio = SocketIO(app)

# Directory to store uploaded images
image_upload_dir = 'static/uploads'
os.makedirs(image_upload_dir, exist_ok=True)

# SQLite database file
db_file = 'chat.db'

# Initialize SQLite database
def init_db():
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

init_db()

# Save a message to the database
def save_message_to_db(username, profilePic, message, image):
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (username, profilePic, message, image, reactions)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, profilePic, message, image, ''))
        conn.commit()
        return cursor.lastrowid

# Load all messages from the database
def load_messages_from_db():
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM messages ORDER BY id ASC')
        rows = cursor.fetchall()
        return [
            {'id': row[0], 'username': row[1], 'profilePic': row[2], 'message': row[3], 'image': row[4], 'reactions': row[5]}
            for row in rows
        ]

# Route to serve the chat page
@app.route('/')
def chat():
    return render_template('chat.html')

@app.route('/privatechat')
def private_chat():
    return render_template('private_chat.html')

@app.route('/sh')
def sh():
    return render_template('sh.html')

@app.route('/fps')
def fps():
    return render_template('fps.html')

# Socket.IO events
#@socketio.on('connect')
#def handle_connect():
    #print('A user connected')

#@socketio.on('disconnect')
#def handle_disconnect():
    #print('A user disconnected')

@socketio.on('edit_message')
def handle_edit_message(data):
        message_id = data.get('id')
        new_message = data.get('message')

        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE messages SET message = ? WHERE id = ?', (new_message, message_id))
            conn.commit()

        # Broadcast the updated message to all clients
        emit('update_message', {'id': message_id, 'message': f"{new_message} (edited)"}, broadcast=True)

@socketio.on('delete_message')
def handle_delete_message(data):
        message_id = data.get('id')

        with sqlite3.connect(db_file) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM messages WHERE id = ?', (message_id,))
            conn.commit()

        # Broadcast the removal of the message to all clients
        emit('remove_message', {'id': message_id}, broadcast=True)

@socketio.on('load_private_messages')
def handle_load_private_messages(data):
        room = data.get('room')
        if room:
            with sqlite3.connect(db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM messages WHERE room = ? ORDER BY id ASC', (room,))
                rows = cursor.fetchall()
                messages = [
                    {'id': row[0], 'username': row[1], 'profilePic': row[2], 'message': row[3], 'image': row[4], 'reactions': row[5]}
                    for row in rows
                ]
            emit('load_private_messages', messages, room=room)

@socketio.on('start_typing')
def handle_start_typing(data):
    username = data.get('username')
    if username and username in online_users:
        print(f"{username} started typing")
        online_users[username]['isTyping'] = True
        emit('update_online_users', [{'username': user, 'isTyping': info['isTyping']} for user, info in online_users.items()], broadcast=True)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    username = data.get('username')
    if username and username in online_users:
        print(f"{username} stopped typing")
        online_users[username]['isTyping'] = False
        emit('update_online_users', [{'username': user, 'isTyping': info['isTyping']} for user, info in online_users.items()], broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    username = data.get('username')
    profilePic = data.get('profilePic', '')
    message = data.get('message')
    image = data.get('image', '')

    # Save the message to the database
    message_id = save_message_to_db(username, profilePic, message, image)

    # Broadcast the message to all connected clients
    emit('receive_message', {
        'id': message_id,
        'username': username,
        'profilePic': profilePic,
        'message': message,
        'image': image,
        'reactions': ''
    }, broadcast=True)

@socketio.on('connect')
def handle_connect():
    print('A user connected')
    # Emit all messages to the newly connected client
    emit('load_messages', load_messages_from_db(), broadcast=False)

# Track online users
online_users = {}

@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    if username:
        print(f"{username} has come online")
        online_users[username] = {'isTyping': False}

        # Add the user to their own private room
        join_room(username)
        print(f"{username} has joined their private room.")

        # Notify all clients about the updated online users
        emit('update_online_users', [{'username': user, 'isTyping': info['isTyping']} for user, info in online_users.items()], broadcast=True)

@socketio.on('leave')
def handle_leave(data):
    username = data.get('username')
    if username and username in online_users:
        print(f"{username} has went offline")
        del online_users[username]
        emit('update_online_users', [{'username': user, 'isTyping': info['isTyping']} for user, info in online_users.items()], broadcast=True)

@socketio.on('add_reaction')
def handle_add_reaction(data):
    message_id = data.get('id')
    reaction = data.get('reaction')

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT reactions FROM messages WHERE id = ?', (message_id,))
        row = cursor.fetchone()
        if row:
            reactions = row[0] or ''
            reactions += f' {reaction}'
            cursor.execute('UPDATE messages SET reactions = ? WHERE id = ?', (reactions.strip(), message_id))
            conn.commit()

    print(reactions)

    # Broadcast the updated reactions to all clients
    socketio.emit('update_reactions', {
    'id': message_id,
    'reactions': reactions.strip()
})
    print(f"Reactions updated for message ID {message_id}: {reactions.strip()}")

# In-memory database for private messages
private_messages = {}

@socketio.on('private_message')
def handle_private_message(data):
    sender = data.get('username')  # Ensure the sender's username is included in the data
    recipient = data.get('recipient')
    message = data.get('message')
    print(f"Private message from {sender} to {recipient}: {message}")

    if sender and recipient and message:
        # Save the message in memory
        if recipient not in private_messages:
            private_messages[recipient] = []
        private_messages[recipient].append({'sender': sender, 'message': message})

        # Emit the message to the recipient
        emit('receive_private_message', {'sender': sender, 'message': message}, room=recipient)

        # Ensure the sender is in the room for acknowledgment
        join_room(sender)

    

@socketio.on('join_rps')
def handle_join_rps(data):
        username = data.get('username')
        print(f"{username} has joined the RPS game")
        if username:
            if 'rps_game' not in globals():
                global rps_game
                rps_game = {'players': [], 'choices': {}}

            

            if len(rps_game['players']) < 2:
                rps_game['players'].append(username)
                rps_game['choices'][username] = None
                join_room(username)  # Ensure the user joins their own room for communication
                if len(rps_game['players']) == 2:
                    player1, player2 = rps_game['players']
                    socketio.emit('rps_start', {'opponent': player2}, room=player1)
                    socketio.emit('rps_start', {'opponent': player1}, room=player2)
                else:
                    emit('rps_result', {'result': 'Waiting for another player to join...'})
            else:
                emit('rps_result', {'result': 'Game is full. Please wait for the next round.'})

@socketio.on('rps_choice')
def handle_rps_choice(data):
        username = data.get('username')
        choice = data.get('choice')
        if username in rps_game['players']:
            rps_game['choices'][username] = choice

            if all(rps_game['choices'].values()):
                player1, player2 = rps_game['players']
                choice1, choice2 = rps_game['choices'][player1], rps_game['choices'][player2]

                if choice1 == choice2:
                    result = "It's a tie!"
                elif (choice1 == 'rock' and choice2 == 'scissors') or \
                     (choice1 == 'scissors' and choice2 == 'paper') or \
                     (choice1 == 'paper' and choice2 == 'rock'):
                    result = f"{player1} wins!"
                else:
                    result = f"{player2} wins!"

                socketio.emit('rps_result', {'result': result}, room=player1)
                socketio.emit('rps_result', {'result': result}, room=player2)

                # Reset the game for the next round
                rps_game['players'] = []
                rps_game['choices'] = {}

                # Broadcast the result as a message to all clients
                socketio.emit('send_message', jsonify({
                    'username': 'SERVER',
                    'profilePic': '',
                    'message': 'The current Rock Paper Scissors game is over. You can join the next round.',
                }))

@socketio.on('broadcast_message')
def handle_broadcast_message(data):
    """
    Broadcast a message to all connected clients.
    """
    message = data.get('message', 'Server Message')
    username = data.get('username', 'SERVER')  # Default to 'Server' if no username is provided
    profile_pic = data.get('profilePic', '')  # Optional profile picture

    # Emit the message to all clients
    emit('receive_message', {
        'id': None,  # You can generate an ID if needed
        'username': username,
        'profilePic': profile_pic,
        'message': message,
        'image': None,  # No image for server messages
        'reactions': ''
    }, broadcast=True)

@socketio.on('leave_rps')
def handle_leave_rps(data):
        username = data.get('username')
        if username in rps_game['players']:
            rps_game['players'].remove(username)
            del rps_game['choices'][username]
            socketio.emit('rps_result', {'result': f"{username} left the game. Game canceled."}, to='/')

# Mute and Unmute
@socketio.on('mute_user')
def handle_mute_user(data):
    username = data.get('username')
    if username:
        print(f"{username} has been muted")
        # Broadcast to all clients that the user is muted
        emit('user_muted', {'username': username}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)