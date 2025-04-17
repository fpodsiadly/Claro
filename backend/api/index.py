import json
import sys
import os
import logging
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
from search import search_articles, get_openai_response, get_db_connection

def handler(request):
    """
    Główna funkcja obsługująca zapytania do API w Vercel Serverless Functions
    
    Args:
        request (dict): Obiekt żądania zawierający metodę HTTP, ciało żądania itp.
        
    Returns:
        dict: Odpowiedź dla Vercel zawierająca status, nagłówki i ciało odpowiedzi
    """
    logger.info(f"Otrzymano żądanie: {request.get('method', 'UNKNOWN')} {request.get('path', '/')}")
    logger.debug(f"Pełny obiekt żądania: {request}")
    
    # Standardowe nagłówki CORS
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    
    # Obsługa CORS preflight request
    if request.get("method", "").upper() == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": ""
        }
    
    # Proste sprawdzenie, czy API działa
    if request.get("method", "").upper() == "GET":
        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "status": "ok",
                "message": "API działa poprawnie. Użyj metody POST aby wysłać zapytanie."
            })
        }
    
    # Przetwarzanie rzeczywistego zapytania
    if request.get("method", "").upper() == "POST":
        try:
            # Parsowanie ciała żądania
            body_str = request.get("body", "{}")
            logger.debug(f"Otrzymane body: {body_str}")
            
            if isinstance(body_str, str):
                try:
                    body = json.loads(body_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Błąd dekodowania JSON: {e}")
                    return {
                        "statusCode": 400,
                        "headers": headers,
                        "body": json.dumps({
                            "error": f"Nieprawidłowy format JSON: {str(e)}"
                        })
                    }
            else:
                body = body_str
                
            query = body.get("query", "")
            logger.info(f"Otrzymano zapytanie: {query}")
            
            if not query:
                return {
                    "statusCode": 400,
                    "headers": headers,
                    "body": json.dumps({
                        "error": "Brak parametru 'query' w żądaniu"
                    })
                }
            
            # Połączenie z bazą danych
            logger.debug("Próba połączenia z bazą danych...")
            conn = get_db_connection()
            if not conn:
                logger.error("Nie udało się połączyć z bazą danych")
                return {
                    "statusCode": 500,
                    "headers": headers,
                    "body": json.dumps({
                        "error": "Błąd połączenia z bazą danych. Spróbuj ponownie później."
                    })
                }
            
            try:
                # Wyszukiwanie odpowiednich artykułów
                logger.debug("Wyszukiwanie artykułów...")
                articles = search_articles(query, conn)
                
                if articles:
                    logger.info(f"Znaleziono {len(articles)} artykułów")
                    # Generowanie odpowiedzi z pomocą OpenAI
                    logger.debug("Generowanie odpowiedzi OpenAI...")
                    answer = get_openai_response(query, articles)
                    article_refs = [f"{a['article_number']} ({a['law_name']})" for a in articles]
                    
                    logger.info(f"Zwracanie odpowiedzi o długości {len(answer)}")
                    return {
                        "statusCode": 200,
                        "headers": headers,
                        "body": json.dumps({
                            "answer": answer,
                            "sources": article_refs
                        })
                    }
                else:
                    logger.info("Nie znaleziono odpowiednich artykułów prawnych")
                    
                    return {
                        "statusCode": 200,
                        "headers": headers,
                        "body": json.dumps({
                            "answer": "Nie znaleziono odpowiednich przepisów prawnych dla tego zapytania.",
                            "sources": []
                        })
                    }
            finally:
                conn.close()
                logger.debug("Zamknięto połączenie z bazą danych")
                
        except Exception as e:
            logger.error(f"Wystąpił nieoczekiwany błąd: {str(e)}", exc_info=True)
            
            return {
                "statusCode": 500,
                "headers": headers,
                "body": json.dumps({
                    "error": f"Wystąpił nieoczekiwany błąd: {str(e)}"
                })
            }
    
    # Domyślna odpowiedź dla nieprawidłowych metod
    return {
        "statusCode": 405,
        "headers": headers,
        "body": json.dumps({
            "error": "Metoda nie jest obsługiwana"
        })
    }