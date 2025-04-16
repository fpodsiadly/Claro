import psycopg2
from db_connection import connect_to_db
import re
import fitz  # PyMuPDF

def insert_pdf_content(content):
    """
    Inserts the content of a PDF into the database.

    Args:
        content (str): The text content extracted from the PDF.
    """
    connection = connect_to_db()
    if connection is None:
        print("Failed to connect to the database.")
        return

    try:
        cursor = connection.cursor()
        # Ensure the table exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pdf_content (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL
            );
        """)

        # Insert the content into the table
        cursor.execute("""
            INSERT INTO pdf_content (content)
            VALUES (%s);
        """, (content,))

        connection.commit()
        print("PDF content inserted successfully.")
    except Exception as e:
        print(f"Error inserting PDF content: {e}")
    finally:
        cursor.close()
        connection.close()

def extract_text_from_pdf(file_path):
    """
    Extracts text from a PDF file.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        str: The extracted text from the PDF.
    """
    doc = fitz.open(file_path)
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text

def split_to_articles(text):
    """
    Splits the given text into articles based on the pattern 'Art. X.'

    Args:
        text (str): The full text to split into articles.

    Returns:
        list: A list of tuples where each tuple contains the article number and its content.
    """
    matches = list(re.finditer(r"Art\. ?(\d+[a-zA-Z]*)\.", text))
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
    connection = connect_to_db()
    if connection is None:
        print("Failed to connect to the database.")
        return

    try:
        cursor = connection.cursor()

        # Insert the article with version dates
        cursor.execute("""
            INSERT INTO article_versions (law_id, article_number, content, version_start_date, version_end_date)
            VALUES (%s, %s, %s, %s, %s);
        """, (law_id, article_number, content, version_start_date, version_end_date))

        connection.commit()
        print(f"Article {article_number} with version inserted successfully.")
    except Exception as e:
        print(f"Error inserting article: {e}")
    finally:
        cursor.close()
        connection.close()

def process_pdf_and_store_articles(file_path):
    """
    Extracts text from a PDF, splits it into articles, and stores them in the database.

    Args:
        file_path (str): The path to the PDF file.
    """
    # Extract text from the PDF
    text = extract_text_from_pdf(file_path)

    # Split the text into articles
    articles = split_to_articles(text)

    # Insert each article into the database
    for number, content in articles:
        print(f"Inserting article {number}...")
        insert_pdf_content(content)

    print("All articles have been processed and stored.")

def process_pdf_and_store_articles_with_versions(file_path, law_id, version_start_date):
    """
    Extracts text from a PDF, splits it into articles, and stores them with versions in the database.

    Args:
        file_path (str): The path to the PDF file.
        law_id (str): The ID of the law the articles belong to.
        version_start_date (str): The start date of the article versions (YYYY-MM-DD).
    """
    # Extract text from the PDF
    text = extract_text_from_pdf(file_path)

    # Split the text into articles
    articles = split_to_articles(text)

    # Insert each article into the database
    for number, content in articles:
        print(f"Inserting article {number}...")
        insert_article_with_version(law_id, number, content, version_start_date)

    print("All articles have been processed and stored.")