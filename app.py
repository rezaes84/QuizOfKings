from flask import Flask, render_template, request, jsonify, redirect, url_for, session, abort
import psycopg2
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)

DATABASE_URL = "postgresql://postgres:Reza4831@localhost:5432/postgres"


MAX_ROUNDS = 3
MAX_QUESTIONS_PER_PLAYER_PER_ROUND = 3



def get_db_connection():

    return psycopg2.connect("postgresql://postgres:Reza4831@localhost:5432/quiz_of_kings")


def create_tables():

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()



        cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id SERIAL PRIMARY KEY,
            username VARCHAR(100) UNIQUE NOT NULL,
            email VARCHAR(100) NOT NULL,
            password TEXT NOT NULL, 
            registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked BOOLEAN DEFAULT FALSE
        );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE
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
            category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT, 
            difficulty VARCHAR(20) CHECK (difficulty IN ('easy', 'medium', 'hard')),
            author VARCHAR(100),
            approval_status VARCHAR(20) CHECK (approval_status IN ('pending', 'approved', 'rejected'))
        );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                player1_id INTEGER REFERENCES players(id),
                player2_id INTEGER REFERENCES players(id) DEFAULT NULL,
                status VARCHAR(50) CHECK (status IN ('active', 'completed', 'waiting_for_player2' , 'waiting_for_player1_category_selection' ,'waiting_for_player2_category_selection', 'finished', 'cancelled')), 
                start_time TIMESTAMP DEFAULT NULL,
                end_time TIMESTAMP DEFAULT NULL,
                winner_id INTEGER REFERENCES players(id) DEFAULT NULL, 
                category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT DEFAULT NULL, 
                current_round INTEGER DEFAULT 1,
                player1_answered_questions_current_round INTEGER DEFAULT 0,
                player2_answered_questions_current_round INTEGER DEFAULT 0,
                next_category_chooser_id INTEGER REFERENCES players(id) DEFAULT NULL
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rounds (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES sessions(id),
                round_number INTEGER,
                question_id INTEGER REFERENCES questions(id),
                player1_answer CHAR(1) CHECK (player1_answer IN ('A', 'B', 'C', 'D', '')), 
                player2_answer CHAR(1) CHECK (player2_answer IN ('A', 'B', 'C', 'D', '')), 
                round_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                question_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (session_id, round_number, question_id) 
            );
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_states (
                player_id INTEGER REFERENCES players(id) PRIMARY KEY,
                games_played INTEGER DEFAULT 0,
                games_won INTEGER DEFAULT 0,
                games_drawn INTEGER DEFAULT 0, 
                accuracy DECIMAL(5, 2) DEFAULT 0, 
                rank INTEGER DEFAULT 1, 
                xp INTEGER DEFAULT 0,
                total_questions_answered INTEGER DEFAULT 0,
                total_correct_answers INTEGER DEFAULT 0
            );
        """)

        cursor.execute("""
           CREATE TABLE IF NOT EXISTS leaderboard (
               player_id INTEGER REFERENCES players(id),
               score INTEGER,
               ranking_type VARCHAR(20) CHECK (ranking_type IN ('weekly', 'monthly', 'all_time' , 'win_rate')),
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_answers (
                id SERIAL PRIMARY KEY,
                session_id INTEGER REFERENCES sessions(id),      
                player_id INTEGER REFERENCES players(id),          
                question_id INTEGER REFERENCES questions(id),    
                round_number INTEGER,                            
                submitted_answer CHAR(1) CHECK (submitted_answer IN ('A', 'B', 'C', 'D', '')), 
                is_correct BOOLEAN,                              
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP    
            );
        """)

        conn.commit()
        print("Tables created successfully!")

    except Exception as e:
        print("Error creating tables:", e)
        if conn:
            conn.rollback()

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']


        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:

            cursor.execute("INSERT INTO players (username, email, password) VALUES (%s, %s, %s);",
                           (username, email, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except psycopg2.IntegrityError:
            return "نام کاربری یا ایمیل قبلاً ثبت شده است.", 400
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        try:

            cursor.execute("SELECT id, username, password, email, is_blocked FROM players WHERE username = %s;",
                           (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user[2], password):
                if user[4]:
                    return "حساب کاربری شما مسدود شده است.", 403

                session['user_id'] = user[0]
                session['username'] = user[1]
                session['email'] = user[3]
                return redirect(url_for('profile'))
            else:
                return "نام کاربری یا رمز عبور اشتباه است.", 401
        finally:
            cursor.close()
            conn.close()
    return render_template('login.html')


def update_player_ranks():

    conn = get_db_connection()
    cursor = conn.cursor()
    try:

        cursor.execute("SELECT player_id, xp FROM player_states ORDER BY xp DESC;")
        all_players_xp = cursor.fetchall()

        current_rank = 0
        previous_xp = -1

        for i, (player_id, xp) in enumerate(all_players_xp):
            if xp != previous_xp:
                current_rank = i + 1


            cursor.execute("UPDATE player_states SET rank = %s WHERE player_id = %s;", (current_rank, player_id))
            previous_xp = xp

        conn.commit()
        print("DEBUG: Player ranks updated successfully based on XP in player_states.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Failed to update player ranks: {e}")
    finally:
        cursor.close()
        conn.close()


def update_leaderboard_table():

    conn = get_db_connection()
    cursor = conn.cursor()
    try:

        cursor.execute("DELETE FROM leaderboard WHERE ranking_type = 'all_time';")
        cursor.execute("""
            INSERT INTO leaderboard (player_id, score, ranking_type, rank)
            SELECT ps.player_id, ps.xp, 'all_time', ps.rank
            FROM player_states ps
            ORDER BY ps.rank ASC, ps.xp DESC;
        """)
        print("DEBUG: All-Time Leaderboard updated.")


        one_week_ago = datetime.now() - timedelta(days=7)
        cursor.execute("DELETE FROM leaderboard WHERE ranking_type = 'weekly';")
        cursor.execute("""
            WITH weekly_scores AS (
                SELECT
                    pa.player_id,
                    SUM(CASE WHEN pa.is_correct = TRUE THEN 1 ELSE 0 END) AS weekly_correct_answers
                FROM
                    player_answers pa
                WHERE
                    pa.timestamp >= %s
                GROUP BY
                    pa.player_id
            ),
            ranked_weekly_scores AS (
                SELECT
                    ws.player_id,
                    ws.weekly_correct_answers AS score,
                    RANK() OVER (ORDER BY ws.weekly_correct_answers DESC) AS rank
                FROM
                    weekly_scores ws
            )
            INSERT INTO leaderboard (player_id, score, ranking_type, rank)
            SELECT player_id, score, 'weekly', rank
            FROM ranked_weekly_scores
            WHERE score > 0; -- Only include players with at least one correct answer
        """, (one_week_ago,))
        print("DEBUG: Weekly Leaderboard updated.")


        one_month_ago = datetime.now() - timedelta(days=30)
        cursor.execute("DELETE FROM leaderboard WHERE ranking_type = 'monthly';")
        cursor.execute("""
            WITH monthly_scores AS (
                SELECT
                    pa.player_id,
                    SUM(CASE WHEN pa.is_correct = TRUE THEN 1 ELSE 0 END) AS monthly_correct_answers
                FROM
                    player_answers pa
                WHERE
                    pa.timestamp >= %s
                GROUP BY
                    pa.player_id
            ),
            ranked_monthly_scores AS (
                SELECT
                    ms.player_id,
                    ms.monthly_correct_answers AS score,
                    RANK() OVER (ORDER BY ms.monthly_correct_answers DESC) AS rank
                FROM
                    monthly_scores ms
            )
            INSERT INTO leaderboard (player_id, score, ranking_type, rank)
            SELECT player_id, score, 'monthly', rank
            FROM ranked_monthly_scores
            WHERE score > 0; -- Only include players with at least one correct answer
        """, (one_month_ago,))
        print("DEBUG: Monthly Leaderboard updated.")


        cursor.execute("DELETE FROM leaderboard WHERE ranking_type = 'win_rate';")
        cursor.execute("""
            WITH win_rates AS (
                SELECT
                    ps.player_id,
                    ps.games_played,
                    ps.games_won,
                    (CASE
                        WHEN ps.games_played > 0 THEN (CAST(ps.games_won AS DECIMAL) * 100.0 / ps.games_played)
                        ELSE 0.0
                    END) AS win_rate_percentage
                FROM
                    player_states ps
                WHERE
                    ps.games_played > 0 -- Only consider players who have played games
            ),
            ranked_win_rates AS (
                SELECT
                    wr.player_id,
                    CAST(wr.win_rate_percentage AS INTEGER) AS score, -- Store as integer percentage
                    RANK() OVER (ORDER BY wr.win_rate_percentage DESC, wr.games_won DESC) AS rank -- Rank by percentage, then by wins
                FROM
                    win_rates wr
            )
            INSERT INTO leaderboard (player_id, score, ranking_type, rank)
            SELECT player_id, score, 'win_rate', rank
            FROM ranked_win_rates;
        """)
        print("DEBUG: Win Rate Leaderboard updated.")


        conn.commit()
        print("DEBUG: All leaderboards updated successfully.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Failed to update leaderboards: {e}")
    finally:
        cursor.close()
        conn.close()



def check_admin_permission(user_id, permission_type):

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if permission_type == 'manage_questions':
            cursor.execute("SELECT manage_questions FROM admin_tools WHERE admin_id = %s;", (user_id,))
        elif permission_type == 'block_users':
            cursor.execute("SELECT block_users FROM admin_tools WHERE admin_id = %s;", (user_id,))
        else:
            return False

        permission = cursor.fetchone()
        return permission[0] if permission else False
    except Exception as e:
        print(f"ERROR: Failed to check admin permission for user {user_id}, type {permission_type}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def assign_initial_admin(admin_username):

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM players WHERE username = %s;", (admin_username,))
        admin_id = cursor.fetchone()
        if admin_id:
            admin_id = admin_id[0]
            cursor.execute(
                "INSERT INTO admin_tools (admin_id, manage_questions, block_users) VALUES (%s, TRUE, TRUE) ON CONFLICT (admin_id) DO UPDATE SET manage_questions = TRUE, block_users = TRUE;",
                (admin_id,))
            conn.commit()
            print(f"Admin permissions granted to {admin_username} (ID: {admin_id}).")
        else:
            print(f"User {admin_username} not found. Cannot assign admin permissions.")
    except Exception as e:
        conn.rollback()
        print(f"Error assigning initial admin: {e}")
    finally:
        cursor.close()
        conn.close()


@app.route('/profile')
def profile():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    player_id = session['user_id']
    username = session['username']
    email = session.get('email', 'N/A')

    conn = get_db_connection()
    cursor = conn.cursor()
    player_states = None


    can_manage_questions = check_admin_permission(player_id, 'manage_questions')
    can_block_users = check_admin_permission(player_id, 'block_users')


    is_admin_user = can_manage_questions or can_block_users

    try:

        cursor.execute(
            "SELECT games_played, games_won, games_drawn, accuracy, xp, rank, total_questions_answered, total_correct_answers FROM player_states WHERE player_id = %s;",
            (player_id,))
        player_states_raw = cursor.fetchone()

        if player_states_raw is None:

            print(f"DEBUG: No player_states found for player {player_id}. Inserting default entry.")
            cursor.execute("INSERT INTO player_states (player_id) VALUES (%s);", (player_id,))
            conn.commit()

            cursor.execute(
                "SELECT games_played, games_won, games_drawn, accuracy, xp, rank, total_questions_answered, total_correct_answers FROM player_states WHERE player_id = %s;",
                (player_id,))
            player_states_raw = cursor.fetchone()
            if player_states_raw:
                print(f"DEBUG: Default player_states created and fetched for player {player_id}: {player_states_raw}")
            else:
                print(f"ERROR: Failed to create or refetch player_states for player {player_id} after insert attempt.")

        if player_states_raw:
            games_played = player_states_raw[0]
            games_won = player_states_raw[1]
            games_drawn = player_states_raw[2]
            accuracy = player_states_raw[3]
            xp = player_states_raw[4]
            rank = player_states_raw[5]
            total_questions_answered = player_states_raw[6]
            total_correct_answers = player_states_raw[7]


            games_lost = games_played - games_won - games_drawn
            if games_lost < 0:
                games_lost = 0


            if games_lost > 0:
                win_loss_ratio = games_won / games_lost
            else:
                win_loss_ratio = float(
                    'inf') if games_won > 0 else 0.0

            player_states = {
                'games_played': games_played,
                'games_won': games_won,
                'games_drawn': games_drawn,
                'games_lost': games_lost,
                'win_loss_ratio': win_loss_ratio,
                'accuracy': accuracy,
                'xp': xp,
                'rank': rank,
                'total_questions_answered': total_questions_answered,
                'total_correct_answers': total_correct_answers
            }


        active_game_info = []
        if not is_admin_user:
            cursor.execute("""
                SELECT s.id, s.player1_id, s.player2_id, s.status, s.current_round, s.category_id, c.name as category_name
                FROM sessions s
                LEFT JOIN categories c ON s.category_id = c.id
                WHERE (s.player1_id = %s OR s.player2_id = %s) AND s.status NOT IN ('finished', 'cancelled');
            """, (player_id, player_id))
            active_games = cursor.fetchall()

            for game in active_games:
                session_id, p1_id, p2_id, status, current_round, category_id, category_name = game
                opponent_id = p2_id if p1_id == player_id else p1_id

                opponent_username = "منتظر بازیکن..."
                if opponent_id:
                    cursor.execute("SELECT username FROM players WHERE id = %s;", (opponent_id,))
                    op_user = cursor.fetchone()
                    if op_user:
                        opponent_username = op_user[0]

                active_game_info.append({
                    'session_id': session_id,
                    'opponent_username': opponent_username,
                    'status': status,
                    'current_round': current_round,
                    'category': category_name,
                    'category_id': category_id
                })

        return render_template('profile.html',
                               username=username,
                               email=email,
                               player_states=player_states,
                               active_games=active_game_info,
                               is_admin_user=is_admin_user,
                               can_access_admin_dashboard=is_admin_user
                               )
    except Exception as e:
        print(f"Error loading profile: {e}")
        return "خطا در بارگذاری پروفایل", 500
    finally:
        cursor.close()
        conn.close()


@app.route('/logout')
def logout():

    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('email', None)
    session.pop('current_game_session_id', None)
    return redirect(url_for('index'))


@app.route('/request_game', methods=['POST'])
def request_game():

    if 'user_id' not in session:
        return jsonify({"message": "ابتدا وارد شوید.", "success": False}), 401

    player1_id = session['user_id']


    if check_admin_permission(player1_id, 'manage_questions') or check_admin_permission(player1_id, 'block_users'):
        return jsonify({"message": "کاربران ادمین نمی‌توانند بازی جدید درخواست دهند.", "success": False}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM sessions WHERE player1_id = %s AND status = 'waiting_for_player2';",
                       (player1_id,))
        existing_session = cursor.fetchone()
        if existing_session:
            return jsonify({
                "message": "شما در حال حاضر منتظر یک بازی هستید.",
                "session_id": existing_session[0],
                "redirect_to": url_for('waiting_for_game', session_id=existing_session[0]),
                "success": True
            }), 200


        cursor.execute("""
            INSERT INTO sessions (player1_id, status, current_round)
            VALUES (%s, 'waiting_for_player2', 1) RETURNING id;
        """, (player1_id,))
        session_id = cursor.fetchone()[0]
        conn.commit()
        return jsonify({
            "message": "درخواست بازی ثبت شد، در انتظار بازیکن دوم...",
            "session_id": session_id,
            "redirect_to": url_for('waiting_for_game', session_id=session_id),
            "success": True
        }), 201
    except Exception as e:
        conn.rollback()
        print(f"Error requesting game: {e}")
        return jsonify({"message": f"خطا در درخواست بازی: {str(e)}", "success": False}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/game_requests')
def game_requests():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    player_id = session['user_id']


    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return "کاربران ادمین نمی‌توانند درخواست‌های بازی را مشاهده کنند.", 403

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.id, p1.username
            FROM sessions s
            JOIN players p1 ON s.player1_id = p1.id
            WHERE s.player2_id IS NULL 
              AND s.status = 'waiting_for_player2' 
              AND s.player1_id != %s;
        """, (player_id,))

        requests = cursor.fetchall()

        game_request_list = []
        for req_id, p1_username in requests:
            game_request_list.append({'session_id': req_id, 'player1_username': p1_username})

        print(f"DEBUG: Game requests for user {player_id}: {game_request_list}")

        return render_template('game_requests.html', requests=game_request_list)
    except Exception as e:
        print(f"Error fetching game requests: {e}")
        return "خطا در دریافت درخواست‌های بازی", 500
    finally:
        cursor.close()
        conn.close()


