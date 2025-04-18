import json
import sys
import os
import logging
import time
import hashlib
import traceback
from pathlib import Path
from dotenv import load_dotenv

# Załaduj zmienne środowiskowe z pliku .env
load_dotenv()

# Dynamiczne dodawanie katalogu z modułami do ścieżki
current_dir = Path(__file__).parent.absolute()
sys.path.insert(0, str(current_dir))

# Konfiguracja logowania
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG", "False").lower() == "true" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import funkcji z lokalnego modułu search.py
try:
    from search import search_articles, get_openai_response, get_db_connection
except ImportError as e:
    logger.error(f"Błąd importu modułów z search.py: {e}")
    traceback.print_exc()
    # Nie definiujemy tutaj fallbacków, ponieważ są one już w search.py

# Funkcja pomocnicza do diagnostyki
def log_request_details(request):
    """
    Loguje szczegóły żądania dla celów diagnostycznych.
    """
    logger.debug("--- DIAGNOSTYKA ŻĄDANIA ---")
    logger.debug(f"Metoda: {request.get('method')}")
    logger.debug(f"Ścieżka: {request.get('path')}")
    logger.debug(f"Nagłówki: {request.get('headers')}")
    logger.debug(f"Body type: {type(request.get('body'))}")
    
    body = request.get('body')
    if isinstance(body, str):
        logger.debug(f"Body length: {len(body)}")
        if len(body) < 1000:  # Loguj tylko jeśli body nie jest zbyt duże
            logger.debug(f"Body content: {body}")
    logger.debug("--- KONIEC DIAGNOSTYKI ---")

# Prosty cache odpowiedzi
response_cache = {}
# Czas ważności cache w sekundach (domyślnie 1 godzina)
CACHE_EXPIRY = int(os.environ.get("CACHE_EXPIRY", 3600))

def generate_cache_key(query):
    """
    Generuje klucz cache dla zapytania.
    
    Args:
        query (str): Zapytanie użytkownika.
        
    Returns:
        str: Klucz cache.
    """
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

def handler(request):
    """
    Główna funkcja obsługująca zapytania do API w Vercel Serverless Functions
    
    Args:
        request (dict): Obiekt żądania zawierający metodę HTTP, ciało żądania itp.
        
    Returns:
        dict: Odpowiedź dla Vercel zawierająca status, nagłówki i ciało odpowiedzi
    """
    start_time = time.time()
    request_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    
    # Dodatkowe logowanie diagnostyczne dla każdego żądania
    log_request_details(request)
    
    logger.info(f"[{request_id}] Otrzymano żądanie: {request.get('method', 'UNKNOWN')} {request.get('path', '/')}")
    
    # Standardowe nagłówki CORS
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Requested-With, Authorization",
        "X-Request-ID": request_id
    }
    
    # Obsługa CORS preflight request
    if request.get("method", "").upper() == "OPTIONS":
        logger.debug(f"[{request_id}] Obsługa CORS preflight request")
        return {
            "statusCode": 200,
            "headers": headers,
            "body": ""
        }
    
    # Endpoint diagnostyczny lub domyślny GET
    if request.get("method", "").upper() == "GET":
        path = request.get("path", "/")
        
        # Kontrola zdrowia API - podstawowy endpoint, który zawsze powinien działać
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "status": "ok",
                "message": "API działa poprawnie. Użyj metody POST aby wysłać zapytanie.",
                "openai_key_status": "present" if os.environ.get("OPENAI_API_KEY") else "missing",
                "request": {
                    "id": request_id,
                    "timestamp": time.time(),
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            })
        }
    
    # Przetwarzanie zapytania POST
    if request.get("method", "").upper() == "POST":
        logger.info(f"[{request_id}] Przetwarzanie żądania POST")
        
        # Parsowanie ciała żądania
        body_str = request.get("body", "{}")
        
        # Zabezpieczenie przed różnymi formatami body
        if not body_str:
            body_str = "{}"
            
        if isinstance(body_str, str):
            try:
                body = json.loads(body_str)
            except json.JSONDecodeError as e:
                logger.error(f"[{request_id}] Błąd dekodowania JSON: {e}")
                return {
                    "statusCode": 400,
                    "headers": headers,
                    "body": json.dumps({
                        "error": f"Nieprawidłowy format JSON: {str(e)}",
                        "request_id": request_id
                    })
                }
        else:
            body = body_str
            
        # Sprawdzenie czy query jest w body
        query = body.get("query", "")
        
        if not query:
            logger.error(f"[{request_id}] Brak parametru 'query' w żądaniu")
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({
                    "error": "Brak parametru 'query' w żądaniu",
                    "request_id": request_id
                })
            }
        
        # Symulowana odpowiedź (gdy nie możemy połączyć z bazą lub OpenAI)
        # Zawsze zwraca poprawnie sformatowaną odpowiedź
        try:
            # Logowanie klucza OpenAI (zanonimizowanego)
            openai_key = os.environ.get("OPENAI_API_KEY", "")
            logger.info(f"[{request_id}] Klucz OpenAI {'obecny' if openai_key else 'brak'}, długość: {len(openai_key)}")
            
            # Uproszczona odpowiedź tymczasowa - zawsze działa, nawet bez bazy danych
            response_data = {
                "answer": f"To jest tymczasowa odpowiedź dla zapytania: '{query}'. System działa w trybie diagnostycznym.",
                "sources": ["Art. 1 (Ustawa testowa)"],
                "stats": {
                    "found_articles": 1,
                    "search_time": "0.01s",
                    "total_time": f"{(time.time() - start_time):.2f}s"
                },
                "request_id": request_id,
                "from_cache": False
            }
            
            logger.info(f"[{request_id}] Zwracanie tymczasowej odpowiedzi dla: {query}")
            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps(response_data)
            }
            
        except Exception as e:
            logger.error(f"[{request_id}] Wystąpił nieoczekiwany błąd: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": f"Wystąpił nieoczekiwany błąd: {str(e)}",
                    "request_id": request_id
                })
            }
    
    # Domyślna odpowiedź dla nieprawidłowych metod
    logger.warning(f"[{request_id}] Nieobsługiwana metoda: {request.get('method', 'UNKNOWN')}")
    return {
        "statusCode": 405,
        "headers": headers,
        "body": json.dumps({
            "error": "Metoda nie jest obsługiwana",
            "request_id": request_id
        })
    }