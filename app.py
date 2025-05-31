import psycopg2
import bcrypt
from flask import Flask, request, jsonify

app = Flask(__name__)

DATABASE_URL = "postgresql://postgres:Reza4831@localhost:5432/postgres"


def get_db_connection():
    conn = psycopg2.connect("postgresql://postgres:Reza4831@localhost:5432/quiz_of_kings")
    return conn

def create_database():
    cursor = None
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()


        cursor.execute("""
        SELECT 1 FROM pg_database WHERE datname = 'quiz_of_kings';
        """)
        result = cursor.fetchone()

        if result:
            print("Database 'quiz_of_kings' already exists!")
        else:

            cursor.execute("CREATE DATABASE quiz_of_kings;")
            print("Database 'quiz_of_kings' created successfully!")

    except Exception as e:
        print("Error creating database:", e)

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_tables():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL,
            password TEXT NOT NULL,
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer CHAR(1) CHECK (correct_answer IN ('A', 'B', 'C', 'D')),
            category VARCHAR(50),
            difficulty VARCHAR(20) CHECK (difficulty IN ('easy', 'medium', 'hard')),
            author VARCHAR(100),
            approval_status VARCHAR(20) CHECK (approval_status IN ('pending', 'approved', 'rejected'))
        );
        """)

        cursor.execute("""
               CREATE TABLE IF NOT EXISTS sessions (
                   id SERIAL PRIMARY KEY,
                   player1_id INTEGER REFERENCES players(id),
                   player2_id INTEGER REFERENCES players(id),
                   status VARCHAR(20) CHECK (status IN ('active', 'completed')),
                   start_time TIMESTAMP,
                   end_time TIMESTAMP,
                   winner_id INTEGER REFERENCES players(id)
               );
               """)

        cursor.execute("""
              CREATE TABLE IF NOT EXISTS rounds (
                  id SERIAL PRIMARY KEY,
                  competition_id INTEGER REFERENCES sessions(id),
                  round_number INTEGER,
                  question_id INTEGER REFERENCES questions(id),
                  player1_answer CHAR(1) CHECK (player1_answer IN ('A', 'B', 'C', 'D')),
                  player2_answer CHAR(1) CHECK (player2_answer IN ('A', 'B', 'C', 'D')),
                  round_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
              );
              """)

        cursor.execute("""
               CREATE TABLE IF NOT EXISTS categories (
                   id SERIAL PRIMARY KEY,
                   name VARCHAR(100) NOT NULL
               );
               """)

        cursor.execute("""
                CREATE TABLE IF NOT EXISTS player_stats (
                    player_id INTEGER REFERENCES players(id) PRIMARY KEY,
                    games_played INTEGER DEFAULT 0,
                    games_won INTEGER DEFAULT 0,
                    accuracy DECIMAL(5, 2) DEFAULT 0,
                    rank INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0
                );
                """)

        cursor.execute("""
           CREATE TABLE IF NOT EXISTS leaderboard (
               player_id INTEGER REFERENCES players(id),
               score INTEGER,
               ranking_type VARCHAR(20) CHECK (ranking_type IN ('weekly', 'monthly', 'all_time')),
               rank INTEGER,
               PRIMARY KEY (player_id, ranking_type)
           );
           """)

        cursor.execute("""
              CREATE TABLE IF NOT EXISTS admin_tools (
                  admin_id INTEGER REFERENCES players(id),
                  manage_questions BOOLEAN DEFAULT FALSE,
                  block_users BOOLEAN DEFAULT FALSE,
                  PRIMARY KEY (admin_id)
              );
              """)

        conn.commit()
        print("Tables created successfully!")

    except Exception as e:
        print("Error creating tables:", e)

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data['username']
    email = data['email']
    password = data['password']

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO players (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, hashed_password))
        conn.commit()
        return jsonify({"message": "User registered successfully!"}), 201
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({"error": f"Error: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data['username']
    password = data['password']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT password FROM players WHERE username = %s", (username,))
    stored_password = cursor.fetchone()

    if stored_password is None:
        return jsonify({"message": "User not found"}), 404

    if bcrypt.checkpw(password.encode('utf-8'), stored_password[0].encode('utf-8')):
        return jsonify({"message": "Login successful!"}), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 400

    cursor.close()
    conn.close()



@app.route('/players', methods=['GET'])
def get_players():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM players;")
    players = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(players), 200


@app.route('/start_session', methods=['POST'])
def start_session():
    data = request.get_json()
    player1_id = data['player1_id']
    player2_id = data['player2_id']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO sessions (player1_id, player2_id, status, start_time) 
    VALUES (%s, %s, 'active', CURRENT_TIMESTAMP) RETURNING id;
    """, (player1_id, player2_id))
    session_id = cursor.fetchone()[0]
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Session started", "session_id": session_id}), 201


