import psycopg2

DATABASE_URL = "postgresql://postgres:Reza4831@localhost:5432/postgres"

def create_database():
    cursor = None
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = 'quiz_of_kings' AND pid <> pg_backend_pid();
        """)
        print("All other connections to the database have been terminated.")

        cursor.execute("DROP DATABASE IF EXISTS quiz_of_kings;")
        print("Previous database (if any) dropped successfully!")

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
        conn = psycopg2.connect("postgresql://postgres:Reza4831@localhost:5432/quiz_of_kings")
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

if __name__ == '__main__':
    create_database()
    create_tables()
