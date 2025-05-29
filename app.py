import psycopg2


DATABASE_URL = "postgresql://postgres:Reza4831@localhost:5432/postgres"

def create_database():
    cursor = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("CREATE DATABASE quiz_of_kings;")
        print("Database 'quiz_of_kings' created successfully!")

    except Exception as e:
        print("Error creating database:", e)

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    create_database()
