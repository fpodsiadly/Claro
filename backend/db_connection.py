import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

def connect_to_db(database_name="postgres"):
    """
    Establishes a connection to PostgreSQL database on AWS RDS.
    
    Args:
        database_name (str): The name of the database you want to connect to. Default is "postgres".
    
    Returns:
        psycopg2.connection: Database connection object or None in case of error.
    """
    try:
        # Database connection parameters from environment variables or default values
        host = os.getenv("DB_HOST", "claro-db.cfs64kowk7ct.eu-north-1.rds.amazonaws.com")
        user = os.getenv("DB_USER", "postgres")
        password = os.getenv("DB_PASSWORD", "Claro2025!")
        port = int(os.getenv("DB_PORT", "5432"))
        
        connection = psycopg2.connect(
            host=host,
            database=database_name,
            user=user,
            password=password,
            port=port,
            connect_timeout=10
        )
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def create_database():
    """
    Creates the 'claro-db' database if it doesn't exist.
    """
    try:
        # Connect to the default postgres database
        connection = connect_to_db()
        connection.autocommit = True  # Required for CREATE DATABASE
        cursor = connection.cursor()
        
        # Check if the database already exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'claro-db'")
        exists = cursor.fetchone()
        
        if not exists:
            print("Creating 'claro-db' database...")
            cursor.execute("CREATE DATABASE \"claro-db\"")
            print("Database 'claro-db' has been created successfully.")
        else:
            print("Database 'claro-db' already exists.")
            
        cursor.close()
        connection.close()
        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

if __name__ == "__main__":
    # Create database if it doesn't exist
    if create_database():
        # Try to connect to the new database
        conn = connect_to_db("claro-db")
        if conn:
            print("Connection to 'claro-db' database successful.")
            conn.close()
        else:
            print("Failed to connect to 'claro-db' database.")