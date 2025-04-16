import psycopg2
from psycopg2 import sql

def connect_to_db():
    try:
        connection = psycopg2.connect(
            dbname="your_database_name",
            user="postgres",
            password="your_password",
            host="localhost",
            port="5432"
        )
        print("Connection to PostgreSQL database successful")
        return connection
    except Exception as e:
        print(f"Error connecting to PostgreSQL database: {e}")
        return None

if __name__ == "__main__":
    conn = connect_to_db()
    if conn:
        conn.close()