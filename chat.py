from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import sqlite3
from datetime import datetime
import json
import threading

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
                reactions TEXT,
                time TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                bio TEXT DEFAULT '', -- Add bio column
                profilePic TEXT DEFAULT '' -- Add profilePic column
            )
        ''')
        conn.commit()

init_db()

# Save a message to the database
def save_message_to_db(username, profilePic, message, image):
    with sqlite3.connect(db_file) as conn:
        current_time = datetime.now().strftime('%H:%M')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (username, profilePic, message, image, reactions, time)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, profilePic, message, image, '', current_time))
        conn.commit()
        return cursor.lastrowid

# Load all messages from the database
def load_messages_from_db():
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM messages ORDER BY id')
        rows = cursor.fetchall()
        # Reverse the order before sending to the client
        return [
            {'id': row[0], 'username': row[1], 'profilePic': row[2], 'message': row[3], 'image': row[4], 'reactions': row[5], 'time': row[6]}
            for row in (rows)
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

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/surf')
def ss():
    return render_template('game.html')

@app.route('/fps')
def fps():
    return render_template('fps.html')

@app.route('/whiteboard')
def whiteboard():
    return render_template('whiteboard.html')

@app.route('/pictionary')
def pictionary():
    return render_template('pictionary.html')

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
        time = datetime.now().strftime('%H:%M')
        if room:
            with sqlite3.connect(db_file) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM messages WHERE room = ? ORDER BY id ASC', (room,))
                rows = cursor.fetchall()
                messages = [
                    {'id': row[0], 'username': row[1], 'profilePic': row[2], 'message': row[3], 'image': row[4], 'reactions': row[5], time: row[6]}
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

    # Check if Word Chain is active and use the word to play the game
    if word_chain.get('active', 0) == 1:
        if message == '/endwordchain':
            word_chain['active'] = 0
            word_chain['last_word'] = None
            word_chain['used_words'].clear()
            emit('receive_message', {
                'username': 'Server',
                'profilePic': '',
                'message': f"{username} has ended the Word Chain game.",
                'image': '',
                'reactions': '',
                'time': datetime.now().strftime('%H:%M')
            }, broadcast=True)
            return
        print("Word Chain game active")
        word = message.lower()
        if word_chain['last_word'] and word[0] != word_chain['last_word'][-1]:
            emit('word_chain_invalid', {'message': 'Invalid word!'}, room=request.sid)
            emit('receive_message', {
                'username': 'Server',
                'profilePic': '',
                'message': f"Invalid word by {username}: {word}",
                'image': '',
                'reactions': '',
                'time': datetime.now().strftime('%H:%M')
            }, broadcast=True)
        elif word in word_chain['used_words']:
            emit('word_chain_invalid', {'message': 'Word already used!'}, room=request.sid)
            emit('receive_message', {
                'username': 'Server',
                'profilePic': '',
                'message': f"Word already used by {username}: {word}",
                'image': '',
                'reactions': '',
                'time': datetime.now().strftime('%H:%M')
            }, broadcast=True)
        else:
            word_chain['last_word'] = word
            word_chain['used_words'].add(word)
            emit('word_chain_update', {'word': word, 'username': username}, broadcast=True)
            emit('receive_message', {
                'username': username,
                'profilePic': profilePic,
                'message': message,
                'image': image,
                'reactions': '',
                'time': datetime.now().strftime('%H:%M')
            }, broadcast=True)

    # Broadcast the message to all connected clients
    emit('receive_message', {
        'id': message_id,
        'username': username,
        'profilePic': profilePic,
        'message': message,
        'image': image,
        'reactions': '',
        'time': datetime.now().strftime('%H:%M')
    }, broadcast=True)



@socketio.on('connect')
def handle_connect():
    print('A user connected')
    # Emit all messages to the newly connected client
    emit('load_messages', load_messages_from_db(), broadcast=False)

@socketio.on('login')
def handle_login(data):
    username = data.get('username')
    print(f"Login attempt: {username}")
    password = data.get('password')

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
        user = cursor.fetchone()

    if user:
        emit('login_success', username)  # Emit the username
    else:
        print(f"Login failed for: {username}")
        emit('login_failure', {'message': 'Invalid username or password'})

@socketio.on('register')
def handle_register(data):
    username = data.get('username')
    password = data.get('password')

    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

        if user:
            emit('register_failure', {'message': 'Username already exists'})
        else:
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            emit('register_success', {'message': 'Registration successful', 'username': username})
# Track online users
online_users = {}

@socketio.on('join')
def handle_join(data):
    
    username = data.get('username')  # Get the username from the client
    print(f"Join event received for: {username}")
    if username:
        print(f"{username} has come online")  # Debugging: Print the username
        online_users[username] = {'isTyping': False}

        # Add the user to their own private room
        join_room(username)
        print(f"{username} has joined their private room.")  # Debugging: Confirm room join

        # Notify all clients about the updated online users
        emit('update_online_users', [{'username': user, 'isTyping': info['isTyping']} for user, info in online_users.items()], broadcast=True)
        
@socketio.on('leave')
def handle_leave(data):
    username = data.get('username')
    if username and username in online_users:
        print(f"{username} has went offline")
        del online_users[username]
        emit('update_online_users', [{'username': user, 'isTyping': info['isTyping']} for user, info in online_users.items()], broadcast=True)

@socketio.on('get_user_data')
def handle_get_user_data(data):
    username = data.get('username')
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT bio, profilePic FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        if user:
            emit('user_data', {'bio': user[0], 'profilePic': user[1]})

@socketio.on('refresh_clients')
def handle_refresh_clients():
    # Broadcast the refresh event to all connected clients
    print("refreshing clients..")
    emit('test_event', {'message': 'Test event triggered'}, broadcast=True)
    emit('refresh_page', broadcast=True)

@socketio.on('update_user_data')
def handle_update_user_data(data):
    username = data.get('username')
    bio = data.get('bio', '')
    profilePic = data.get('profilePic', '')

    # Save the updated bio and profile picture to the database
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET bio = ?, profilePic = ? WHERE username = ?', (bio, profilePic, username))
        conn.commit()

    # Broadcast the updated profile picture to all connected clients
    emit('profile_pic_updated', {'username': username, 'profilePic': profilePic}, broadcast=True)

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

# In-memory storage for chess games
chess_games = {}

@socketio.on('join_chess')
def handle_join_chess(data):
    username = data.get('username')
    room = data.get('room', 'chess_room')  # Default room for chess
    print(f"{username} has joined the chess game in room {room}")
    join_room(room)

    if room not in chess_games:
        chess_games[room] = {
            'players': [],
            'moves': [],
            'turn': 'white',  # White moves first
        }

    # Check if the player is already in the game
    if username in chess_games[room]['players']:
        emit('chess_joined', {'username': username, 'color': 'white' if chess_games[room]['players'][0] == username else 'black'}, room=room)
        return

    # Add the player if there's room
    if len(chess_games[room]['players']) < 2:
        chess_games[room]['players'].append(username)
        color = 'white' if len(chess_games[room]['players']) == 1 else 'black'
        emit('chess_joined', {'username': username, 'color': color}, room=room)

        # Start the game if two players have joined
        if len(chess_games[room]['players']) == 2:
            emit('chess_start', {'players': chess_games[room]['players'], 'turn': chess_games[room]['turn']}, room=room)
    else:
        emit('chess_full', {'message': 'The game is full. Please wait for the next round.'}, to=request.sid)
        
@socketio.on('chess_move')
def handle_chess_move(data):
    room = data.get('room', 'chess_room')
    move = data.get('move')  # Example: {'from': 'e2', 'to': 'e4'}

    if room in chess_games:
        chess_games[room]['moves'].append(move)
        chess_games[room]['turn'] = 'black' if chess_games[room]['turn'] == 'white' else 'white'
        emit('chess_update', {'move': move, 'turn': chess_games[room]['turn']}, room=room)

@socketio.on('leave_chess')
def handle_leave_chess(data):
    username = data.get('username')
    room = data.get('room', 'chess_room')
    print(f"{username} has left the chess game in room {room}")
    if room in chess_games and username in chess_games[room]['players']:
        chess_games[room]['players'].remove(username)
        emit('chess_player_left', {'username': username}, room=room)

        # Reset the game if all players leave
        if not chess_games[room]['players']:
            del chess_games[room]

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
                    message = username+' has joined rock paper scissors. Waiting for another player...'
                    save_message_to_db('Server', '', message, '')
                    if message:
                        emit('receive_message', {
                            'username': 'Server',
                            'profilePic': '',
                            'message': message,
                            'image': '',
                            'reactions': '',
                            'time': datetime.now().strftime('%H:%M')
                        }, broadcast=True)
            else:
                emit('rps_result', {'result': 'Game is full. Please wait for the next round.'})
                message = 'Rock paper scissors is now full. Please wait for the next round.'
                save_message_to_db('Server', '', message, '')
                if message:
                        emit('receive_message', {
                            'username': 'Server',
                            'profilePic': '',
                            'message': message,
                            'image': '',
                            'reactions': '',
                            'time': datetime.now().strftime('%H:%M')
                        }, broadcast=True)

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
                    serverresult = f"{player1}"
                else:
                    result = f"{player2} wins!"
                    serverresult = f"{player2}"

                socketio.emit('rps_result', {'result': result}, room=player1)
                socketio.emit('rps_result', {'result': result}, room=player2)

                # Reset the game for the next round
                rps_game['players'] = []
                rps_game['choices'] = {}

                # Notify all players that the game is over
                message = f'The current Rock Paper Scissors game is over. \n{serverresult} won. \nYou may join the next round.'
                username = 'Server'
                profilePic = ''
                image = ''
                # Save the message to the database
                save_message_to_db(username, profilePic, message, image)
                if message:
                    emit('receive_message', {
                        'username': 'Server',
                        'profilePic': '',
                        'message': message,
                        'image': '',
                        'reactions': ''
                    }, broadcast=True)

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

@socketio.on('admin_fetch_messages')
def handle_admin_fetch_messages():
    messages = load_messages_from_db()
    emit('admin_messages', messages)

@socketio.on('admin_fetch_users')
def handle_admin_fetch_users():
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT username, bio, profilePic FROM users')
        rows = cursor.fetchall()
        users = [{'username': row[0], 'bio': row[1], 'profilePic': row[2]} for row in rows]
    emit('admin_users', users)

@socketio.on('admin_fake_message')
def handle_admin_fake_message(data):
    username = data.get('username')
    profilePic = data.get('profilePic', '')
    message = data.get('message')
    image = data.get('image', '')
    time = datetime.now().strftime('%H:%M')

    # Save the message to the database
    message_id = save_message_to_db(username, profilePic, message, image)

    # Emit the fake message to all clients
    emit('receive_message', {
        'id': message_id,
        'username': username,
        'profilePic': profilePic,
        'message': message,
        'image': image,
        'reactions': '',
        'time': time
    }, broadcast=True)

@socketio.on('admin_edit_message')
def handle_admin_edit_message(data):
    message_id = data.get('id')
    new_message = data.get('message')
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE messages SET message = ? WHERE id = ?', (new_message, message_id))
        conn.commit()
    # Emit the updated message to all clients
    emit('update_message', {'id': message_id, 'message': f"{new_message}"}, broadcast=True)

@socketio.on('admin_delete_message')
def handle_admin_delete_message(data):
    message_id = data.get('id')
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages WHERE id = ?', (message_id,))
        conn.commit()
    # Notify all clients about the deleted message
    emit('remove_message', {'id': message_id}, broadcast=True)

@socketio.on('admin_broadcast')
def handle_admin_broadcast(data):
        print("Admin broadcast initiated")
        print(data)
        alert_message = data.get('alert', 'Broadcast Alert')
        # Emit the broadcast alert to all connected clients
        emit('receive_alert', {'alert': alert_message}, broadcast=True)

@socketio.on('admin_refresh')
def handle_admin_broadcast(data):
        print("Admin refresh initiated")
        emit('receive_refresh', broadcast=True)

@socketio.on('admin_erase_chat')
def handle_admin_erase_chat():
    with sqlite3.connect(db_file) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM messages')
        conn.commit()
    # Notify all clients that the chat has been erased
    emit('admin_chat_erased', broadcast=True)

@socketio.on('join_tictactoe')
def handle_join_tictactoe(data):
    username = data.get('username')
    if 'tictactoe_game' not in globals():
        global tictactoe_game
        tictactoe_game = {
            'board': [''] * 9,
            'players': [],
            'currentPlayer': '',
            'isGameOver': False
        }

    if len(tictactoe_game['players']) < 2:
        tictactoe_game['players'].append(username)
        if len(tictactoe_game['players']) == 2:
            tictactoe_game['currentPlayer'] = tictactoe_game['players'][0]
            player1, player2 = tictactoe_game['players']
            socketio.emit('tictactoe_start', {'opponent': player2, 'isFirstPlayer': True}, room=player1)
            socketio.emit('tictactoe_start', {'opponent': player1, 'isFirstPlayer': False}, room=player2)
        else:
            emit('tictactoe_waiting', {'message': 'Waiting for another player to join...'})
    else:
        emit('tictactoe_full', {'message': 'Game is full. Please wait for the next round.'})

@socketio.on('tictactoe_move')
def handle_tictactoe_move(data):
    username = data.get('username')
    index = data.get('index')

    if tictactoe_game['isGameOver'] or tictactoe_game['board'][index] != '' or tictactoe_game['currentPlayer'] != username:
        return

    tictactoe_game['board'][index] = 'X' if tictactoe_game['currentPlayer'] == tictactoe_game['players'][0] else 'O'
    tictactoe_game['currentPlayer'] = tictactoe_game['players'][0] if tictactoe_game['currentPlayer'] == tictactoe_game['players'][1] else tictactoe_game['players'][1]

    socketio.emit('tictactoe_update', {
        'board': tictactoe_game['board'],
        'currentPlayer': tictactoe_game['currentPlayer']
    }, broadcast=True)

    winner = check_tictactoe_winner()
    if winner:
        tictactoe_game['isGameOver'] = True
        socketio.emit('tictactoe_game_over', {'winner': winner}, broadcast=True)
    elif all(cell != '' for cell in tictactoe_game['board']):
        tictactoe_game['isGameOver'] = True
        socketio.emit('tictactoe_game_over', {'winner': None}, broadcast=True)

def check_tictactoe_winner():
    winning_combinations = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],  # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8],  # Columns
        [0, 4, 8], [2, 4, 6]              # Diagonals
    ]
    for combo in winning_combinations:
        a, b, c = combo
        if tictactoe_game['board'][a] == tictactoe_game['board'][b] == tictactoe_game['board'][c] and tictactoe_game['board'][a] != '':
            return tictactoe_game['board'][a]
    return None

# In-memory storage for whiteboard data
whiteboard_data = []
whiteboard_lock = threading.Lock()

@socketio.on('whiteboard_draw')
def handle_whiteboard_draw(data):
    # Broadcast drawing data to all clients
    emit('whiteboard_update', data, broadcast=True)

    # Save the drawing data to the in-memory database
    with whiteboard_lock:  # Ensure thread-safe access
        whiteboard_data.append(data)

@socketio.on('save_whiteboard')
def handle_save_whiteboard():
    # This event is triggered to ensure the whiteboard is saved
    emit('whiteboard_saved', {'message': 'Whiteboard saved successfully'}, broadcast=True)

@socketio.on('load_whiteboard')
def handle_load_whiteboard():
    with whiteboard_lock:  # Ensure thread-safe access
        emit('whiteboard_data', whiteboard_data, broadcast=False)

# Track active cursors
active_cursors = {}

@socketio.on('cursor_position')
def handle_cursor_position(data):
    user_id = data.get('id')
    position = data.get('position')
    if user_id and position:
        active_cursors[user_id] = position
        emit('cursor_update', {'id': user_id, 'position': position}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.sid  # Use the session ID as the unique user ID
    if user_id in active_cursors:
        del active_cursors[user_id]
        emit('cursor_disconnect', {'id': user_id}, broadcast=True)

@socketio.on('whiteboard_mouseup')
def handle_whiteboard_mouseup(data):
    # Save the whiteboard data automatically on mouseup
    with whiteboard_lock:  # Ensure thread-safe access
        whiteboard_data.append(data)
    emit('whiteboard_saved', {'message': 'Whiteboard saved successfully'}, broadcast=True)

@socketio.on('undo_whiteboard')
def handle_undo_whiteboard():
    # Remove the last drawing action from the in-memory database
    with whiteboard_lock:  # Ensure thread-safe access
        if whiteboard_data:
            whiteboard_data.pop()

    # Broadcast the updated whiteboard data to all clients
    emit('whiteboard_data', whiteboard_data, broadcast=True)
    
@socketio.on('anonymous_message')
def handle_anonymous_message(data):
    message = data.get('message')
    username = 'Anonymous'
    profilePic = ''
    image = ''
    time = datetime.now().strftime('%H:%M')
    # Save the message to the database
    save_message_to_db(username, profilePic, message, image)
    if message:
        emit('receive_message', {
            'username': 'Anonymous',
            'profilePic': '',
            'message': message,
            'image': '',
            'reactions': '',
            'time': datetime.now().strftime('%H:%M')
        }, broadcast=True)

@socketio.on('chess_move')
def handle_chess_move(data):
    # Broadcast the move to the opponent
    emit('chess_update', data, room=data.get('room'))

@socketio.on('load_more_messages')
def handle_load_more_messages(data):
    limit = data.get('limit', 20)  # Default to 20 messages
    offset = data.get('offset', 0)  # Default to 0 (no offset)
    messages = load_messages_from_db(limit=limit, offset=offset)
    emit('load_more_messages', messages)

# Polls

# In-memory storage for polls
polls = {}

@socketio.on('create_poll')
def handle_create_poll(data):
    poll_id = len(polls) + 1
    polls[poll_id] = {
        'question': data['question'],
        'options': {option: 0 for option in data['options']},
        'creator': data['creator']
    }
    emit('poll_created', {'poll_id': poll_id, 'poll': polls[poll_id]}, broadcast=True)

@socketio.on('vote_poll')
def handle_vote_poll(data):
    poll_id = data['poll_id']
    option = data['option']
    if poll_id in polls and option in polls[poll_id]['options']:
        polls[poll_id]['options'][option] += 1
        emit('poll_updated', {'poll_id': poll_id, 'poll': polls[poll_id]}, broadcast=True)

# Mini-Games

# Word Chain

# In-memory storage for word chain
word_chain = {'last_word': None, 'used_words': set()}

@socketio.on('word_chain')
def handle_word_chain(data):
    word = data['word'].lower()
    if word_chain['last_word'] and word[0] != word_chain['last_word'][-1]:
        emit('word_chain_invalid', {'message': 'Invalid word!'}, room=request.sid)
    elif word in word_chain['used_words']:
        emit('word_chain_invalid', {'message': 'Word already used!'}, room=request.sid)
    else:
        word_chain['last_word'] = word
        word_chain['used_words'].add(word)
        emit('word_chain_update', {'word': word, 'username': data['username']}, broadcast=True)

@socketio.on('start_wordchain')
def handle_start_wordchain(data):
    print("Starting Word Chain game")
    username = data.get('username')
    word_chain['last_word'] = None
    word_chain['used_words'] = set()
    emit('receive_message', {
        'username': 'Server',
        'message': f"{username} has started a Word Chain game! Type a word to play.",
        'profilePic': '',
        'time': datetime.now().strftime('%H:%M')
    }, broadcast=True)
    word_chain['active'] = 1

# Pictionary

# In-memory storage for Pictionary
pictionary = {'current_word': None, 'drawer': None, 'guesses': []}

@socketio.on('start_pictionary')
def handle_start_pictionary(data):
    pictionary['current_word'] = data['word']
    pictionary['drawer'] = data['drawer']
    emit('pictionary_started', {'drawer': data['drawer'], 'word': data['word']}, broadcast=True)

@socketio.on('guess_pictionary')
def handle_guess_pictionary(data):
    username = data.get('username')
    guess = data.get('guess')

    if guess.lower() == pictionary['current_word'].lower():
        # Send correct guess message
        emit('pictionary_correct', {'username': username}, broadcast=True)
        
        # Send word reveal as system message
        emit('pictionary_system_message', {
            'message': f"The word was: {pictionary['current_word']}"
        }, broadcast=True)
        
        # Show the end round screen with the word
        emit('round_end', {
            'word': pictionary['current_word'],
            'scores': [{'username': username, 'points': 10}]  # Simple scoring
        }, broadcast=True)
        
        emit('clear_canvas', broadcast=True)  # Clear the canvas for all players
        
        # Wait a few seconds before starting a new round
        socketio.sleep(5)
        start_new_round()  # Start a new round
    else:
        emit('pictionary_incorrect', {'username': username, 'guess': guess}, broadcast=True)

# In-memory storage for Pictionary players
pictionary_players = []
pictionary_ready = []



@socketio.on('join_pictionary')
def handle_join_pictionary(data):
    username = data.get('username')
    
    # Store the user's sid for disconnect handling
    if username not in [player['username'] for player in pictionary_players]:
        is_host = len(pictionary_players) == 0
        pictionary_players.append({
            'username': username, 
            'ready': False, 
            'isHost': is_host,
            'sid': request.sid  # Store the socket ID
        })
        emit('update_players', pictionary_players, broadcast=True)
        
        if is_host:
            emit('assign_host', {'isHost': True}, room=request.sid)
@socketio.on('ready_up')
def handle_ready_up(data):
    username = data.get('username')
    ready = data.get('ready')

    for player in pictionary_players:
        if player['username'] == username:
            player['ready'] = ready
            break

    emit('update_players', pictionary_players, broadcast=True)

    # Check if all players are ready
    if all(player['ready'] for player in pictionary_players):
        # Notify the host that the game can be started
        for player in pictionary_players:
            if player['isHost']:
                emit('game_ready_to_start', room=player['username'])
                break

@socketio.on('disconnect')
def handle_disconnect():
    global pictionary_players, game_in_progress
    
    # Get the disconnected user's sid
    sid = request.sid
    
    # Find the user in pictionary_players
    disconnected_player = None
    for i, player in enumerate(pictionary_players):
        if player['username'] == sid or player.get('sid') == sid:
            disconnected_player = player
            pictionary_players.pop(i)
            break
    
    if disconnected_player:
        # If the disconnected player was the host, assign a new host
        if disconnected_player.get('isHost') and pictionary_players:
            pictionary_players[0]['isHost'] = True
            emit('assign_host', {'isHost': True}, room=pictionary_players[0].get('sid', pictionary_players[0]['username']))
        
        # If the disconnected player was the drawer, start a new round
        if game_in_progress and pictionary.get('drawer') == disconnected_player['username']:
            emit('pictionary_system_message', {
                'message': f"{disconnected_player['username']} (the drawer) disconnected. Starting new round."
            }, broadcast=True)
            start_new_round()
        
        # Emit updated player list to all clients
        emit('update_players', pictionary_players, broadcast=True)

import random
import requests

def start_new_round():
    if len(pictionary_players) < 2:
        emit('pictionary_system_message', {'message': 'Not enough players to start the game.'}, broadcast=True)
        return

    # Randomly select a drawer
    drawer = random.choice(pictionary_players)
    pictionary['drawer'] = drawer['username']
    pictionary['current_word'] = generate_random_word()

    # Update drawer status
    for player in pictionary_players:
        player['isDrawing'] = player['username'] == drawer['username']

    # Notify all players about the new round
    emit('new_round', {'drawer': pictionary['drawer'], 'word': pictionary['current_word']}, broadcast=True)
    
    # Announce the new round as a system message
    emit('pictionary_system_message', {
        'message': f"New round started! {drawer['username']} is drawing."
    }, broadcast=True)
    
    # Update the player list with the new drawer
    emit('update_players', pictionary_players, broadcast=True)
def generate_random_word():
    # Predefined list of "easy" words
    easy_words = [
        "flower", "bridge", "ice cream cone", "ring", "diamond", "blanket", "bird", "bumblebee", "glasses", "girl",
        "grapes", "water", "dragon", "sheep", "float", "backpack", "mountains", "button", "roly poly/pill bug/doodle bug",
        "cherry", "bear", "island", "egg", "mitten", "leaf", "fork", "cookie", "lollipop", "frog", "star", "jacket",
        "square", "nose", "football", "crayon", "wheel", "triangle", "family", "knee", "cow", "candy", "branch", "ship",
        "rainbow", "grass", "cat", "bell", "zigzag", "jar", "spider", "kite", "duck", "zoo", "rock", "swimming pool",
        "beach", "window", "owl", "ghost", "house", "zebra", "pencil", "spider web", "sunglasses", "dog", "ear", "swing",
        "key", "shoe", "ï»¿airplane", "snail", "music", "bunny", "motorcycle", "cloud", "corn", "comb", "man", "Mickey Mouse",
        "door", "jail", "eyes", "smile", "bus", "beak", "horse", "snake", "pizza", "basketball", "carrot", "broom", "eye",
        "bed", "candle", "seashell", "cupcake", "king", "night", "feather", "computer", "bat", "ocean", "box", "helicopter",
        "ball", "pen", "face", "dream", "cube", "inchworm", "hand", "bounce", "hamburger", "legs", "slide", "dinosaur",
        "whale", "ladybug", "rabbit", "lion", "light", "popsicle", "elephant", "tree", "desk", "shirt", "chimney", "daisy",
        "spoon", "clock", "car", "sea", "tail", "feet", "hair", "mountain", "lizard", "milk", "moon", "line", "fish", "pants",
        "lips", "bracelet", "mouse", "hippo", "river", "neck", "turtle", "sea turtle", "Earth", "octopus", "monkey", "worm",
        "skateboard", "apple", "baby", "woman", "bee", "table", "ears", "bowl", "bunk bed", "coin", "pie", "finger",
        "caterpillar", "alligator", "coat", "bone", "book", "bike", "love", "arm", "crack", "cup", "giraffe", "fire", "kitten",
        "leg", "curl", "snowman", "flag", "angel", "heart", "purse", "doll", "pig", "cheese", "baseball", "oval", "butterfly",
        "balloon", "mouth", "crab", "fly", "hat", "bug", "ants", "hook", "circle", "ant", "bench", "starfish", "train", "head",
        "banana", "person", "bathroom", "bark", "nail", "drum", "bread", "stairs", "socks", "lamp", "alive", "monster",
        "suitcase", "rain", "plant", "camera", "rocket", "orange", "boat", "chicken", "pillow", "jellyfish", "boy", "lemon",
        "snowflake", "chair", "sun", "bow", "truck", "blocks", "robot"
    ]
    medium_words = [
        "feast", "tusk", "address", "tub", "goat", "pool", "day", "desk", "drawer", "strawberry", "empty", "music", "rat",
        "mail", "silverware", "nurse", "hero", "lawnmower", "sunglasses", "daddy longlegs", "go", "scale", "radish", "crib",
        "bathroom scale", "fairies", "heel", "cell phone", "motorcycle", "pipe", "wedge", "thermometer", "food", "pop",
        "dustpan", "zebra", "needle", "shipwreck", "paperclip", "state", "time", "corn dog", "towel", "dimple",
        "cheeseburger", "children", "constellation", "turkey", "tiger", "rocket", "dig", "ambulance", "banana split",
        "dragon", "dinner", "refrigerator", "hoof", "coast", "latitude", "piano", "fruit", "plate", "key", "harmonica",
        "lawn mower", "package", "broccoli", "unicorn", "cover", "class", "headband", "city", "map", "washing machine",
        "submarine", "stocking", "girlfriend", "vegetable", "campfire", "howl", "flamingo", "round", "hole", "cobra", "toe",
        "marshmallow", "movie theater", "wreath", "newspaper", "cobweb", "string", "dominoes", "drums", "black hole",
        "sleeping bag", "stump", "coyote", "ask", "quilt", "cheerleader", "subway", "homeless", "wall", "truck", "ladybug",
        "nut", "closed", "telephone", "full moon", "wheelbarrow", "mouse pad", "pan", "free", "potato", "chalk", "envelope",
        "see", "shape", "goldfish", "beehive", "blowfish", "elevator", "hula hoop", "aunt", "hospital", "oil", "cast",
        "popcorn", "snowflake", "shadow", "bike", "hot dog", "yarn", "corn", "celery", "cotton candy", "tricycle",
        "firefighter", "trip", "panda", "sword", "magnet", "garbage", "mailbox", "wave", "box", "stoplight", "eye patch",
        "cemetery", "chest", "dirt", "summer", "start", "scissors", "hotel", "penny", "sink", "step", "fanny pack",
        "bathtub", "stingray", "paint", "store", "organ", "table", "bagel", "candle", "lemon", "plank", "crumb", "floor",
        "braid", "curtains", "lid", "plug", "sandal", "kite", "anemone", "smile", "airport", "twig", "pond", "angel",
        "carpet", "babysitter", "spool", "shopping cart", "ticket", "cockroach", "rake", "base", "sock", "toast",
        "electricity", "tail", "seesaw", "blue jeans", "puzzle", "clown", "fin", "safe", "wagon", "queen", "sidekick",
        "wrench", "hopscotch", "tooth", "tank", "cork", "lucky", "aircraft", "janitor", "escalator", "barn", "jacket",
        "lifejacket", "eel", "quadruplets", "doormat", "golf", "juice", "porthole", "clam", "frying pan", "pea", "cowboy",
        "chip", "slide", "drill", "helium", "shovel", "zoo", "crayon", "chess", "positive", "America", "hiss", "cricket",
        "honey", "shampoo", "scar", "picture frame", "skateboard", "banjo", "salt", "birthday", "eraser", "coal", "milk",
        "computer", "compass", "pickle", "strap", "maid", "hurdle", "suitcase", "pocket", "notepad", "growl", "teeth",
        "coil", "sailboat", "tip", "bib", "trophy", "three-toed sloth", "spider web", "locket", "swimming pool", "ship",
        "skunk", "toothbrush", "hot-air balloon", "cracker", "poodle", "cardboard", "crow", "t-shirt", "lip", "spot",
        "sleep", "trampoline", "solar system", "alarm clock", "banana peel", "cocoon", "sea turtle", "pail", "cucumber",
        "cook", "garage", "zookeeper", "ocean", "toaster", "pencil", "fang", "rice", "jungle", "dad", "orange", "peach",
        "faucet", "scarecrow", "rain", "quicksand", "glue", "roof", "garden", "watch", "graph", "bug spray", "monster",
        "mask", "list", "hammer", "fire hydrant", "jelly", "marry", "room", "nature", "circus", "extension cord", "curb",
        "puddle", "minivan", "iPad", "lock", "knot", "butcher", "sunflower", "attic", "barrel", "insect", "colored pencil",
        "rattle", "chef", "jet ski", "cape", "pinecone", "shower", "peck", "mud", "fax", "detective", "ping pong", "inch",
        "gate", "beach", "tulip", "rib", "surfboard", "spine", "blanket", "toilet paper", "globe", "letter", "pelican",
        "french fries", "molecule", "snowball", "kayak", "hairbrush", "narwhal", "pilot", "sushi", "tightrope", "stork",
        "log", "carousel", "castle", "pet", "cabin", "sprinkler", "anvil", "crater", "magic", "laundry basket", "elbow",
        "coat", "soup", "dress", "harp", "rhinoceros", "kiss", "cactus", "crust", "race car", "curtain", "eagle", "kettle",
        "volcano", "bubble", "knee", "rolly polly", "blimp", "stroller", "door", "parachuting", "cul-de-sac", "hook", "nest",
        "safety goggles", "chin", "flood", "manatee", "wick", "lightsaber", "yo-yo", "brain", "sponge", "contain",
        "gasoline", "save", "cheek", "magic carpet", "wax", "wreck", "fox", "salt and pepper", "back", "maze", "DVD",
        "printer", "page", "spear", "sleeve", "electrical outlet", "parachute", "kitchen", "squirt gun", "tape", "bottle",
        "coin", "flute", "nail", "draw", "baby", "ink", "pie", "window", "artist", "dog leash", "hippopotamus", "yacht",
        "desert", "oar", "brush", "dragonfly", "umbrella", "pineapple", "match", "bowtie", "black widow", "piranha",
        "bald eagle", "hair", "dump truck", "torch", "buggy", "platypus", "donkey", "paper clips", "vase", "skate",
        "forehead", "elephant", "snail", "reindeer", "school bus", "light switch", "oven", "unite", "password", "flagpole",
        "tower", "newlywed", "drumstick", "spell", "squirrel", "waterfall", "playground", "librarian", "cake", "neck",
        "screwdriver", "aquarium", "meteor", "ferry", "pulley", "pollution", "ceiling fan", "cave", "library", "read",
        "connect", "tissue", "pot", "curve", "field", "germ", "spoon", "quarter", "gum", "soda", "napkin", "ring",
        "windmill", "claw", "middle", "apologize", "church", "lake", "eclipse", "spaceship", "weight", "party",
        "ironing board", "starfish", "trumpet", "wheelchair", "lap", "outside", "purse", "jump", "popsicle", "mattress",
        "enter", "wooly mammoth", "restaurant", "storm", "bell", "happy", "mouse", "seaweed", "stapler", "smoke", "north",
        "hail", "video camera", "cello", "wrist", "rowboat", "wing", "fur", "meat", "mini blinds", "soap", "hummingbird",
        "mug", "ladder", "sheep", "onion", "stem", "television", "light bulb", "bus", "grandma", "spare", "baggage",
        "monkey", "saltwater", "grape", "zipper", "net", "roller blading", "easel", "pirate", "fishing pole", "bushes",
        "pantry", "apple pie", "beaver", "photograph", "porcupine", "railroad", "hug", "school", "wallet", "tuba", "pizza",
        "seashell", "lamp", "corner", "dock", "snowboarding", "boot", "mouth", "front porch", "collar", "cannon",
        "rainstorm", "pancake", "guitar", "face", "cougar", "prince", "horn", "porch", "lung", "wood", "thumb", "giant",
        "seed", "toy", "forest", "ribbon", "mold", "chimney", "frame", "crack", "blueprint", "museum", "waffle", "equator",
        "mitten", "half", "sack", "glass", "trash can", "doorknob", "pumpkin", "pitchfork", "melt", "throat", "cub",
        "necktie", "fern", "yardstick", "flashlight", "ski", "sail", "rainbow", "iron", "camera", "cash", "bucket",
        "shallow", "unicycle", "merry-go-round", "bell pepper", "corndog", "knight", "bagpipe", "whisk", "hen", "rock",
        "Ferris wheel", "bag", "garbage truck", "pine tree", "highway", "trunk", "scientist", "tent", "watering can",
        "muffin", "catfish", "vest", "propeller", "cliff", "hockey", "noon", "lipstick", "throne", "farmer", "clownfish",
        "frog", "root", "mailman", "jail", "coconut", "chart", "bakery", "hip", "fungus", "gold", "slope", "thief",
        "pillowcase", "battery", "gravity", "shark", "teapot", "gift", "hair dryer", "earmuffs", "baker", "bicycle", "jar",
        "island", "penguin", "mop", "hill", "swing", "snow", "chameleon", "soccer", "parka", "sit", "stove", "lighthouse",
        "shake", "mushroom", "crown", "TV", "sand", "notebook", "tongs", "leak", "windshield", "powder", "art", "hunter",
        "pinwheel", "horse", "ice", "park", "outer space", "stamp", "shelf", "sky", "fan", "gap", "open", "rope",
        "helicopter", "farm", "pretzel", "batteries", "lobster", "treasure", "spill", "pear", "sister", "backbone",
        "bacteria", "violin", "chocolate chip cookie", "stain", "present", "orphan", "timer", "stomach", "goose",
        "breakfast", "saw", "lunchbox", "saddle", "gumball", "spring", "jewelry", "sunset", "song", "college", "calendar",
        "deer", "target", "pogo stick", "canoe", "Jupiter", "tractor", "sneeze", "top hat", "tire", "gingerbread man",
        "pajamas", "doghouse", "cheetah", "teacher", "skirt", "neighbor", "paper", "newborn", "doctor", "magazine", "fist",
        "taxi", "belt", "baseball", "marker", "button", "east", "hourglass", "robin", "princess", "swim", "chain", "glove",
        "pen", "sidewalk", "plant", "seal", "run", "fork", "saxophone", "king", "rose", "muscle", "dollar", "tie",
        "trapeze", "astronaut", "third plate", "grill", "basket", "brick", "liquid", "stick", "tennis", "hurricane",
        "scarf", "river", "owl", "razor", "tongue", "road", "whistle", "tadpole", "waist", "sign", "goblin", "shade",
        "limousine", "rocking chair", "palace", "puppet", "bat", "pendulum", "bomb", "rug", "mirror", "straw", "deep",
        "drink", "family", "nun", "dolphin", "sunburn", "shoulder", "peanut", "trap", "well", "seahorse", "birthday cake",
        "paw", "money", "loaf", "cage", "worm"
    ]
    hard_words = [
        "jeans", "Heinz", "boulevard", "torch", "logo", "earthquake", "ticket", "wig", "dust bunny", "handle",
        "end zone", "macho", "barbershop", "toy store", "fireman pole", "ringleader", "glue gun", "chime", "competition",
        "cream", "university", "pigpen", "aircraft carrier", "coach", "chef", "clog", "pain", "parking garage", "tag",
        "edge", "rubber", "fortress", "gumball", "palace", "owner", "s'mores", "wedding cake", "staple", "hairspray",
        "grasslands", "diagonal", "saddle", "last", "dizzy", "plow", "humidity", "juggle", "fizz", "border", "religion",
        "quit", "newsletter", "swoop", "hot tub", "clique", "dodgeball", "cure", "airport security", "sash", "centimeter",
        "golf cart", "acrobat", "atlas", "skating rink", "tugboat", "peasant", "pet store", "vanilla", "sponge",
        "firefighter", "guarantee", "stage", "brand", "stationery", "fur", "landlord", "trombone", "sunrise", "testify",
        "vacation", "first class", "water cycle", "braid", "crow's nest", "wallow", "toddler", "heater", "shrew",
        "letter opener", "baguette", "parade", "cubicle", "zipper", "comfy", "groom", "ceiling fan", "fiddle", "freshman",
        "safe", "dent", "tin", "win", "car dealership", "imagine", "bride", "dryer sheets", "drip", "chess", "dress shirt",
        "beluga whale", "son-in-law", "violent", "sword swallower", "movie", "pilot", "yard", "best friend",
        "stutter", "tackle", "wobble", "mayor", "plastic", "laser", "junk", "correct", "foil", "nanny", "volleyball", "mast",
        "interception", "record", "runt", "concession stand", "tip", "servant", "thrift store", "dorsal", "snooze", "level",
        "expert", "invent", "economics", "bleach", "bedbug", "mirror", "trip", "cabin", "baggage", "yodel", "drain", "cowboy",
        "rib", "jaw", "pro", "downpour", "chariot", "elope", "deliver", "hipster", "rodeo", "cloak", "extension cord",
        "roller coaster", "pickup truck", "density", "pest", "homework", "carpenter", "commercial", "chariot racing",
        "cheerleader", "ivy", "softball", "bookend", "amusement park", "lung", "cot", "devious", "cockpit", "publisher",
        "page", "grandpa", "police", "wheelie", "prize", "quicksand", "bald", "hoop", "hovercraft", "cattle", "plank", "fog",
        "story", "mysterious", "taxes", "vehicle", "biscuit", "albatross", "sun block", "tide", "cable car", "punk", "produce",
        "chameleon", "download", "crane", "sleep", "soak", "drill bit", "trapped", "chisel", "customer", "wag", "gas station",
        "jazz", "back flip", "government", "dead end", "optometrist", "swarm", "chemical", "mat", "taxidermist", "hurdle",
        "advertisement", "loveseat", "blueprint", "mine", "birthday", "think", "engaged", "cliff diving", "propose", "pail",
        "irrigation", "manatee", "important", "peace", "yawn", "germ", "barber", "elf", "delivery", "somersault", "swing dancing",
        "team", "blush", "great-grandfather", "diver", "stuffed animal", "leather", "sneeze", "prime meridian", "hydrogen",
        "yak", "black belt", "rhythm", "clown", "sandbox", "ashamed", "sandpaper", "drawback", "sushi", "frost", "zoom",
        "check", "season", "taxi", "shrink ray", "rudder", "pile", "gold", "gown", "arcade", "world", "glitter", "driveway",
        "bobsled", "president", "cape", "lecture", "injury", "athlete", "toolbox", "bruise", "parent", "shack", "apathetic",
        "cruise ship", "van", "welder", "toothpaste", "time", "living room", "cuckoo clock", "ping pong", "shelter", "dream",
        "nap", "carnival", "cough", "steam", "molar", "seat", "cartoon", "tow truck", "ruby", "spare", "hang glider",
        "lipstick", "distance", "time machine", "hand soap", "speakers", "recycle", "headache", "half", "bonnet", "disc jockey",
        "vitamin", "thief", "script", "tiptoe", "baseboards", "fiance", "judge", "vein", "Internet", "musician", "putty",
        "stay", "art gallery", "roommate", "picnic", "cruise", "caviar", "edit", "macaroni", "tourist", "water buffalo",
        "haircut", "traffic jam", "salmon", "husband", "drive-through", "yardstick", "retail", "sheep dog", "dew", "applause",
        "ski lift", "clamp", "washing machine", "hospital", "factory", "drugstore", "lunar rover", "science", "photosynthesis",
        "avocado", "darts", "dawn", "drought", "telephone booth", "cliff", "coworker", "degree", "sunburn", "wrap", "tablespoon",
        "hour", "lunch tray", "earache", "icicle", "plantation", "goalkeeper", "sled", "pawn", "honk", "synchronized swimming",
        "student", "nightmare", "migrate", "receipt", "leak", "passenger", "sugar", "pharaoh", "reveal", "song", "character",
        "suit", "carat", "cherub", "sweater vest", "yacht", "mime", "chairman", "vegetarian", "hermit crab", "pocket", "startup",
        "cellar", "cheat", "banister", "fresh water", "scream", "robe", "lie", "country", "fabric", "koala", "crop duster",
        "jungle", "sticky note", "twist", "darkness", "tank", "wool", "spaceship", "oxcart", "gold medal", "rim", "puppet",
        "limit", "scuba diving", "runoff", "captain", "aunt", "quadrant", "crust", "shower curtain", "eighteen-wheeler", "wind",
        "geologist", "RV", "cardboard", "obey", "printer ink", "ornament", "cargo", "glue stick", "gasoline", "partner",
        "ratchet", "crime", "surround", "reservoir", "flock", "moth", "laundry detergent", "prey", "school", "videogame",
        "plumber", "ginger", "zoo", "ski goggles", "foam", "lullaby", "ream", "thaw", "front", "bookstore", "lumberyard",
        "lace", "double", "snag", "turtleneck", "Quidditch", "snore", "geyser", "coil", "crate", "print", "idea", "blizzard",
        "shampoo", "cello", "eraser", "trail", "dripping", "recess", "cell phone charger", "myth", "rind", "baby-sitter",
        "houseboat", "florist", "boxing", "hut", "midnight", "poison", "fireside", "stew", "tow", "cousin", "flu", "ounce",
        "landscape", "wax", "gallon", "learn", "goblin", "miner", "postcard", "professor", "knight", "carpet", "rut",
        "stopwatch", "fast food", "stage fright", "mascot", "grocery store", "stadium", "cleaning spray", "coastline", "right",
        "sap", "date", "calm", "mold", "monsoon", "kneel", "truck stop", "chestnut", "quartz", "full", "signal", "vet", "lance",
        "log-in", "pharmacist", "jigsaw", "password", "wooly mammoth", "stow", "omnivore", "neighborhood", "scuff mark",
        "cushion", "electrical outlet", "connection", "actor", "weather", "bargain", "oar", "thunder", "deep", "classroom",
        "fade", "exercise", "balance beam", "bulldog", "dashboard", "swamp", "boa constrictor", "chicken coop", "sweater",
        "dance", "hail", "post office", "organ", "lap", "dentist", "pizza sauce", "snarl", "point", "company", "tearful",
        "yolk", "catalog", "costume", "toll road", "CD", "beanstalk", "whisk", "chain mail", "Jedi", "compare", "vanish",
        "garden hose", "human", "conveyor belt", "raft", "flavor", "attack", "ditch", "orbit"
    ]
    extreme_words = [
        "castaway", "stowaway", "scatter", "rest stop", "con", "doubtful", "navigate", "diversify", "resourceful",
        "observatory", "philosopher", "danger", "today", "handful", "figment", "apparatus", "pride", "mine car", "zero",
        "cover", "name", "practice", "leap year", "gymnast", "population", "flight", "inquisition", "ornithologist",
        "infect", "digestion", "joke", "hay wagon", "sleet", "twang", "temper", "mortified", "addendum", "dictate",
        "income tax", "Everglades", "drift", "slump", "fake flowers", "sidekick", "quiver", "mooch", "stockholder",
        "eureka", "publisher", "discovery", "profit", "flutter", "climate", "fathom", "implode", "champion", "realm",
        "translate", "panic", "paranoid", "promise", "courthouse", "depth", "exhibition", "hypothermia", "insurance",
        "infection", "blueprint", "education", "voicemail", "hobby", "confide", "cloudburst", "ray", "rival", "first mate",
        "transpose", "blunt", "opinion", "vanquish", "try", "intern", "galaxy", "theory", "periwinkle", "blacksmith",
        "voice", "armada", "soul", "wasabi", "companion", "czar", "ironic", "channel", "reimbursement", "one-way street",
        "schedule", "brunette", "Zen", "guru", "regret", "interject", "debt", "loiterer", "Atlantis", "gallop", "telepathy",
        "offstage", "ice fishing", "index", "smidgen", "quarantine", "archaeologist", "parody", "ligament", "aftermath",
        "big bang theory", "reaction", "parley", "wormhole", "plot", "stranger", "gravel", "memory", "carat", "shame",
        "snag", "pastry", "landfill", "zip code", "stagecoach", "income", "opaque", "feeder road", "default", "forklift",
        "doubloon", "inertia", "turret", "soulmate", "consent", "rhyme", "friction", "haberdashery", "semester",
        "exponential", "cutlass", "disgust", "tribe", "preteen", "property", "wish", "bushel", "effect", "occupant",
        "writhe", "welder", "mayhem", "cause", "guess", "doppelganger", "fad", "mortal", "dud", "enemy", "community",
        "upgrade", "texture", "remain", "condition", "pelt", "steamboat", "credit", "compromise", "duvet", "sapphire",
        "tournament", "copyright", "error", "stun", "century", "fun", "trademark", "confidant", "punishment", "statement",
        "nutmeg", "deceive", "lyrics", "overture", "convenience store", "P.O. box", "dryer sheet", "fuel", "creator",
        "cartography", "layover", "junk drawer", "rainwater", "brainstorm", "random", "expired", "license", "rhythm",
        "emperor", "in-law", "wetlands", "altitude", "history", "sophomore", "jig", "crow's nest", "incisor", "doubt",
        "feeling", "sickle", "aristocrat", "siesta", "buccaneer", "whiplash", "fragment", "employee", "flotsam", "cubit",
        "tutor", "trawler", "destruction", "system", "clue", "demanding", "kilogram", "irrational", "villain", "knowledge",
        "password", "treatment", "vision", "time zone", "cartoonist", "representative", "Chick-fil-A", "gondola",
        "psychologist", "group", "inning", "admire", "grain", "riddle", "water vapor", "VIP", "standing ovation",
        "committee", "pen pal", "coast", "refund", "president", "good-bye", "food court", "interference", "cranium",
        "slam dunk", "prepare", "cramp", "tinting", "dugout", "emigrate", "decipher", "form", "cashier", "fowl", "protestant",
        "improve", "tug", "detail", "ma'am", "lichen", "hang ten", "pomp", "swag", "crisp", "positive", "problem", "chord",
        "destination", "comparison", "bed and breakfast", "zone defense", "reward", "ï»¿acoustics", "tattle", "stout",
        "crew", "dispatch", "title", "descendant", "freshwater", "risk", "chaos", "scalawag", "neutron", "steel drum",
        "stuff", "gentleman", "pawnshop", "wealth", "acre", "county fair", "silt", "language", "organization", "society",
        "fun house", "member", "retire", "hearse"
    ]
    if pictionary_difficulty == 'easy':
        print("Easy words selected")
        return random.choice(easy_words)
    elif pictionary_difficulty == 'medium':
        print("Medium words selected")
        return random.choice(medium_words)
    elif pictionary_difficulty == 'hard':
        print("Hard words selected")
        return random.choice(hard_words)
    else:
        return random.choice(easy_words)  # Default to easy if difficulty is invalid

def generate_custom_word():
    # Read custom words from a JSON file
    try:
        with open('custom_words.json', 'r') as file:
            custom_words = json.load(file)
            return random.choice(custom_words)
    except (FileNotFoundError, json.JSONDecodeError):
        # Fallback to a predefined word if the file is missing or invalid
        return "default_word"

@socketio.on('start_draw')
def handle_start_draw(data):
    emit('start_draw', data, broadcast=True, include_self=False)

@socketio.on('stop_draw')
def handle_stop_draw():
    emit('stop_draw', broadcast=True, include_self=False)

@socketio.on('draw')
def handle_draw(data):
    emit('draw', data, broadcast=True, include_self=False)

@socketio.on('fill')
def handle_fill(data):
    emit('fill', data, broadcast=True, include_self=False)

@socketio.on('undo_canvas')
def handle_undo_canvas():
    print("Undo canvas event received")
    emit('undo_canvas', broadcast=True, include_self=False)

@socketio.on('guess_pictionary')
def handle_guess_pictionary(data):
    username = data.get('username')
    guess = data.get('guess')

    if guess.lower() == pictionary['current_word'].lower():
        emit('pictionary_correct', {'username': username}, broadcast=True)
        
        # Announce the correct word to the chat
        emit('receive_message', {
            'username': 'Server',
            'profilePic': '',
            'message': f"{username} guessed correctly! The word was: {pictionary['current_word']}",
            'time': datetime.now().strftime('%H:%M')
        }, broadcast=True)
        
        # Show the end round screen with the word
        emit('round_end', {
            'word': pictionary['current_word'],
            'scores': [{'username': username, 'points': 10}]  # Simple scoring
        }, broadcast=True)
        
        emit('clear_canvas', broadcast=True)  # Clear the canvas for all players
        
        # Wait a few seconds before starting a new round
        socketio.sleep(5)
        start_new_round()  # Start a new round
    else:
        emit('pictionary_incorrect', {'username': username, 'guess': guess}, broadcast=True)

@socketio.on('clear_canvas')
def handle_clear_canvas():
    emit('clear_canvas', broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    user_id = request.sid
    for player in pictionary_players:
        if player['username'] == user_id:
            pictionary_players.remove(player)
            break

    # Reassign host if the current host leaves
    if any(player['isHost'] for player in pictionary_players):
        for player in pictionary_players:
            if player['isHost']:
                break
    elif pictionary_players:
        pictionary_players[0]['isHost'] = True
        emit('assign_host', {'isHost': True}, room=pictionary_players[0]['username'])

    emit('update_players', pictionary_players, broadcast=True)

pictionary_difficulty = 'easy'  # Default difficulty

@socketio.on('set_difficulty')
def handle_set_difficulty(data):
    global pictionary_difficulty
    username = data.get('username')
    difficulty = data.get('difficulty')

    # Only the host can set the difficulty
    for player in pictionary_players:
        if player['username'] == username and player['isHost']:
            pictionary_difficulty = difficulty
            emit('difficulty_updated', {'difficulty': pictionary_difficulty}, broadcast=True)
            break

# Add these variables to track game state
game_in_progress = False
end_game_votes = set()


@socketio.on('start_game')
def handle_start_game(data):
    global game_in_progress
    username = data.get('username')

    # Only host can start game if all players are ready and no game in progress
    for player in pictionary_players:
        if player['username'] == username and player['isHost']:
            if not all(player['ready'] for player in pictionary_players):
                emit('game_error', {'message': 'Not all players are ready'}, room=request.sid)
                return
            
            if game_in_progress:
                emit('game_error', {'message': 'Game already in progress'}, room=request.sid)
                return
                
            game_in_progress = True
            end_game_votes.clear()
            start_new_round()
            break

@socketio.on('vote_end_game')
def handle_vote_end_game(data):
    username = data.get('username')
    end_game_votes.add(username)
    
    # Check if all players voted to end
    if len(end_game_votes) == len(pictionary_players):
        emit('game_ended', broadcast=True)
        global game_in_progress
        game_in_progress = False
        end_game_votes.clear()
    else:
        # Update all clients with current vote count
        emit('end_game_votes', {'votes': len(end_game_votes), 'total': len(pictionary_players)}, broadcast=True)

@socketio.on('round_timeout')
def handle_round_timeout(data):
    word = data.get('word')
    
    # Send a system message to the Pictionary chat
    emit('pictionary_system_message', {
        'message': f"Time's up! The word was: {word}"
    }, broadcast=True)
    
    # Show the word in the game area
    emit('round_end', {
        'word': word,
        'scores': []  # You can add scoring logic here if desired
    }, broadcast=True)
    
    # Wait a few seconds before starting a new round
    socketio.sleep(5)
    start_new_round()

@socketio.on('draw_shape')
def handle_draw_shape(data):
    emit('draw_shape', data, broadcast=True, include_self=False)



# Submit custom word
@socketio.on('submit_custom_word')
def handle_submit_custom_word(data):
    custom_word = data.get('custom_word')
    if custom_word:
        # Append the new word to the custom words list
        try:
            with open('custom_words.json', 'r+') as file:
                try:
                    custom_words = json.load(file)
                except json.JSONDecodeError:
                    custom_words = []
                custom_words.append(custom_word)
                file.seek(0)
                json.dump(custom_words, file)
        except FileNotFoundError:
            with open('custom_words.json', 'w') as file:
                json.dump([custom_word], file)

        emit('custom_word_submitted', {'status': 'success'}, broadcast=True)
    else:
        emit('custom_word_submitted', {'status': 'error'}, broadcast=True)

# Read Custom_Words File
def read_custom_words():
    try:
        with open('custom_words.json', 'r') as file:
            custom_words = json.load(file)
            return custom_words
    except (FileNotFoundError, json.JSONDecodeError):
        return []

if __name__ == '__main__':
    socketio.run(app, debug=True)