@app.route('/accept_game', methods=['POST'])
def accept_game():

    if 'user_id' not in session:
        return jsonify({"message": "ابتدا وارد شوید.", "success": False}), 401

    player2_id = session['user_id']

    if check_admin_permission(player2_id, 'manage_questions') or check_admin_permission(player2_id, 'block_users'):
        return jsonify({"message": "کاربران ادمین نمی‌توانند بازی‌ها را بپذیرند.", "success": False}), 403

    data = request.get_json()
    session_id = data.get('session_id')

    if not session_id:
        return jsonify({"message": "شناسه جلسه بازی الزامی است.", "success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:

        cursor.execute("""
            UPDATE sessions
            SET player2_id = %s, status = 'waiting_for_player2_category_selection', start_time = NOW(),
                next_category_chooser_id = %s -- تنظیم انتخاب‌کننده اولیه
            WHERE id = %s AND status = 'waiting_for_player2' AND player2_id IS NULL RETURNING id;
        """, (player2_id, player2_id, session_id))

        updated_session_id = cursor.fetchone()
        if updated_session_id:
            conn.commit()
            print(
                f"DEBUG: In /accept_game, session {session_id} accepted by player {player2_id}. Status set to waiting_for_player2_category_selection. Initial chooser: {player2_id}")
            return jsonify({
                "message": "بازی پذیرفته شد. انتخاب دسته‌بندی...",
                "success": True,
                "redirect_to": url_for('select_category_page', session_id=session_id, next_round=False)
            }), 200
        else:
            conn.rollback()
            return jsonify({"message": "بازی یافت نشد یا قابل پذیرش نیست.", "success": False}), 400
    except Exception as e:
        conn.rollback()
        print(f"Error accepting game: {e}")
        return jsonify({"message": f"خطا در پذیرش بازی: {str(e)}", "success": False}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/waiting_for_game/<int:session_id>')
def waiting_for_game(session_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return "کاربران ادمین نمی‌توانند در بازی شرکت کنند.", 403

    session['current_game_session_id'] = session_id

    return render_template('waiting_for_game.html', session_id=session_id, user_id=session['user_id'])


@app.route('/check_game_status/<int:session_id>')
def check_game_status(session_id):
    # مسیر بررسی وضعیت بازی
    if 'user_id' not in session:
        return jsonify({"message": "ابتدا وارد شوید.", "success": False}), 401

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return jsonify({"message": "کاربران ادمین نمی‌توانند وضعیت بازی را بررسی کنند.", "success": False}), 403

    conn = get_db_connection()
    cursor = conn.cursor()
    try:

        cursor.execute(
            "SELECT status, category_id, current_round, player1_id, player2_id, player1_answered_questions_current_round, player2_answered_questions_current_round, next_category_chooser_id FROM sessions WHERE id = %s;",
            (session_id,))
        session_data = cursor.fetchone()

        if not session_data:
            print(f"DEBUG: check_game_status - Session {session_id} not found in DB.")
            return jsonify({"message": "جلسه بازی یافت نشد.", "status": "error", "success": False}), 404

        status, category_id, current_round, player1_id, player2_id, p1_answered_db, p2_answered_db, next_category_chooser_id_db = session_data
        user_id = session['user_id']


        category_name = None
        if category_id:
            cursor.execute("SELECT name FROM categories WHERE id = %s;", (category_id,))
            cat_name_result = cursor.fetchone()
            if cat_name_result:
                category_name = cat_name_result[0]

        is_round_finished = (p1_answered_db >= MAX_QUESTIONS_PER_PLAYER_PER_ROUND and
                             p2_answered_db >= MAX_QUESTIONS_PER_PLAYER_PER_ROUND)

        print(
            f"DEBUG: check_game_status - Session ID: {session_id}, Current Round: {current_round}, Status: {status}, Category ID: {category_id}, Category Name: {category_name}")
        print(f"DEBUG: check_game_status - P1_ID: {player1_id}, P2_ID: {player2_id}, Current User: {user_id}")
        print(
            f"DEBUG: check_game_status - P1 Answered (DB): {p1_answered_db}, P2 Answered (DB): {p2_answered_db}, Max Q: 3")
        print(f"DEBUG: check_game_status - Is Round Finished? {is_round_finished}")

        print(f"DEBUG: check_game_status - Next Category Chooser ID (from DB): {next_category_chooser_id_db}")

        status_message = ""
        if status == 'active':
            status_message = "بازی فعال است."
        elif status == 'waiting_for_player2':
            status_message = "در انتظار بازیکن دوم..."
        elif status == 'waiting_for_player1_category_selection':
            status_message = "راند به پایان رسید. در انتظار انتخاب دسته‌بندی توسط بازیکن اول..."
        elif status == 'waiting_for_player2_category_selection':
            status_message = "بازیکن مقابل در حال انتخاب دسته‌بندی است..."
        elif status == 'cancelled':
            status_message = "بازی لغو شد."
        elif status == 'finished':
            status_message = "بازی به پایان رسید!"

        game_over_flag = (status == 'finished')

        return jsonify({
            "session_id": session_id,
            "status": status,
            "category": category_name,
            "category_id": category_id,
            "current_round": current_round,
            "player1_id": player1_id,
            "player2_id": player2_id,
            "player1_answered_questions_current_round": p1_answered_db,
            "player2_answered_questions_current_round": p2_answered_db,
            "is_round_finished": is_round_finished,
            "next_category_chooser_id": next_category_chooser_id_db,
            "status_message": status_message,
            "success": True,
            "game_over": game_over_flag
        }), 200

    except Exception as e:
        print(f"Error checking game status: {e}")
        return jsonify({"message": f"خطا در بررسی وضعیت بازی: {str(e)}", "status": "error", "success": False}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/select_category_page')
def select_category_page():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return "کاربران ادمین نمی‌توانند دسته‌بندی انتخاب کنند.", 403

    session_id = request.args.get('session_id')
    current_user_id = session.get('user_id')

    conn = get_db_connection()
    cursor = conn.cursor()
    categories = []
    try:
        cursor.execute("SELECT name FROM categories;")
        categories = [row[0] for row in cursor.fetchall()]
        print(f"DEBUG: Retrieved categories: {categories}")
    except Exception as e:
        print(f"Error fetching categories: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    is_chooser = False

    if current_user_id is None:
        print("WARN: session['user_id'] is None in select_category_page, redirecting to login.")
        return redirect(url_for('login'))

    try:
        current_user_id = int(current_user_id)
    except (TypeError, ValueError):
        print(
            f"ERROR: session['user_id'] is not a valid integer: {session.get('user_id')}, type: {type(session.get('user_id'))}. Redirecting to login.")
        return redirect(url_for('login'))

    if session_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:

            cursor.execute("SELECT next_category_chooser_id FROM sessions WHERE id = %s;", (session_id,))
            chooser_id_from_db = cursor.fetchone()

            if chooser_id_from_db:
                actual_chooser_id = chooser_id_from_db[0]

                is_chooser = (current_user_id == actual_chooser_id)

                print(f"DEBUG: select_category_page - Determining is_chooser for Session {session_id}.")
                print(f"DEBUG: select_category_page - Current User ID (session): {current_user_id}")
                print(f"DEBUG: select_category_page - Actual Chooser ID (from DB): {actual_chooser_id}")
                print(f"DEBUG: select_category_page - Setting is_chooser = {is_chooser}.")

            else:
                print(
                    f"DEBUG: Session {session_id} not found or next_category_chooser_id is NULL in select_category_page.")
                is_chooser = False
        except Exception as e:
            print(f"Error checking chooser status in select_category_page: {e}")
            is_chooser = False
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    print(f"DEBUG: select_category_page - Final is_chooser: {is_chooser}, categories: {categories}")

    return render_template('select_category.html',
                           categories=categories,
                           session_id=session_id,
                           is_chooser=is_chooser,
                           user_id=current_user_id)


@app.route('/select_category_and_start_game', methods=['POST'])
def select_category_and_start_game():

    if 'user_id' not in session:
        return jsonify({"message": "ابتدا وارد شوید.", "success": False}), 401

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return jsonify({"message": "کاربران ادمین نمی‌توانند بازی شروع کنند.", "success": False}), 403


    data = request.get_json()
    session_id = data.get('session_id')
    selected_category_name = data.get('category')

    if not session_id or not selected_category_name:
        return jsonify({"message": "دسته و شناسه جلسه الزامی است.", "success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:

        cursor.execute("SELECT id FROM categories WHERE name = %s;", (selected_category_name,))
        category_id_result = cursor.fetchone()
        if not category_id_result:
            return jsonify({"message": "دسته‌بندی انتخاب شده معتبر نیست.", "success": False}), 400
        selected_category_id = category_id_result[0]

        cursor.execute("SELECT player1_id, player2_id, current_round, status, next_category_chooser_id FROM sessions WHERE id = %s;", (session_id,))
        session_info = cursor.fetchone()
        if not session_info:
            print(f"ERROR: select_category_and_start_game - Session ID {session_id} not found.")
            return jsonify({"message": "جلسه بازی یافت نشد.", "success": False}), 404

        p1_id, p2_id, current_round_db, session_status_db, next_category_chooser_id_db = session_info

        print(f"DEBUG: select_category_and_start_game - User {player_id} attempting to select category.")
        print(f"DEBUG: select_category_and_start_game - Session ID: {session_id}, Current Round (DB): {current_round_db}, Status (DB): {session_status_db}")
        print(f"DEBUG: select_category_and_start_game - P1 ID: {p1_id}, P2 ID: {p2_id}, Current Player ID: {player_id}")
        print(f"DEBUG: select_category_and_start_game - Next Category Chooser ID (from DB): {next_category_chooser_id_db}")


        is_allowed_chooser = (player_id == next_category_chooser_id_db)

        if not is_allowed_chooser:
            print(f"WARN: select_category_and_start_game - Player {player_id} attempted to choose category but it's not their turn. Expected Chooser: {next_category_chooser_id_db}.")
            return jsonify({"message": "نوبت شما برای انتخاب دسته‌بندی نیست. بازیکن مقابل باید انتخاب کند.", "success": False}), 403


        print(f"DEBUG: {player_id} (chooser) selecting {MAX_QUESTIONS_PER_PLAYER_PER_ROUND} common questions for Round {current_round_db}...")


        cursor.execute("""
            SELECT id FROM questions 
            WHERE category_id = %s AND approval_status = 'approved' ORDER BY RANDOM() LIMIT %s;
        """, (selected_category_id, MAX_QUESTIONS_PER_PLAYER_PER_ROUND))

        selected_question_ids = [row[0] for row in cursor.fetchall()]

        if not selected_question_ids:
            return jsonify({"message": "هیچ سوالی در این دسته‌بندی یافت نشد. لطفاً دسته‌بندی دیگری را انتخاب کنید.", "success": False}), 404


        for q_id in selected_question_ids:
            try:
                cursor.execute("""
                    INSERT INTO rounds (session_id, round_number, question_id, player1_answer, player2_answer, question_start_time)
                    VALUES (%s, %s, %s, '', '', NOW())
                    ON CONFLICT (session_id, round_number, question_id) DO NOTHING;
                """, (session_id, current_round_db, q_id))
                conn.commit()
                print(f"DEBUG: Inserted common question {q_id} for Session {session_id}, Round {current_round_db} into rounds table.")
            except Exception as insert_e:
                conn.rollback()
                print(f"ERROR: Failed to insert common question {q_id} into rounds table: {insert_e}")



        cursor.execute("""
            UPDATE sessions
            SET category_id = %s, status = 'active'
            WHERE id = %s RETURNING current_round;
        """, (selected_category_id, session_id))

        updated_session = cursor.fetchone()
        if updated_session:
            current_round = updated_session[0]
            conn.commit()
            print(f"DEBUG: select_category_and_start_game - Session {session_id} updated for new Round {current_round} with category ID {selected_category_id}. Status set to 'active'.")
            return jsonify({
                "message": "دسته انتخاب شد. بازی شروع می‌شود.",
                "success": True,
                "redirect_to": url_for('game', session_id=session_id, category_id=selected_category_id, current_round=current_round)
            }), 200
        else:
            conn.rollback()
            print(f"ERROR: select_category_and_start_game - Session {session_id} not found or category could not be updated.")
            return jsonify({"message": "جلسه بازی یافت نشد یا دسته قابل به‌روزرسانی نیست.", "success": False}), 400
    except Exception as e:
        conn.rollback()
        print(f"CRITICAL ERROR: select_category_and_start_game - Error selecting category and starting game: {e}")
        return jsonify({"message": f"خطا در انتخاب دسته: {str(e)}", "success": False}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/game')
def game():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return "کاربران ادمین نمی‌توانند وارد بازی شوند.", 403

    session_id = request.args.get('session_id')
    category_id_from_url = request.args.get('category_id', type=int)
    initial_round = request.args.get('current_round', 1, type=int)

    if not session_id:
        print(f"ERROR: Missing session_id in /game route. session_id: {session_id}")
        return "پارامترهای بازی ناقص هستند.", 400

    conn = get_db_connection()
    cursor = conn.cursor()
    current_round_from_db = 1
    category_name_for_display = None
    category_id_for_display = None

    try:

        cursor.execute("SELECT current_round, category_id FROM sessions WHERE id = %s;", (session_id,))
        session_info_db = cursor.fetchone()

        if not session_info_db:
            print(f"ERROR: /game route - Session {session_id} not found in DB. Returning 404.")
            return "بازی یافت نشد یا منقضی شده است.", 404

        current_round_from_db = session_info_db[0]
        category_id_from_db = session_info_db[1]

        if category_id_from_db:

            cursor.execute("SELECT name FROM categories WHERE id = %s;", (category_id_from_db,))
            cat_name_result = cursor.fetchone()
            if cat_name_result:
                category_name_for_display = cat_name_result[0]
                category_id_for_display = category_id_from_db

        print(
            f"DEBUG: /game route - Session {session_id} loaded. DB Round: {current_round_from_db}, DB Category ID: {category_id_from_db}, Display Category: {category_name_for_display}")

        return render_template('game.html',
                               session_id=session_id,
                               initial_category=category_name_for_display,
                               initial_category_id=category_id_for_display,
                               initial_round=current_round_from_db,
                               user_id=session['user_id'])

    except Exception as e:
        print(f"Error getting current round/category for game page from DB: {e}")
        return f"خطا در بارگذاری صفحه بازی: {str(e)}", 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route('/get_questions_by_category')
def get_questions_by_category():

    if 'user_id' not in session:
        return jsonify({"message": "ابتدا وارد شوید.", "success": False}), 401

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return jsonify({"message": "کاربران ادمین مجاز به دریافت سوالات بازی نیستند.", "success": False}), 403


    category_id = request.args.get('category_id', type=int)
    session_id = request.args.get('session_id')
    round_number = request.args.get('round')

    print(
        f"DEBUG: get_questions_by_category called - Category ID: {category_id}, Session ID: {session_id}, Round: {round_number}")

    if category_id is None or not session_id or not round_number:
        print(
            f"ERROR: Missing or invalid parameters in get_questions_by_category: category_id='{category_id}', session_id='{session_id}', round_number='{round_number}'")
        return jsonify({"message": "پارامترهای ناقص یا نامعتبر برای دریافت سوالات.", "success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    questions_data = []
    try:

        cursor.execute("""
            SELECT q.id, q.question_text, q.option_a, q.option_b, q.option_c, q.option_d, q.correct_answer 
            FROM rounds r
            JOIN questions q ON r.question_id = q.id
            WHERE r.session_id = %s AND r.round_number = %s; 
        """, (session_id, round_number))

        questions_raw = cursor.fetchall()
        print(
            f"DEBUG: Retrieved {len(questions_raw)} questions for Session {session_id}, Round {round_number} from rounds table.")

        if not questions_raw:
            print(
                f"WARN: No questions found in 'rounds' table for Session {session_id}, Round {round_number}. This might indicate a problem with category selection flow.")
            return jsonify({
                               "message": "سوالات برای این راند بارگذاری نشده‌اند. لطفاً دسته‌بندی را دوباره انتخاب کنید یا منتظر بمانید.",
                               "success": False}), 404

        for q_id, q_text, op_a, op_b, op_c, op_d, correct_ans in questions_raw:
            questions_data.append({
                "id": q_id,
                "question_text": q_text,
                "option_a": op_a,
                "option_b": op_b,
                "option_c": op_c,
                "option_d": op_d,
                "correct_answer": correct_ans
            })

        return jsonify({"questions": questions_data, "success": True}), 200

    except Exception as e:
        print(f"Error getting questions by category (from rounds table): {e}")
        return jsonify({"message": f"خطا در دریافت سوالات: {str(e)}", "success": False}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/submit_answer', methods=['POST'])
def submit_answer():

    if 'user_id' not in session:
        return jsonify({"message": "ابتدا وارد شوید.", "success": False}), 401

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return jsonify({"message": "کاربران ادمین مجاز به ثبت پاسخ نیستند.", "success": False}), 403

    data = request.get_json()
    try:
        session_id = int(data.get('session_id'))
        question_id = int(data.get('question_id'))
        submitted_answer = data.get('answer')
        round_number_from_client = int(data.get('round_number'))
    except (TypeError, ValueError) as e:
        print(f"DEBUG: submit_answer data parsing error: {e}")
        return jsonify({"message": "اطلاعات ناقص یا نامعتبر است.", "success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:

        cursor.execute(
            "SELECT player1_id, player2_id, current_round, category_id, player1_answered_questions_current_round, player2_answered_questions_current_round FROM sessions WHERE id = %s;",
            (session_id,))
        game_session_data = cursor.fetchone()
        if not game_session_data:
            print(f"DEBUG: submit_answer - Session ID {session_id} not found.")
            return jsonify({"message": "جلسه بازی یافت نشد.", "success": False}), 404

        player1_id, player2_id, current_round_db, current_category_id, p1_answered_before_update, p2_answered_before_update = game_session_data

        print(
            f"DEBUG: submit_answer - Session ID: {session_id}, Round (DB): {current_round_db}, Category ID (DB): {current_category_id}")
        print(f"DEBUG: submit_answer - Question ID (Client): {question_id}, Round (Client): {round_number_from_client}")
        print(
            f"DEBUG: submit_answer - Current Player: {player_id}, P1_ID in DB: {player1_id}, P2_ID in DB: {player2_id}")
        print(
            f"DEBUG: submit_answer - Counters BEFORE update: P1={p1_answered_before_update}, P2={p2_answered_before_update}")

        if round_number_from_client != current_round_db:
            print(
                f"DEBUG: submit_answer - Round number mismatch! Client: {round_number_from_client}, DB: {current_round_db}. Allowing to proceed but this indicates client-side sync issue.")
            pass


        cursor.execute("SELECT correct_answer FROM questions WHERE id = %s;", (question_id,))
        question_info = cursor.fetchone()

        if question_info is None:
            print(f"DEBUG: submit_answer - Question with ID {question_id} not found in questions table.")
            is_correct = False
        else:
            correct_answer = question_info[0]
            is_correct = (submitted_answer == correct_answer)


        cursor.execute("""
            INSERT INTO player_answers (session_id, player_id, question_id, submitted_answer, is_correct, round_number)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (session_id, player_id, question_id, submitted_answer, is_correct, round_number_from_client))


        if player_id == player1_id:
            cursor.execute("""
                UPDATE sessions
                SET player1_answered_questions_current_round = player1_answered_questions_current_round + 1
                WHERE id = %s;
            """, (session_id,))
            print(f"DEBUG: submit_answer - Player 1 ({player_id}) answered. Attempted increment.")
        elif player_id == player2_id:
            cursor.execute("""
                UPDATE sessions
                SET player2_answered_questions_current_round = player2_answered_questions_current_round + 1
                WHERE id = %s;
            """, (session_id,))
            print(f"DEBUG: submit_answer - Player 2 ({player_id}) answered. Attempted increment.")
        else:
            print(f"DEBUG: submit_answer - Player ID {player_id} not found in session {session_id}.")
            return jsonify({"message": "بازیکن در این جلسه شناسایی نشد.", "success": False}), 403


        current_total_answered = 0
        current_total_correct = 0

        cursor.execute("SELECT total_questions_answered, total_correct_answers FROM player_states WHERE player_id = %s;",
                       (player_id,))
        stats_before_update = cursor.fetchone()

        if stats_before_update:
            current_total_answered = stats_before_update[0] + 1
            current_total_correct = stats_before_update[1] + (1 if is_correct else 0)
        else:

            cursor.execute(
                "INSERT INTO player_states (player_id, total_questions_answered, total_correct_answers) VALUES (%s, %s, %s);",
                (player_id, 1, (1 if is_correct else 0)))
            conn.commit()
            current_total_answered = 1
            current_total_correct = (1 if is_correct else 0)

        new_accuracy = (current_total_correct / current_total_answered) * 100 if current_total_answered > 0 else 0

        cursor.execute("""
            UPDATE player_states
            SET total_questions_answered = %s,
                total_correct_answers = %s,
                accuracy = %s
            WHERE player_id = %s;
        """, (current_total_answered, current_total_correct, new_accuracy, player_id))

        conn.commit()
        print(
            f"DEBUG: submit_answer - Player {player_id} stats updated. Total Answered: {current_total_answered}, Correct: {current_total_correct}, Accuracy: {new_accuracy:.2f}%")

        cursor.execute(
            "SELECT player1_answered_questions_current_round, player2_answered_questions_current_round FROM sessions WHERE id = %s;",
            (session_id,))
        p1_answered_after_update, p2_answered_after_update = cursor.fetchone()
        print(
            f"DEBUG: submit_answer - Counters AFTER update (from DB): P1={p1_answered_after_update}, P2={p2_answered_after_update}")

        return jsonify({"message": "پاسخ با موفقیت ثبت شد.", "success": True, "is_correct": is_correct}), 200

    except Exception as e:
        conn.rollback()
        print(f"Error submitting answer: {e}")
        return jsonify({"message": f"خطا در ثبت پاسخ: {str(e)}", "success": False}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/end_round_and_prepare_next', methods=['POST'])
def end_round_and_prepare_next():
    if 'user_id' not in session:
        return jsonify({"message": "ابتدا وارد شوید.", "success": False}), 401

    player_id = session['user_id']
    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return jsonify({"message": "کاربران ادمین مجاز به پایان رساندن راند نیستند.", "success": False}), 403

    data = request.get_json()
    try:
        session_id = int(data.get('session_id'))
        round_number_from_client = int(data.get('round_number'))
    except (TypeError, ValueError) as e:
        print(f"DEBUG: end_round_and_prepare_next data parsing error: {e}")
        return jsonify({"message": "اطلاعات ناقص یا نامعتبر است.", "success": False}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT player1_id, player2_id, current_round, player1_answered_questions_current_round, player2_answered_questions_current_round, status FROM sessions WHERE id = %s;",
            (session_id,))
        session_info = cursor.fetchone()
        if not session_info:
            return jsonify({"message": "جلسه بازی یافت نشد.", "success": False}), 404

        player1_id, player2_id, current_round_db, p1_answered_db, p2_answered_db, session_status_db = session_info

        print(f"DEBUG /end_round_and_prepare_next: Session {session_id}, Round (DB): {current_round_db}")
        print(
            f"DEBUG /end_round_and_prepare_next: P1 Answered (from DB): {p1_answered_db}, P2 Answered (from DB): {p2_answered_db}")
        print(f"DEBUG /end_round_and_prepare_next: Current User ID: {player_id}")

        if round_number_from_client != current_round_db:
            print(
                f"DEBUG: end_round_and_prepare_next - Round number mismatch! Client: {round_number_from_client}, DB: {current_round_db}. Allowing to proceed but this indicates client-side sync issue.")
            pass

        is_player1_finished_round = (p1_answered_db >= MAX_QUESTIONS_PER_PLAYER_PER_ROUND)
        is_player2_finished_round = (p2_answered_db >= MAX_QUESTIONS_PER_PLAYER_PER_ROUND)

        print(
            f"DEBUG /end_round_and_prepare_next: Is P1 Finished? {is_player1_finished_round}, Is P2 Finished? {is_player2_finished_round}")

        next_category_chooser_id = None

        if (current_round_db + 1) % 2 == 0:
            next_category_chooser_id = player2_id
        else:
            next_category_chooser_id = player1_id

        print(
            f"DEBUG /end_round_and_prepare_next: Next Chooser ID for Round {current_round_db + 1}: {next_category_chooser_id}")

        if is_player1_finished_round and is_player2_finished_round:

            print(f"DEBUG: Both players finished round {current_round_db}. Updating rounds table entries.")


            cursor.execute("""
                SELECT DISTINCT question_id
                FROM player_answers
                WHERE session_id = %s AND round_number = %s;
            """, (session_id, current_round_db))
            question_ids_in_round = [row[0] for row in cursor.fetchall()]

            for q_id in question_ids_in_round:
                p1_ans = ''
                p2_ans = ''


                cursor.execute("""
                    SELECT submitted_answer
                    FROM player_answers
                    WHERE session_id = %s AND round_number = %s AND question_id = %s AND player_id = %s
                    ORDER BY timestamp DESC LIMIT 1;
                """, (session_id, current_round_db, q_id, player1_id))
                p1_res = cursor.fetchone()
                if p1_res:
                    p1_ans = p1_res[0]


                cursor.execute("""
                    SELECT submitted_answer
                    FROM player_answers
                    WHERE session_id = %s AND player_id = %s AND question_id = %s AND round_number = %s
                    ORDER BY timestamp DESC LIMIT 1;
                """, (session_id, player2_id, q_id, round_number_from_client))  # استفاده از round_number_from_client
                p2_res = cursor.fetchone()
                if p2_res:
                    p2_ans = p2_res[0]

                try:
                    cursor.execute("""
                        UPDATE rounds
                        SET player1_answer = %s, player2_answer = %s, round_time = NOW()
                        WHERE session_id = %s AND round_number = %s AND question_id = %s;
                    """, (p1_ans, p2_ans, session_id, current_round_db, q_id))
                    conn.commit()
                    print(
                        f"DEBUG: Updated rounds table for QID {q_id}, Round {current_round_db}: P1={p1_ans}, P2={p2_ans}")
                except Exception as update_rounds_e:
                    conn.rollback()
                    print(f"ERROR: Failed to update rounds table for QID {q_id}: {update_rounds_e}")


            next_round_number = current_round_db + 1

            if current_round_db >= MAX_ROUNDS:
                print(f"DEBUG: Game over! Session {session_id} completed {MAX_ROUNDS} rounds.")

                cursor.execute("""
                    SELECT player_id, SUM(CASE WHEN is_correct = TRUE THEN 1 ELSE 0 END) AS score
                    FROM player_answers
                    WHERE session_id = %s
                    GROUP BY player_id;
                """, (session_id,))

                scores_raw = cursor.fetchall()
                p1_final_score = 0
                p2_final_score = 0

                for p_id, score in scores_raw:
                    if p_id == player1_id:
                        p1_final_score = score
                    elif p_id == player2_id:
                        p2_final_score = score

                winner_id = None
                game_outcome = "draw"
                if p1_final_score > p2_final_score:
                    winner_id = player1_id
                    game_outcome = "win"
                elif p2_final_score > p1_final_score:
                    winner_id = player2_id
                    game_outcome = "win"
                else:
                    game_outcome = "draw"

                print(
                    f"DEBUG: Final Scores - P1({player1_id}): {p1_final_score}, P2({player2_id}): {p2_final_score}, Winner: {winner_id}, Outcome: {game_outcome}")

                players_to_update = [player1_id, player2_id]
                for p_id in players_to_update:
                    cursor.execute("SELECT 1 FROM player_states WHERE player_id = %s;", (p_id,))
                    if cursor.fetchone() is None:
                        cursor.execute("INSERT INTO player_states (player_id) VALUES (%s);", (p_id,))
                        conn.commit()

                cursor.execute("UPDATE player_states SET games_played = games_played + 1 WHERE player_id = %s;",
                               (player1_id,))
                cursor.execute("UPDATE player_states SET games_played = games_played + 1 WHERE player_id = %s;",
                               (player2_id,))


                if game_outcome == "win":
                    winner_xp = 50
                    loser_xp = 20
                    if winner_id == player1_id:
                        cursor.execute("UPDATE player_states SET xp = xp + %s WHERE player_id = %s;",
                                       (winner_xp, player1_id))
                        cursor.execute("UPDATE player_states SET xp = xp + %s WHERE player_id = %s;",
                                       (loser_xp, player2_id))
                    else:
                        cursor.execute("UPDATE player_states SET xp = xp + %s WHERE player_id = %s;",
                                       (winner_xp, player2_id))
                        cursor.execute("UPDATE player_states SET xp = xp + %s WHERE player_id = %s;",
                                       (loser_xp, player1_id))
                    cursor.execute("UPDATE player_states SET games_won = games_won + 1 WHERE player_id = %s;",
                                   (winner_id,))
                    print(
                        f"DEBUG: XP awarded: Winner ({winner_id}) +{winner_xp}, Loser ({'player1' if winner_id == player2_id else 'player2'}) +{loser_xp}")
                elif game_outcome == "draw":
                    draw_xp = 10
                    cursor.execute(
                        "UPDATE player_states SET xp = xp + %s, games_drawn = games_drawn + 1 WHERE player_id = %s;",
                        (draw_xp, player1_id))
                    cursor.execute(
                        "UPDATE player_states SET xp = xp + %s, games_drawn = games_drawn + 1 WHERE player_id = %s;",
                        (draw_xp, player2_id))
                    print(f"DEBUG: XP awarded: Draw, both players +{draw_xp}. Games drawn incremented.")


                cursor.execute("""
                    UPDATE sessions
                    SET status = 'finished', end_time = NOW(), winner_id = %s, category_id = NULL, next_category_chooser_id = NULL -- پاک کردن دسته‌بندی و انتخاب‌کننده در پایان بازی
                    WHERE id = %s;
                """, (winner_id, session_id))
                conn.commit()


                update_player_ranks()

                update_leaderboard_table()

                print(
                    f"DEBUG: Game session {session_id} finished. Stats updated for players {player1_id} and {player2_id}.")
                return jsonify({
                    "message": "بازی به پایان رسید! مشاهده نتایج.",
                    "success": True,
                    "game_over": True,
                    "p1_score": p1_final_score,
                    "p2_score": p2_final_score,
                    "winner_id": winner_id,
                    "redirect_to": url_for('game_results', session_id=session_id)
                }), 200

            else:
                new_status = 'waiting_for_player1_category_selection'
                if next_category_chooser_id == player2_id:
                    new_status = 'waiting_for_player2_category_selection'

                cursor.execute("""
                    UPDATE sessions
                    SET status = %s, 
                        current_round = %s, 
                        player1_answered_questions_current_round = 0, 
                        player2_answered_questions_current_round = 0,
                        category_id = NULL, -- پاک کردن دسته‌بندی برای راند بعدی
                        next_category_chooser_id = %s -- تنظیم انتخاب‌کننده بعدی در DB
                    WHERE id = %s;
                """, (new_status, next_round_number, next_category_chooser_id,
                      session_id))
                conn.commit()
                print(
                    f"DEBUG /end_round_and_prepare_next: Both players finished. Session status updated to '{new_status}' for Round {next_round_number}. Category cleared. Round number incremented in DB. Next Chooser ID saved: {next_category_chooser_id}.")

                return jsonify({
                    "message": "راند به پایان رسید. نوبت شماست که دسته‌بندی راند بعدی را انتخاب کنید." if player_id == next_category_chooser_id else "راند به پایان رسید. در انتظار انتخاب دسته‌بندی توسط بازیکن مقابل...",
                    "success": True,
                    "redirect_to": None,
                    "next_category_chooser_id": next_category_chooser_id,
                    "status_update": new_status,
                    "current_round_number": next_round_number
                }), 200
        else:
            print(
                f"DEBUG /end_round_and_prepare_next: Player {player_id} finished. Waiting for other player to finish round.")
            return jsonify({
                "message": "راند شما به پایان رسید. در انتظار بازیکن مقابل برای پایان راند...",
                "success": True,
                "waiting_for_other_player": True,
                "next_category_chooser_id": next_category_chooser_id
            }), 200

    except Exception as e:
        conn.rollback()
        print(f"CRITICAL ERROR: end_round_and_prepare_next - Error ending round: {e}")
        return jsonify({"message": f"خطا در پایان راند: {str(e)}", "success": False}), 500
    finally:
        cursor.close()
        conn.close()


@app.route('/game_results/<int:session_id>')
def game_results(session_id):

    if 'user_id' not in session:
        return redirect(url_for('login'))

    player_id = session['user_id']

    if check_admin_permission(player_id, 'manage_questions') or check_admin_permission(player_id, 'block_users'):
        return "کاربران ادمین مجاز به مشاهده نتایج بازی نیستند.", 403

    conn = get_db_connection()
    cursor = conn.cursor()

    session_info = None
    try:
        cursor.execute("SELECT player1_id, player2_id, current_round, status, winner_id FROM sessions WHERE id = %s;",
                       (session_id,))
        session_info = cursor.fetchone()

        if not session_info:
            return "بازی یافت نشد.", 404

        player1_id, player2_id, current_round, status, winner_id_db = session_info

        if status != 'finished':
            return "بازی هنوز به پایان نرسیده یا نتایج آن در دسترس نیست.", 400

        cursor.execute("SELECT id, username FROM players WHERE id IN (%s, %s);", (player1_id, player2_id))
        players_data = cursor.fetchall()
        players_map = {p_id: username for p_id, username in players_data}

        p1_username = players_map.get(player1_id, f"Unknown User {player1_id}")
        p2_username = players_map.get(player2_id, f"Unknown User {player2_id}")

        cursor.execute("""
            SELECT player_id, SUM(CASE WHEN is_correct = TRUE THEN 1 ELSE 0 END) AS score
            FROM player_answers
            WHERE session_id = %s
            GROUP BY player_id;
        """, (session_id,))
        scores_raw = cursor.fetchall()
        p1_final_score = 0
        p2_final_score = 0

        for p_id, score in scores_raw:
            if p_id == player1_id:
                p1_final_score = score
            elif p_id == player2_id:
                p2_final_score = score

        winner_message = ""
        if winner_id_db == player1_id:
            winner_message = f"برنده: {p1_username}"
        elif winner_id_db == player2_id:
            winner_message = f"برنده: {p2_username}"
        else:
            winner_message = "نتیجه: تساوی"


        reviewed_questions = []

        cursor.execute("""
            SELECT
                r.round_number,
                q.id AS question_id,
                q.question_text,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_answer
            FROM rounds r
            JOIN questions q ON r.question_id = q.id
            WHERE r.session_id = %s
            ORDER BY r.round_number ASC, r.id ASC; 
        """, (session_id,))
        game_questions = cursor.fetchall()

        for round_num, q_id, q_text, op_a, op_b, op_c, op_d, correct_ans in game_questions:
            question_data = {
                'round_number': round_num,
                'question_id': q_id,
                'question_text': q_text,
                'option_a': op_a,
                'option_b': op_b,
                'option_c': op_c,
                'option_d': op_d,
                'correct_answer': correct_ans,
                'player1_answer': {'submitted': '', 'is_correct': False},
                'player2_answer': {'submitted': '', 'is_correct': False}
            }


            cursor.execute("""
                SELECT submitted_answer, is_correct
                FROM player_answers
                WHERE session_id = %s AND player_id = %s AND question_id = %s AND round_number = %s
                ORDER BY timestamp DESC LIMIT 1;
            """, (session_id, player1_id, q_id, round_num))
            p1_ans_data = cursor.fetchone()
            if p1_ans_data:
                question_data['player1_answer']['submitted'] = p1_ans_data[0]
                question_data['player1_answer']['is_correct'] = p1_ans_data[1]


            cursor.execute("""
                SELECT submitted_answer, is_correct
                FROM player_answers
                WHERE session_id = %s AND player_id = %s AND question_id = %s AND round_number = %s
                ORDER BY timestamp DESC LIMIT 1;
            """, (session_id, player2_id, q_id, round_num))
            p2_ans_data = cursor.fetchone()
            if p2_ans_data:
                question_data['player2_answer']['submitted'] = p2_ans_data[0]
                question_data['player2_answer']['is_correct'] = p2_ans_data[1]

            reviewed_questions.append(question_data)


        return render_template('game_results.html',
                               session_id=session_id,
                               p1_username=p1_username,
                               p2_username=p2_username,
                               p1_final_score=p1_final_score,
                               p2_final_score=p2_final_score,
                               winner_message=winner_message,
                               reviewed_questions=reviewed_questions,
                               MAX_QUESTIONS_PER_PLAYER_PER_ROUND=MAX_QUESTIONS_PER_PLAYER_PER_ROUND)
    except Exception as e:
        print(f"Error fetching game results: {e}")
        return f"خطا در بارگذاری نتایج بازی: {str(e)}", 500
    finally:
        cursor.close()
        conn.close()


@app.route('/leaderboard')
def leaderboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))


    ranking_type = request.args.get('type', 'all_time')

    conn = get_db_connection()
    cursor = conn.cursor()
    top_players = []
    try:

        cursor.execute("""
            SELECT 
                l.rank, 
                p.username, 
                l.score, 
                ps.games_played, 
                ps.games_won, 
                ps.games_drawn, 
                ps.accuracy
            FROM leaderboard l
            JOIN players p ON l.player_id = p.id
            LEFT JOIN player_states ps ON l.player_id = ps.player_id 
            WHERE l.ranking_type = %s
            ORDER BY l.rank ASC, l.score DESC
            LIMIT 10;
        """, (ranking_type,))
        top_players_raw = cursor.fetchall()

        for rank, username, score, games_played, games_won, games_drawn, accuracy in top_players_raw:

            current_games_played = games_played if games_played is not None else 0
            current_games_won = games_won if games_won is not None else 0
            current_games_drawn = games_drawn if games_drawn is not None else 0
            current_accuracy = accuracy if accuracy is not None else 0.0

            current_games_lost = current_games_played - current_games_won - current_games_drawn
            if current_games_lost < 0:
                current_games_lost = 0

            current_win_loss_ratio = 0.0
            if current_games_lost > 0:
                current_win_loss_ratio = current_games_won / current_games_lost
            elif current_games_won > 0:
                current_win_loss_ratio = float('inf')


            display_win_loss_ratio = "%.2f" % current_win_loss_ratio if current_win_loss_ratio != float('inf') else '∞'

            #
            display_score = score
            if ranking_type == 'win_rate':
                display_score = f"{score}%"

            top_players.append({
                'rank': rank,
                'username': username,
                'score': display_score,
                'games_played': current_games_played,
                'games_won': current_games_won,
                'games_drawn': current_games_drawn,
                'games_lost': current_games_lost,
                'win_loss_ratio': display_win_loss_ratio,
                'accuracy': "%.2f" % current_accuracy
            })


        return render_template('players_leaderboard.html',
                               top_players=top_players,
                               current_ranking_type=ranking_type)
    except Exception as e:
        print(f"Error fetching players leaderboard for type '{ranking_type}': {e}")
        return "خطا در بارگذاری جدول رده‌بندی بازیکنان", 500
    finally:
        cursor.close()
        conn.close()


@app.route('/top_categories')
def top_categories():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    top_categories_data = []
    try:

        cursor.execute("""
            SELECT
                cat.name,
                COUNT(DISTINCT r.session_id || '-' || r.round_number) AS rounds_played_count
            FROM
                rounds r
            JOIN
                questions q ON r.question_id = q.id
            JOIN
                categories cat ON q.category_id = cat.id 
            WHERE
                q.category_id IS NOT NULL AND q.approval_status = 'approved'
            GROUP BY
                cat.name
            ORDER BY
                rounds_played_count DESC
            LIMIT 3;
        """)
        top_categories_raw = cursor.fetchall()

        for category_name, count in top_categories_raw:
            top_categories_data.append({
                'name': category_name,
                'count': count
            })
        print(f"DEBUG: Top categories fetched (corrected logic - counting rounds): {top_categories_data}")

        return render_template('top_categories_leaderboard.html', top_categories=top_categories_data)
    except Exception as e:
        print(f"Error fetching top categories (corrected logic): {e}")
        return "خطا در بارگذاری دسته‌بندی‌های برتر", 500
    finally:
        cursor.close()
        conn.close()


@app.route('/add_question', methods=['GET', 'POST'])
def add_question():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    categories = []
    message = ""

    try:
        cursor.execute("SELECT name FROM categories ORDER BY name;")
        categories = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching categories for add_question page: {e}")
        message = "خطا در بارگذاری دسته‌بندی‌ها."

    if request.method == 'POST':
        question_text = request.form['question_text']
        option_a = request.form['option_a']
        option_b = request.form['option_b']
        option_c = request.form['option_c']
        option_d = request.form['option_d']
        correct_answer = request.form['correct_answer']
        category_name = request.form['category']
        difficulty = request.form['difficulty']
        author_username = session.get('username')

        if not all([question_text, option_a, option_b, option_c, option_d, correct_answer, category_name, difficulty,
                    author_username]):
            message = "لطفاً تمام فیلدها را پر کنید."
            return render_template('add_question.html', categories=categories, difficulties=['easy', 'medium', 'hard'],
                                   message=message)

        try:

            cursor.execute("SELECT id FROM categories WHERE name = %s;", (category_name,))
            category_id_result = cursor.fetchone()
            if not category_id_result:
                message = "دسته‌بندی انتخاب شده معتبر نیست. لطفاً یک دسته‌بندی موجود را انتخاب کنید."
                return render_template('add_question.html', categories=categories,
                                       difficulties=['easy', 'medium', 'hard'], message=message)

            category_id = category_id_result[0]

            cursor.execute("""
                INSERT INTO questions (question_text, option_a, option_b, option_c, option_d, correct_answer, category_id, difficulty, author, approval_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending');
            """, (question_text, option_a, option_b, option_c, option_d, correct_answer, category_id, difficulty,
                  author_username))
            conn.commit()
            message = "سوال شما با موفقیت اضافه شد و در انتظار تأیید است."
            return render_template('add_question.html', categories=categories, difficulties=['easy', 'medium', 'hard'],
                                   message=message, submitted_successfully=True)

        except Exception as e:
            conn.rollback()
            print(f"Error adding question: {e}")
            message = f"خطا در افزودن سوال: {str(e)}"

    return render_template('add_question.html', categories=categories, difficulties=['easy', 'medium', 'hard'],
                           message=message)



@app.route('/admin_dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if not (check_admin_permission(user_id, 'manage_questions') or check_admin_permission(user_id, 'block_users')):
        abort(403)

    return render_template('admin_dashboard.html',
                           can_manage_questions=check_admin_permission(user_id, 'manage_questions'),
                           can_block_users=check_admin_permission(user_id, 'block_users'))



@app.route('/admin/manage_questions', methods=['GET', 'POST'])
def admin_manage_questions():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if not check_admin_permission(user_id, 'manage_questions'):
        abort(403)

    conn = get_db_connection()
    cursor = conn.cursor()
    message = ""

    if request.method == 'POST':
        action = request.form.get('action')
        question_id = request.form.get('question_id', type=int)

        if question_id is None:
            message = "شناسه سوال نامعتبر است."
        elif action == 'approve':
            try:
                cursor.execute("UPDATE questions SET approval_status = 'approved' WHERE id = %s;", (question_id,))
                conn.commit()
                message = f"سوال {question_id} با موفقیت تأیید شد."
            except Exception as e:
                conn.rollback()
                message = f"خطا در تأیید سوال: {e}"
        elif action == 'reject':
            try:
                cursor.execute("UPDATE questions SET approval_status = 'rejected' WHERE id = %s;", (question_id,))
                conn.commit()
                message = f"سوال {question_id} با موفقیت رد شد."
            except Exception as e:
                conn.rollback()
                message = f"خطا در رد سوال: {e}"
        else:
            message = "عملیات نامعتبر است."

    questions = []
    try:

        cursor.execute("""
            SELECT q.id, q.question_text, c.name as category_name, q.difficulty, q.author, q.approval_status 
            FROM questions q
            JOIN categories c ON q.category_id = c.id
            ORDER BY q.approval_status ASC, q.id DESC;
        """)
        questions_raw = cursor.fetchall()
        for q_id, text, cat_name, diff, auth, status in questions_raw:
            questions.append({
                'id': q_id,
                'text': text,
                'category': cat_name,
                'difficulty': diff,
                'author': auth,
                'status': status
            })
    except Exception as e:
        print(f"Error fetching questions for admin: {e}")
        message = "خطا در بارگذاری سوالات."
    finally:
        cursor.close()
        conn.close()

    return render_template('admin_manage_questions.html', questions=questions, message=message,
                           can_manage_questions=check_admin_permission(user_id, 'manage_questions'))



@app.route('/admin/manage_users', methods=['GET', 'POST'])
def admin_manage_users():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if not check_admin_permission(user_id, 'block_users'):
        abort(403)

    conn = get_db_connection()
    cursor = conn.cursor()
    message = ""

    if request.method == 'POST':
        action = request.form.get('action')
        target_user_id = request.form.get('user_id', type=int)

        if target_user_id is None:
            message = "شناسه کاربر نامعتبر است."
        elif target_user_id == user_id:
            message = "شما نمی‌توانید حساب کاربری خود را مسدود کنید."
        elif action == 'block':
            try:
                cursor.execute("UPDATE players SET is_blocked = TRUE WHERE id = %s;", (target_user_id,))
                conn.commit()
                message = f"کاربر {target_user_id} با موفقیت مسدود شد."
            except Exception as e:
                conn.rollback()
                message = f"خطا در مسدودسازی کاربر: {e}"
        elif action == 'unblock':
            try:
                cursor.execute("UPDATE players SET is_blocked = FALSE WHERE id = %s;", (target_user_id,))
                conn.commit()
                message = f"کاربر {target_user_id} با موفقیت از حالت مسدود خارج شد."
            except Exception as e:
                conn.rollback()
                message = f"خطا در رفع مسدودسازی کاربر: {e}"
        else:
            message = "عملیات نامعتبر است."

    users = []
    try:
        cursor.execute("SELECT id, username, email, is_blocked FROM players ORDER BY username ASC;")
        users_raw = cursor.fetchall()
        for u_id, username, email, is_blocked_status in users_raw:
            users.append({
                'id': u_id,
                'username': username,
                'email': email,
                'is_blocked': is_blocked_status
            })
    except Exception as e:
        print(f"Error fetching users for admin: {e}")
        message = "خطا در بارگذاری کاربران."
    finally:
        cursor.close()
        conn.close()

    return render_template('admin_manage_users.html', users=users, message=message,
                           can_block_users=check_admin_permission(user_id, 'block_users'),
                           current_admin_id=user_id)



@app.route('/match_history')
def match_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_user_id = session['user_id']
    current_username = session['username']

    conn = get_db_connection()
    cursor = conn.cursor()

    matches = []
    try:

        cursor.execute("""
            SELECT
                s.id,
                s.player1_id,
                p1.username AS player1_username,
                s.player2_id,
                p2.username AS player2_username,
                s.winner_id,
                s.start_time,
                s.end_time,
                s.status
            FROM
                sessions s
            JOIN
                players p1 ON s.player1_id = p1.id
            LEFT JOIN
                players p2 ON s.player2_id = p2.id
            WHERE
                (s.player1_id = %s OR s.player2_id = %s)
                AND s.status = 'finished'
            ORDER BY
                s.end_time DESC;
        """, (current_user_id, current_user_id))

        game_sessions = cursor.fetchall()

        for session_data in game_sessions:
            (session_id, p1_id, p1_username, p2_id, p2_username, winner_id, start_time, end_time, status) = session_data


            opponent_username = "N/A"
            if p1_id == current_user_id and p2_username:
                opponent_username = p2_username
            elif p2_id == current_user_id and p1_username:
                opponent_username = p1_username


            cursor.execute("""
                SELECT player_id, SUM(CASE WHEN is_correct = TRUE THEN 1 ELSE 0 END) AS score
                FROM player_answers
                WHERE session_id = %s
                GROUP BY player_id;
            """, (session_id,))

            scores_raw = cursor.fetchall()
            p1_score = 0
            p2_score = 0
            for p_id, score in scores_raw:
                if p_id == p1_id:
                    p1_score = score
                elif p_id == p2_id:
                    p2_score = score


            outcome = "تساوی"
            if winner_id == current_user_id:
                outcome = "برد"
            elif winner_id is not None and winner_id != current_user_id:
                outcome = "باخت"

            matches.append({
                'session_id': session_id,
                'opponent_username': opponent_username,
                'your_score': p1_score if p1_id == current_user_id else p2_score,
                'opponent_score': p2_score if p1_id == current_user_id else p1_score,
                'outcome': outcome,
                'start_time': start_time.strftime('%Y-%m-%d %H:%M') if start_time else 'N/A',
                'end_time': end_time.strftime('%Y-%m-%d %H:%M') if end_time else 'N/A',
                'status': status
            })

        return render_template('match_history.html',
                               matches=matches,
                               current_username=current_username)

    except Exception as e:
        print(f"Error fetching match history for user {current_user_id}: {e}")
        return "خطا در بارگذاری تاریخچه مسابقات.", 500
    finally:
        cursor.close()
        conn.close()





if __name__ == '__main__':

    create_tables()

    assign_initial_admin('Admin')
    app.run(debug=True)

