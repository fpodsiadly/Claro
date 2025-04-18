import json
import sys
import os
import logging
import time
import hashlib
from pathlib import Path
from dotenv import load_dotenv

# Załaduj zmienne środowiskowe z pliku .env
load_dotenv()

# Konfiguracja logowania
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("DEBUG", "False").lower() == "true" else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import funkcji z lokalnego modułu search.py
from api.search import search_articles, get_openai_response, get_db_connection

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
    
    logger.info(f"[{request_id}] Otrzymano żądanie: {request.get('method', 'UNKNOWN')} {request.get('path', '/')}")
    logger.debug(f"[{request_id}] Pełny obiekt żądania: {request}")
    
    # Standardowe nagłówki CORS
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Requested-With",
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
    
    # Endpoint diagnostyczny
    if request.get("method", "").upper() == "GET":
        path = request.get("path", "/")
        
        # Endpoint /api/status - rozszerzony diagnostyczny endpoint
        if path.endswith("/status"):
            try:
                # Próba połączenia z bazą danych
                logger.info(f"[{request_id}] Sprawdzanie statusu bazy danych...")
                conn = get_db_connection()
                db_status = "online" if conn else "offline"
                
                if conn:
                    try:
                        # Sprawdzenie liczby artykułów w bazie
                        with conn.cursor() as cur:
                            cur.execute("SELECT COUNT(*) FROM articles")
                            article_count = cur.fetchone()[0]
                            
                            cur.execute("SELECT COUNT(*) FROM laws")
                            law_count = cur.fetchone()[0]
                    except Exception as e:
                        logger.error(f"[{request_id}] Błąd podczas sprawdzania statystyk bazy: {str(e)}")
                        article_count = "error"
                        law_count = "error"
                    finally:
                        conn.close()
                else:
                    article_count = "unknown"
                    law_count = "unknown"
                
                # Sprawdzenie dostępności OpenAI API
                openai_key_status = "configured" if os.environ.get("OPENAI_API_KEY") else "missing"
                
                return {
                    "statusCode": 200,
                    "headers": headers,
                    "body": json.dumps({
                        "status": "ok",
                        "version": "1.1.0",
                        "uptime": "unknown",  # W środowisku serverless nie mamy ciągłego uptime
                        "database": {
                            "status": db_status,
                            "articles": article_count,
                            "laws": law_count
                        },
                        "openai_api": {
                            "status": openai_key_status
                        },
                        "cache": {
                            "enabled": True,
                            "size": len(response_cache),
                            "expiry": f"{CACHE_EXPIRY} seconds"
                        },
                        "request": {
                            "id": request_id,
                            "timestamp": time.time(),
                            "processing_time_ms": int((time.time() - start_time) * 1000)
                        }
                    })
                }
            except Exception as e:
                logger.error(f"[{request_id}] Błąd podczas tworzenia odpowiedzi diagnostycznej: {str(e)}")
                return {
                    "statusCode": 500,
                    "headers": headers,
                    "body": json.dumps({
                        "error": f"Błąd podczas pobierania statusu: {str(e)}"
                    })
                }
        
        # Standardowy endpoint GET /api
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "status": "ok",
                "message": "API działa poprawnie. Użyj metody POST aby wysłać zapytanie.",
                "endpoints": {
                    "/api": "Główny endpoint API (POST z parametrem 'query')",
                    "/api/status": "Endpoint diagnostyczny (GET)"
                },
                "request": {
                    "id": request_id,
                    "timestamp": time.time(),
                    "processing_time_ms": int((time.time() - start_time) * 1000)
                }
            })
        }
    
    # Przetwarzanie rzeczywistego zapytania
    if request.get("method", "").upper() == "POST":
        try:
            # Parsowanie ciała żądania
            body_str = request.get("body", "{}")
            logger.debug(f"[{request_id}] Otrzymane body: {body_str}")
            
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
                
            query = body.get("query", "")
            logger.info(f"[{request_id}] Otrzymano zapytanie: {query}")
            
            if not query:
                return {
                    "statusCode": 400,
                    "headers": headers,
                    "body": json.dumps({
                        "error": "Brak parametru 'query' w żądaniu",
                        "request_id": request_id
                    })
                }
            
            # Sprawdzenie cache
            cache_key = generate_cache_key(query)
            current_time = time.time()
            if cache_key in response_cache:
                cache_entry = response_cache[cache_key]
                # Sprawdzenie czy cache nie wygasł
                if current_time - cache_entry["timestamp"] < CACHE_EXPIRY:
                    logger.info(f"[{request_id}] Znaleziono odpowiedź w cache dla zapytania: {query}")
                    cache_entry["response"]["request_id"] = request_id
                    cache_entry["response"]["from_cache"] = True
                    cache_entry["response"]["cache_age"] = int(current_time - cache_entry["timestamp"])
                    
                    return {
                        "statusCode": 200,
                        "headers": headers,
                        "body": json.dumps(cache_entry["response"])
                    }
                else:
                    # Usunięcie wygasłego cache
                    del response_cache[cache_key]
                    logger.debug(f"[{request_id}] Usunięto wygasły cache dla zapytania: {query}")
            
            # Połączenie z bazą danych
            logger.debug(f"[{request_id}] Próba połączenia z bazą danych...")
            conn = get_db_connection()
            if not conn:
                logger.error(f"[{request_id}] Nie udało się połączyć z bazą danych")
                return {
                    "statusCode": 500,
                    "headers": headers,
                    "body": json.dumps({
                        "error": "Błąd połączenia z bazą danych. Spróbuj ponownie później.",
                        "request_id": request_id
                    })
                }
            
            try:
                # Wyszukiwanie odpowiednich artykułów
                logger.debug(f"[{request_id}] Wyszukiwanie artykułów...")
                search_start_time = time.time()
                articles = search_articles(query, conn)
                search_time = time.time() - search_start_time
                
                if articles:
                    logger.info(f"[{request_id}] Znaleziono {len(articles)} artykułów w {search_time:.2f}s")
                    
                    # Generowanie odpowiedzi z pomocą OpenAI
                    logger.debug(f"[{request_id}] Generowanie odpowiedzi OpenAI...")
                    openai_start_time = time.time()
                    answer = get_openai_response(query, articles)
                    openai_time = time.time() - openai_start_time
                    
                    article_refs = [f"{a['article_number']} ({a['law_name']})" for a in articles]
                    
                    response_data = {
                        "answer": answer,
                        "sources": article_refs,
                        "stats": {
                            "found_articles": len(articles),
                            "search_time": f"{search_time:.2f}s",
                            "openai_time": f"{openai_time:.2f}s",
                            "total_time": f"{(time.time() - start_time):.2f}s"
                        },
                        "request_id": request_id,
                        "from_cache": False
                    }
                    
                    # Zapisanie odpowiedzi w cache
                    response_cache[cache_key] = {
                        "timestamp": time.time(),
                        "response": response_data
                    }
                    
                    logger.info(f"[{request_id}] Zwracanie odpowiedzi o długości {len(answer)} (całkowity czas: {time.time() - start_time:.2f}s)")
                    return {
                        "statusCode": 200,
                        "headers": headers,
                        "body": json.dumps(response_data)
                    }
                else:
                    logger.info(f"[{request_id}] Nie znaleziono odpowiednich artykułów prawnych (czas wyszukiwania: {search_time:.2f}s)")
                    
                    response_data = {
                        "answer": "Nie znaleziono odpowiednich przepisów prawnych dla tego zapytania. Spróbuj przeformułować pytanie lub użyć innych słów kluczowych.",
                        "sources": [],
                        "stats": {
                            "found_articles": 0,
                            "search_time": f"{search_time:.2f}s",
                            "total_time": f"{(time.time() - start_time):.2f}s"
                        },
                        "request_id": request_id,
                        "from_cache": False
                    }
                    
                    # Zapisanie odpowiedzi w cache
                    response_cache[cache_key] = {
                        "timestamp": time.time(),
                        "response": response_data
                    }
                    
                    return {
                        "statusCode": 200,
                        "headers": headers,
                        "body": json.dumps(response_data)
                    }
            finally:
                conn.close()
                logger.debug(f"[{request_id}] Zamknięto połączenie z bazą danych")
                
        except Exception as e:
            logger.error(f"[{request_id}] Wystąpił nieoczekiwany błąd: {str(e)}", exc_info=True)
            
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": f"Wystąpił nieoczekiwany błąd: {str(e)}",
                    "request_id": request_id,
                    "processing_time": f"{(time.time() - start_time):.2f}s"
                })
            }
    
    # Domyślna odpowiedź dla nieprawidłowych metod
    return {
        "statusCode": 405,
        "headers": headers,
        "body": json.dumps({
            "error": "Metoda nie jest obsługiwana",
            "request_id": request_id
        })
    }