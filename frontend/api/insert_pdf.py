import psycopg2
from db_connection import connect_to_db
import re
import fitz  # PyMuPDF
import os

def extract_text_from_pdf(file_path):
    """
    Extracts text from a PDF file.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        str: The extracted text from the PDF.
    """
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        return None
        
    try:
        doc = fitz.open(file_path)
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

def split_to_articles(text):
    """
    Splits the given text into articles based on the pattern 'Art. X.'

    Args:
        text (str): The full text to split into articles.

    Returns:
        list: A list of tuples where each tuple contains the article number and its content.
    """
    if text is None:
        return []
        
    matches = list(re.finditer(r"Art\. ?(\d+[a-zA-Z]*)\.", text))
    
    if not matches:
        print("No articles found in the text.")
        return []
        
    articles = []
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        number = matches[i].group(0).strip()
        content = text[start:end].strip()
        articles.append((number, content))
    return articles

def insert_article_with_version(law_id, article_number, content, version_start_date, version_end_date=None):
    """
    Inserts an article and its version into the database.

    Args:
        law_id (str): The ID of the law the article belongs to.
        article_number (str): The number of the article.
        content (str): The content of the article.
        version_start_date (str): The start date of the article version (YYYY-MM-DD).
        version_end_date (str, optional): The end date of the article version (YYYY-MM-DD). Defaults to None.
    """
    connection = connect_to_db("claro-db")
    if connection is None:
        print("Failed to connect to the database.")
        return False

    try:
        cursor = connection.cursor()

        # Check if there is an entry in the laws table
        cursor.execute("SELECT 1 FROM laws WHERE law_id = %s", (law_id,))
        if not cursor.fetchone():
            # Insert a new entry if it doesn't exist
            cursor.execute("INSERT INTO laws (law_id, law_name) VALUES (%s, %s)", 
                          (law_id, f"Law {law_id}"))

        # Check if the article exists
        cursor.execute("SELECT id FROM articles WHERE law_id = %s AND article_number = %s", 
                      (law_id, article_number))
        article_row = cursor.fetchone()
        
        if article_row:
            article_id = article_row[0]
        else:
            # Insert a new article
            cursor.execute("INSERT INTO articles (law_id, article_number) VALUES (%s, %s) RETURNING id", 
                          (law_id, article_number))
            article_id = cursor.fetchone()[0]

        # Insert the article version
        cursor.execute("""
            INSERT INTO article_versions (article_id, content, version_start_date, version_end_date)
            VALUES (%s, %s, %s, %s);
        """, (article_id, content, version_start_date, version_end_date))

        connection.commit()
        print(f"Article {article_number} with version inserted successfully.")
        return True
    except Exception as e:
        print(f"Error inserting article: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def process_pdf_and_store_articles_with_versions(file_path, law_id, version_start_date):
    """
    Extracts text from a PDF, splits it into articles, and stores them with versions in the database.

    Args:
        file_path (str): The path to the PDF file.
        law_id (str): The ID of the law the articles belong to.
        version_start_date (str): The start date of the article versions (YYYY-MM-DD).
        
    Returns:
        bool: True if successful, False otherwise.
    """
    # Extract text from the PDF
    text = extract_text_from_pdf(file_path)
    if not text:
        return False

    # Split the text into articles
    articles = split_to_articles(text)
    if not articles:
        return False
        
    print(f"Found {len(articles)} articles.")

    # Insert each article into the database
    success_count = 0
    for number, content in articles:
        print(f"Inserting article {number}...")
        if insert_article_with_version(law_id, number, content, version_start_date):
            success_count += 1

    if success_count == len(articles):
        print(f"All {len(articles)} articles have been successfully saved.")
        return True
    else:
        print(f"Saved {success_count} out of {len(articles)} articles.")
        return success_count > 0