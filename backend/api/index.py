import json
import sys
import os
import logging
from pathlib import Path

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO)
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
    
    # Obsługa CORS preflight request
    if request.get("method", "").upper() == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "86400"
            },
            "body": ""
        }
    
    # Proste sprawdzenie, czy API działa
    if request.get("method", "").upper() == "GET":
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
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
            if isinstance(body_str, str):
                body = json.loads(body_str)
            else:
                body = body_str
                
            query = body.get("query", "")
            logger.info(f"Otrzymano zapytanie: {query}")
            
            if not query:
                return {
                    "statusCode": 400,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "error": "Brak parametru 'query' w żądaniu"
                    })
                }
            
            # Połączenie z bazą danych
            conn = get_db_connection()
            if not conn:
                logger.error("Nie udało się połączyć z bazą danych")
                return {
                    "statusCode": 500,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "error": "Błąd połączenia z bazą danych. Spróbuj ponownie później."
                    })
                }
            
            try:
                # Wyszukiwanie odpowiednich artykułów
                articles = search_articles(query, conn)
                
                if articles:
                    # Generowanie odpowiedzi z pomocą OpenAI
                    answer = get_openai_response(query, articles)
                    article_refs = [f"{a['article_number']} ({a['law_name']})" for a in articles]
                    
                    logger.info(f"Znaleziono {len(articles)} odpowiednich artykułów")
                    
                    return {
                        "statusCode": 200,
                        "headers": {
                            "Content-Type": "application/json",
                            "Access-Control-Allow-Origin": "*"
                        },
                        "body": json.dumps({
                            "answer": answer,
                            "sources": article_refs
                        })
                    }
                else:
                    logger.info("Nie znaleziono odpowiednich artykułów prawnych")
                    
                    return {
                        "statusCode": 200,
                        "headers": {
                            "Content-Type": "application/json",
                            "Access-Control-Allow-Origin": "*"
                        },
                        "body": json.dumps({
                            "answer": "Nie znaleziono odpowiednich przepisów prawnych dla tego zapytania.",
                            "sources": []
                        })
                    }
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Wystąpił nieoczekiwany błąd: {str(e)}")
            
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "error": f"Wystąpił nieoczekiwany błąd: {str(e)}"
                })
            }
    
    # Domyślna odpowiedź dla nieprawidłowych metod
    return {
        "statusCode": 405,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "error": "Metoda nie jest obsługiwana"
        })
    }