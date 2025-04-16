import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import openai
import logging

# Logging configuration
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_db_connection():
    """
    Creates and returns a database connection.
    
    Returns:
        connection: Database connection object or None in case of error.
    """
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST"),
            dbname=os.environ.get("DB_NAME", "claro-db"),
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD"),
            port=os.environ.get("DB_PORT", 5432)
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

def lambda_handler(event, context):
    """
    Main function handling requests in AWS Lambda.
    
    Args:
        event: AWS Lambda event object.
        context: AWS Lambda context object.
        
    Returns:
        dict: HTTP response.
    """
    try:
        # Query parsing
        body = json.loads(event.get("body", "{}"))
        query = body.get("query", "")
        
        if not query:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'query' parameter in request"})
            }
        
        logger.info(f"Received query: {query}")
        
        # Database connection
        conn = get_db_connection()
        if not conn:
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Database connection error"})
            }
        
        try:
            # Search for articles
            articles = search_articles(query, conn)
            
            # Generate response from OpenAI
            if articles:
                answer = get_openai_response(query, articles)
                
                # Prepare response with information about found articles
                article_refs = [f"{a['article_number']} ({a['law_name']})" for a in articles]
                
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "answer": answer,
                        "sources": article_refs
                    })
                }
            else:
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "answer": "No relevant legal provisions found in the database for this query.",
                        "sources": []
                    })
                }
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": f"Unexpected error: {str(e)}"})
        }

# For local testing
if __name__ == "__main__":
    # Set environment variables for testing
    os.environ["OPENAI_API_KEY"] = "your-api-key"
    
    # Simulate a query
    test_event = {
        "body": json.dumps({"query": "Can I deduct VAT on car purchase?"})
    }
    
    # Call the handler
    response = lambda_handler(test_event, None)
    print(json.dumps(json.loads(response["body"]), indent=2))