@app.route('/add_question', methods=['POST'])
def add_question():
    data = request.get_json()
    question_text = data['question_text']
    option_a = data['option_a']
    option_b = data['option_b']
    option_c = data['option_c']
    option_d = data['option_d']
    correct_answer = data['correct_answer']
    category = data['category']
    difficulty = data['difficulty']
    author = data['author']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO questions (question_text, option_a, option_b, option_c, option_d, correct_answer, category, difficulty, author, approval_status)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending');
    """, (question_text, option_a, option_b, option_c, option_d, correct_answer, category, difficulty, author))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Question added successfully!"}), 201


@app.route('/approve_question', methods=['POST'])
def approve_question():
    data = request.get_json()
    question_id = data['question_id']
    approval_status = data['approval_status']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE questions 
    SET approval_status = %s 
    WHERE id = %s;
    """, (approval_status, question_id))
    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Question status updated"}), 200


@app.route('/end_session', methods=['POST'])
def end_session():
    data = request.get_json()
    session_id = data['session_id']
    winner_id = data['winner_id']
    player1_id = data['player1_id']
    player2_id = data['player2_id']
    player1_score = data['player1_score']
    player2_score = data['player2_score']

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE sessions 
    SET status = 'completed', end_time = CURRENT_TIMESTAMP, winner_id = %s 
    WHERE id = %s;
    """, (winner_id, session_id))

    cursor.execute("""
    INSERT INTO player_stats (player_id, games_played, games_won, xp, rank)
    VALUES (%s, 1, 1, %s, (SELECT COUNT(*) FROM player_stats WHERE xp > %s) + 1)
    ON CONFLICT (player_id) 
    DO UPDATE 
    SET games_played = player_stats.games_played + 1, 
        games_won = player_stats.games_won + 1,
        xp = player_stats.xp + %s;
    """, (winner_id, player1_score, player1_score, player1_score))

    cursor.execute("""
    INSERT INTO player_stats (player_id, games_played, games_won, xp, rank)
    VALUES (%s, 1, 0, %s, (SELECT COUNT(*) FROM player_stats WHERE xp > %s) + 1)
    ON CONFLICT (player_id) 
    DO UPDATE 
    SET games_played = player_stats.games_played + 1, 
        xp = player_stats.xp + %s;
    """, (player2_id, player2_score, player2_score, player2_score))


    cursor.execute("""
    INSERT INTO leaderboard (player_id, score, ranking_type, rank)
    VALUES (%s, %s, 'all_time', 
            (SELECT COUNT(*) FROM leaderboard WHERE score > %s) + 1)
    ON CONFLICT (player_id, ranking_type) 
    DO UPDATE 
    SET score = EXCLUDED.score;
    """, (winner_id, player1_score, player1_score))

    cursor.execute("""
    INSERT INTO leaderboard (player_id, score, ranking_type, rank)
    VALUES (%s, %s, 'all_time', 
            (SELECT COUNT(*) FROM leaderboard WHERE score > %s) + 1)
    ON CONFLICT (player_id, ranking_type) 
    DO UPDATE 
    SET score = EXCLUDED.score;
    """, (player2_id, player2_score, player2_score))

    conn.commit()

    cursor.close()
    conn.close()

    return jsonify({"message": "Session ended and statistics updated"}), 200


@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    ranking_type = request.args.get('ranking_type', default='all_time', type=str)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT players.username, leaderboard.score, leaderboard.rank
    FROM leaderboard
    JOIN players ON leaderboard.player_id = players.id
    WHERE leaderboard.ranking_type = %s
    ORDER BY leaderboard.rank ASC;
    """, (ranking_type,))

    leaderboard = cursor.fetchall()
    cursor.close()
    conn.close()

    if leaderboard:
        return jsonify(leaderboard), 200
    else:
        return jsonify({"message": "No leaderboard data found for the specified ranking type."}), 404


if __name__ == '__main__':
    create_database()
    create_tables()
    app.run(debug=True)
