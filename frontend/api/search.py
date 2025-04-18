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

from scripts.db_connection import connect_to_db

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
            # Zaawansowane wyszukiwanie pełnotekstowe z rankingiem trafności
            sql = """
                SELECT 
                    a.article_number, 
                    av.content, 
                    l.law_name,
                    ts_rank_cd(to_tsvector('polish', av.content), plainto_tsquery('polish', %s)) AS rank
                FROM 
                    articles a
                JOIN 
                    article_versions av ON a.id = av.article_id
                JOIN 
                    laws l ON a.law_id = l.law_id
                WHERE 
                    to_tsvector('polish', av.content) @@ plainto_tsquery('polish', %s)
                    AND av.version_end_date IS NULL
                ORDER BY 
                    rank DESC,
                    av.version_start_date DESC
                LIMIT %s
            """
            
            # Fallback na prostsze wyszukiwanie, jeśli nie znajdzie wyników
            # lub jeśli język 'polish' nie jest dostępny w PostgreSQL
            try:
                cur.execute(sql, (query, query, limit))
                results = cur.fetchall()
                
                if not results:
                    logger.info("No results using 'polish' dictionary, falling back to 'simple'")
                    sql_fallback = """
                        SELECT 
                            a.article_number, 
                            av.content, 
                            l.law_name,
                            ts_rank_cd(to_tsvector('simple', av.content), plainto_tsquery('simple', %s)) AS rank
                        FROM 
                            articles a
                        JOIN 
                            article_versions av ON a.id = av.article_id
                        JOIN 
                            laws l ON a.law_id = l.law_id
                        WHERE 
                            to_tsvector('simple', av.content) @@ plainto_tsquery('simple', %s)
                            OR av.content ILIKE %s
                            AND av.version_end_date IS NULL
                        ORDER BY 
                            rank DESC,
                            av.version_start_date DESC
                        LIMIT %s
                    """
                    cur.execute(sql_fallback, (query, query, f"%{query}%", limit))
                    results = cur.fetchall()
                
                return results
            
            except psycopg2.Error as e:
                logger.error(f"Search error with 'polish' dictionary: {str(e)}")
                # Próba z prostszym słownikiem
                sql_simple = """
                    SELECT 
                        a.article_number, 
                        av.content, 
                        l.law_name,
                        ts_rank_cd(to_tsvector('simple', av.content), plainto_tsquery('simple', %s)) AS rank
                    FROM 
                        articles a
                    JOIN 
                        article_versions av ON a.id = av.article_id
                    JOIN 
                        laws l ON a.law_id = l.law_id
                    WHERE 
                        to_tsvector('simple', av.content) @@ plainto_tsquery('simple', %s)
                        OR av.content ILIKE %s
                        AND av.version_end_date IS NULL
                    ORDER BY 
                        rank DESC,
                        av.version_start_date DESC
                    LIMIT %s
                """
                cur.execute(sql_simple, (query, query, f"%{query}%", limit))
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Error searching for articles: {str(e)}", exc_info=True)
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
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key or api_key == "sk-twójkluczopenai" or api_key == "your-openai-api-key-here":
            logger.error("Brak prawidłowego klucza API OpenAI. Proszę ustawić OPENAI_API_KEY w pliku .env")
            return "Błąd konfiguracji: nie podano prawidłowego klucza API OpenAI. Proszę skontaktować się z administratorem."
        
        client = openai.OpenAI(api_key=api_key)
        logger.info(f"Przygotowuję zapytanie do OpenAI z {len(articles)} artykułami")
        
        # Przygotowanie tekstu artykułów w lepszym formacie
        articles_text = ""
        for i, article in enumerate(articles):
            # Określenie priorytetu artykułu na podstawie rankingu (jeśli istnieje)
            priority = f"Priorytet: {i+1}" if i < 3 else "Niższy priorytet"
            
            # Pełna zawartość artykułu dla wyższych priorytetów, skrócona dla niższych
            if i < 3 and 'rank' in article and article['rank'] > 0.5:
                content = article['content']
            else:
                # Inteligentne skracanie treści, zachowując kluczowe fragmenty
                content = article['content'][:500] + "..." if len(article['content']) > 500 else article['content']
            
            articles_text += f"\n\nARTYKUŁ {i+1}: {article['article_number']} ({article['law_name']}) - {priority}\n{content}"
        
        # Instrukcje systemowe dla modelu
        system_instruction = """
        Jesteś ekspertem prawnym specjalizującym się w polskim prawie, szczególnie podatkowym. Twoje zadanie:
        
        1. Dokładnie przeanalizuj dostarczone przepisy prawne w kontekście zapytania użytkownika.
        2. Udziel jasnej, zwięzłej i dokładnej odpowiedzi opartej WYŁĄCZNIE na dostarczonych przepisach.
        3. Jeśli przepisy nie są jednoznaczne, wyjaśnij różne możliwe interpretacje.
        4. Odpowiadaj w języku polskim w sposób przystępny dla osoby bez wykształcenia prawniczego.
        5. Używaj konkretnych odwołań do numerów artykułów, gdy je cytujesz.
        6. Nie wymyślaj przepisów ani interpretacji, których nie ma w dostarczonych materiałach.
        7. Jeśli dostarczone przepisy nie są wystarczające, wyraźnie to zaznacz.
        
        Pamiętaj, że Twoja odpowiedź może być wykorzystana do celów informacyjnych, ale nie zastępuje profesjonalnej porady prawnej.
        """
        
        # Instrukcja dla użytkownika
        user_instruction = f"""
        Pytanie użytkownika: {query}
        
        Na podstawie poniższych przepisów prawnych udziel odpowiedzi:
        {articles_text}
        
        Pamiętaj, żeby:
        - Cytować konkretne artykuły
        - Odnosić się bezpośrednio do pytania użytkownika
        - Wskazać jasne wnioski na podstawie przepisów
        """
        
        # Wykonanie zapytania do OpenAI API
        logger.info("Wysyłam zapytanie do OpenAI API...")
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Można zmienić na gpt-4 dla lepszych wyników
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_instruction}
            ],
            temperature=0.2,  # Niższa temperatura dla bardziej precyzyjnych, mniej kreatywnych odpowiedzi
            max_tokens=1500
        )
        
        answer = completion.choices[0].message.content
        logger.info(f"Otrzymano odpowiedź z OpenAI API o długości {len(answer)} znaków")
        return answer
    except Exception as e:
        logger.error(f"Error communicating with OpenAI API: {str(e)}", exc_info=True)
        return f"Przepraszam, wystąpił błąd podczas generowania odpowiedzi: {str(e)}. Proszę spróbować ponownie później."

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