from http.server import BaseHTTPRequestHandler
import json
import sys
import os
from pathlib import Path

# Dodanie ścieżki backend do sys.path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.append(str(backend_path))
sys.path.append(str(backend_path / "api"))

# Import funkcji handler z modułu search.py
from api.search import search_articles, get_openai_response, get_db_connection

def handler(request, response):
    """
    Funkcja obsługująca zapytania dla Vercel Serverless Functions
    """
    # Określ metodę HTTP
    method = request.get("method", "").upper()
    
    # Obsługa CORS preflight
    if method == "OPTIONS":
        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            },
            "body": ""
        }
    
    # Obsługa GET - zwróć prosty komunikat
    if method == "GET":
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/plain",
                "Access-Control-Allow-Origin": "*"
            },
            "body": "Please use POST method for search queries"
        }
    
    # Obsługa POST - przeprowadź wyszukiwanie
    if method == "POST":
        try:
            # Pobierz dane z ciała żądania
            body = json.loads(request.get("body", "{}"))
            query = body.get("query", "")
            
            if not query:
                return {
                    "statusCode": 400,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({"error": "Missing 'query' parameter in request"})
                }
            
            # Połączenie z bazą danych
            conn = get_db_connection()
            if not conn:
                return {
                    "statusCode": 500,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({"error": "Database connection error"})
                }
            
            try:
                # Wyszukiwanie artykułów
                articles = search_articles(query, conn)
                
                # Generowanie odpowiedzi OpenAI
                if articles:
                    answer = get_openai_response(query, articles)
                    article_refs = [f"{a['article_number']} ({a['law_name']})" for a in articles]
                    
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
                    return {
                        "statusCode": 200,
                        "headers": {
                            "Content-Type": "application/json",
                            "Access-Control-Allow-Origin": "*"
                        },
                        "body": json.dumps({
                            "answer": "No relevant legal provisions found in the database for this query.",
                            "sources": []
                        })
                    }
            finally:
                conn.close()
                
        except Exception as e:
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": f"Unexpected error: {str(e)}"})
            }
    
    # Domyślnie zwróć 405 Method Not Allowed
    return {
        "statusCode": 405,
        "headers": {
            "Content-Type": "text/plain",
            "Access-Control-Allow-Origin": "*"
        },
        "body": "Method not allowed"
    }