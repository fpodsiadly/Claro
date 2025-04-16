import psycopg2
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

def connect_to_db(database_name=None):
    """
    Establishes a connection to PostgreSQL database (Neon PostgreSQL).
    
    Args:
        database_name (str): The name of the database you want to connect to. 
                             If None, uses the default database from connection string.
    
    Returns:
        psycopg2.connection: Database connection object or None in case of error.
    """
    try:
        # Use DATABASE_URL as primary connection method (recommended by Neon)
        database_url = os.getenv("DATABASE_URL")
        
        if database_url:
            # If a specific database name is provided, we'll need to modify the URL
            if database_name:
                # Parse the URL and replace the database name
                parsed_url = urlparse(database_url)
                path_parts = parsed_url.path.split('/')
                path_parts[-1] = database_name
                new_path = '/'.join(path_parts)
                database_url = database_url.replace(parsed_url.path, new_path)
            
            # Connect using the connection string
            connection = psycopg2.connect(database_url)
            return connection
        else:
            # Fallback to individual parameters if URL is not available
            host = os.getenv("PGHOST")
            user = os.getenv("PGUSER")
            password = os.getenv("PGPASSWORD")
            db_name = database_name if database_name else os.getenv("PGDATABASE")
            
            connection = psycopg2.connect(
                host=host,
                database=db_name,
                user=user,
                password=password,
                sslmode='require'
            )
            return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def test_connection():
    """
    Tests the connection to the database and prints relevant information.
    """
    try:
        connection = connect_to_db()
        if connection:
            cursor = connection.cursor()
            # Get PostgreSQL version
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            # Get current database name
            cursor.execute("SELECT current_database();")
            current_db = cursor.fetchone()
            
            print(f"Successfully connected to PostgreSQL!")
            print(f"Version: {version[0]}")
            print(f"Database: {current_db[0]}")
            
            cursor.close()
            connection.close()
            return True
        else:
            print("Failed to connect to the database.")
            return False
    except Exception as e:
        print(f"Error testing connection: {e}")
        return False

if __name__ == "__main__":
    # Test the database connection
    test_connection()