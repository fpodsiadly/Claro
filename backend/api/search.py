import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import openai
import logging
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs
import sys
from pathlib import Path

# Dodanie ścieżki do katalogu backend
sys.path.append(str(Path(__file__).parent.parent))
from db_connection import connect_to_db

# Logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_db_connection():
    """
    Creates and returns a database connection using the updated connection method.
    
    Returns:
        connection: Database connection object or None in case of error.
    """
    try:
        # Użycie nowej metody połączenia z db_connection.py
        conn = connect_to_db()
        
        # Jeśli powyższe nie zadziała, użyj starej metody jako fallback
        if not conn:
            conn = psycopg2.connect(
                host=os.environ.get("PGHOST", os.environ.get("DB_HOST")),
                dbname=os.environ.get("PGDATABASE", os.environ.get("DB_NAME", "neondb")),
                user=os.environ.get("PGUSER", os.environ.get("DB_USER", "neondb_owner")),
                password=os.environ.get("PGPASSWORD", os.environ.get("DB_PASSWORD")),
                port=os.environ.get("DB_PORT", 5432),
                sslmode='require'
            )
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return None

def search_articles(query, conn, limit=5):
    """
    Searches for articles in the database based on the query.
    
    Args:
        query (str): Search query.
        conn: Database connection object.
        limit (int, optional): Maximum number of results. Default is 5.
        
    Returns:
        list: List of found articles.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Using full-text search optimization
            sql = """
                SELECT a.article_number, av.content, l.law_name
                FROM articles a
                JOIN article_versions av ON a.id = av.article_id
                JOIN laws l ON a.law_id = l.law_id
                WHERE to_tsvector('simple', av.content) @@ plainto_tsquery('simple', %s)
                AND av.version_end_date IS NULL
                ORDER BY av.version_start_date DESC
                LIMIT %s
            """
            cur.execute(sql, (query, limit))
            return cur.fetchall()
    except Exception as e:
        logger.error(f"Error searching for articles: {str(e)}")
        return []

def get_openai_response(query, articles):
    """
    Gets a response from the OpenAI API.
    
    Args:
        query (str): User query.
        articles (list): List of articles for context.
        
    Returns:
        str: Response from OpenAI.
    """
    try:
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        
        # Prepare article text
        articles_text = ""
        for article in articles:
            # Shortened content, up to 300 characters
            content_preview = article['content'][:300] + "..." if len(article['content']) > 300 else article['content']
            articles_text += f"\n\nArtykuł {article['article_number']} ({article['law_name']}):\n{content_preview}"
        
        # Execute a request to the OpenAI API
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Changed from gpt-4 to gpt-3.5-turbo
            messages=[
                {"role": "system", "content": "Jesteś prawnikiem specjalizującym się w polskim prawie. Odpowiadasz na pytania użytkowników na podstawie przepisów prawnych."},
                {"role": "user", "content": f"Pytanie: {query}\n\nPowiązane przepisy:{articles_text}"}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        logger.error(f"Error communicating with OpenAI API: {str(e)}")
        return "Przepraszam, wystąpił błąd podczas generowania odpowiedzi. Proszę spróbować ponownie później."

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write('Please use POST method for search queries'.encode())
        
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            body = json.loads(post_data)
            query = body.get("query", "")
            
            if not query:
                self._send_json_response(400, {"error": "Missing 'query' parameter in request"})
                return
            
            logger.info(f"Received query: {query}")
            
            # Database connection
            conn = get_db_connection()
            if not conn:
                self._send_json_response(500, {"error": "Database connection error"})
                return
            
            try:
                # Search for articles
                articles = search_articles(query, conn)
                
                # Generate response from OpenAI
                if articles:
                    answer = get_openai_response(query, articles)
                    
                    # Prepare response with information about found articles
                    article_refs = [f"{a['article_number']} ({a['law_name']})" for a in articles]
                    
                    self._send_json_response(200, {
                        "answer": answer,
                        "sources": article_refs
                    })
                else:
                    self._send_json_response(200, {
                        "answer": "No relevant legal provisions found in the database for this query.",
                        "sources": []
                    })
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            self._send_json_response(500, {"error": f"Unexpected error: {str(e)}"})
    
    def _send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

# Function for Vercel serverless deployment
def handler(request, response):
    # Handle CORS preflight requests
    if request.method == 'OPTIONS':
        response.status = 200
        response.headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type'
        }
        return response

    # Handle actual requests
    if request.method == 'POST':
        try:
            body = request.json()
            query = body.get("query", "")
            
            if not query:
                response.status = 400
                response.body = json.dumps({"error": "Missing 'query' parameter in request"})
                return response
            
            logger.info(f"Received query: {query}")
            
            # Database connection
            conn = get_db_connection()
            if not conn:
                response.status = 500
                response.body = json.dumps({"error": "Database connection error"})
                return response
            
            try:
                # Search for articles
                articles = search_articles(query, conn)
                
                # Generate response from OpenAI
                if articles:
                    answer = get_openai_response(query, articles)
                    
                    # Prepare response with information about found articles
                    article_refs = [f"{a['article_number']} ({a['law_name']})" for a in articles]
                    
                    response.status = 200
                    response.body = json.dumps({
                        "answer": answer,
                        "sources": article_refs
                    })
                else:
                    response.status = 200
                    response.body = json.dumps({
                        "answer": "No relevant legal provisions found in the database for this query.",
                        "sources": []
                    })
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            response.status = 500
            response.body = json.dumps({"error": f"Unexpected error: {str(e)}"})
    else:
        response.status = 200
        response.body = "Please use POST method for search queries"
    
    response.headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    }
    return response

# For local testing
if __name__ == "__main__":
    # Set environment variables for testing
    os.environ["OPENAI_API_KEY"] = "your-api-key"
    
    # Simulate a request and response for Vercel
    class MockRequest:
        def __init__(self, method, json_data):
            self.method = method
            self._json = json_data
        
        def json(self):
            return self._json
    
    class MockResponse:
        def __init__(self):
            self.status = None
            self.headers = {}
            self.body = None
    
    # Simulate a query
    mock_request = MockRequest("POST", {"query": "Can I deduct VAT on car purchase?"})
    mock_response = MockResponse()
    
    # Call the handler
    result = handler(mock_request, mock_response)
    print(f"Status: {result.status}")
    print(f"Headers: {result.headers}")
    print(f"Body: {result.body}")