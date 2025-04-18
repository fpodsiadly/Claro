### vat_scraper.py – retrieving the consolidated VAT text from ISAP and updating the database

import requests
import fitz  # PyMuPDF
import psycopg2
import re
from bs4 import BeautifulSoup
from datetime import date
import time
import os
import logging
from scripts.db_connection import connect_to_db

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
LAW_ID = "vat"
LAW_TITLE = "Ustawa o podatku od towarów i usług"
ISAP_ID = "WDU20040540535"

def get_latest_pdf_url(doc_id: str) -> str:
    """
    Gets the URL to the latest PDF file from ISAP based on the "Unified Text" label.

    Args:
        doc_id (str): Document ID in ISAP.

    Returns:
        str: Full URL to the PDF file.

    Raises:
        Exception: If the PDF link is not found.
    """
    url = f"https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id={doc_id}"
    
    # Headers simulating a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Referer': 'https://isap.sejm.gov.pl/',
        'Upgrade-Insecure-Requests': '1'
    }
    
    # Get page content
    logger.info("Downloading ISAP page...")
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()  # Throw exception for HTTP errors
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download ISAP page: {e}")
        raise Exception(f"Failed to download ISAP page: {e}")
    
    logger.info("Page downloaded successfully.")
    
    # Check if the response contains anti-bot verification
    if "human visitor" in response.text or "spam submission" in response.text:
        logger.error("Page returned anti-bot protection.")
        raise Exception("Page returned anti-bot protection. Try using Selenium.")
    
    # Parse HTML
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Method 1: Try to find the link next to the "Unified Text:" label
    try:
        unified_text_label = soup.find("div", class_="col-sm-4", string="Tekst ujednolicony:")
        if unified_text_label:
            pdf_link_tag = unified_text_label.find_next_sibling("div", class_="col-sm-8").find("a", href=True)
            if pdf_link_tag:
                relative_url = pdf_link_tag["href"]
                full_url = f"https://isap.sejm.gov.pl{relative_url}"
                logger.info(f"Found PDF link (method 1): {full_url}")
                return full_url
    except Exception as e:
        logger.warning(f"Method 1 failed: {e}")
    
    # Method 2: Directly search for all links to PDF
    logger.info("Searching for PDF links (method 2)...")
    all_links = soup.find_all('a', href=True)
    doc_id_clean = doc_id.replace("wdu", "D").upper()
    
    for link in all_links:
        href = link['href']
        # Check if it's a PDF link related to doc_id
        if href.endswith('.pdf') and doc_id_clean in href:
            full_url = href if href.startswith('http') else f"https://isap.sejm.gov.pl{href}"
            logger.info(f"Found PDF link (method 2): {full_url}")
            return full_url
    
    logger.error("No link to the unified text PDF file found")
    raise Exception("No link to the unified text PDF file found")

def download_pdf(pdf_url, output_file="vat_tekst_ujednolicony.pdf", max_retries=3):
    """
    Downloads a PDF file from the provided URL and saves it locally.
    Checks if the file already exists before downloading.

    Args:
        pdf_url (str): URL to the PDF file.
        output_file (str, optional): Output filename. Default "vat_tekst_ujednolicony.pdf".
        max_retries (int, optional): Maximum number of download attempts. Default 3.

    Returns:
        str: Path to the downloaded file.

    Raises:
        Exception: If the PDF file couldn't be downloaded after all attempts.
    """
    # Check if the file already exists
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        if file_size > 0:
            logger.info(f"File {output_file} already exists on disk (size: {file_size} bytes). Skipping download.")
            return output_file

    # Headers simulating a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/pdf',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://isap.sejm.gov.pl/'
    }
    
    logger.info(f"Downloading PDF: {pdf_url}")
    
    attempts = 0
    while attempts < max_retries:
        try:
            attempts += 1
            logger.info(f"Attempt {attempts} of {max_retries}...")
            
            # Increased timeout for slow connections
            response = requests.get(pdf_url, headers=headers, timeout=30)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            # Check if the response contains a PDF
            content_type = response.headers.get('Content-Type', '')
            if 'application/pdf' not in content_type and len(response.content) < 5000:
                logger.warning(f"Warning: Returned content may not be a PDF file (Content-Type: {content_type})")
            
            with open(output_file, "wb") as f:
                f.write(response.content)
            
            logger.info(f"PDF file downloaded: {output_file}")
            return output_file
            
        except (requests.exceptions.RequestException, IOError) as e:
            logger.error(f"Error during attempt {attempts}: {e}")
            if attempts < max_retries:
                wait_time = 3 * attempts  # Increasing wait time with each attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"Failed to download PDF file after {max_retries} attempts")
                raise Exception(f"Failed to download PDF file after {max_retries} attempts: {e}")
    
    raise Exception("Failed to download PDF file")

def extract_articles(pdf_path):
    """
    Extracts articles from the PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file.
        
    Returns:
        list: List of tuples (article_number, content).
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = "\n".join(page.get_text() for page in doc)
        doc.close()

        matches = list(re.finditer(r"Art\. ?(\d+[a-zA-Z]*)\.", full_text))
        
        if not matches:
            logger.warning("No articles found in the text.")
            return []
            
        articles = []
        for i in range(len(matches)):
            start = matches[i].start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            number = matches[i].group(0).strip()
            content = full_text[start:end].strip()
            articles.append((number, content))
        
        logger.info(f"Found {len(articles)} articles in the PDF file.")
        return articles
    except Exception as e:
        logger.error(f"Error extracting articles from PDF: {e}")
        raise Exception(f"Error extracting articles from PDF: {e}")

def save_to_db(articles, pdf_url):
    """
    Saves articles to the database.
    
    Args:
        articles (list): List of tuples (article_number, content).
        pdf_url (str): Source URL of the PDF file.
        
    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    # Using a new database connection
    conn = connect_to_db()
    if not conn:
        logger.error("Cannot connect to database")
        return False

    try:
        cur = conn.cursor()

        # Add or update the law
        cur.execute("""
            INSERT INTO laws (law_id, law_name)
            VALUES (%s, %s)
            ON CONFLICT (law_id) DO UPDATE SET law_name = EXCLUDED.law_name
        """, (LAW_ID, LAW_TITLE))

        success_count = 0
        for article_number, content in articles:
            try:
                # Check if the article exists
                cur.execute("SELECT id FROM articles WHERE law_id = %s AND article_number = %s", (LAW_ID, article_number))
                article = cur.fetchone()

                if not article:
                    # Add new article
                    cur.execute("INSERT INTO articles (law_id, article_number) VALUES (%s, %s) RETURNING id", 
                                (LAW_ID, article_number))
                    article_id = cur.fetchone()[0]
                    logger.info(f"Added new article: {article_number}")
                else:
                    article_id = article[0]
                    logger.info(f"Found existing article: {article_number} (id: {article_id})")

                # Check if there is a current version of the article
                cur.execute("""
                    SELECT id, content FROM article_versions
                    WHERE article_id = %s AND version_end_date IS NULL
                    ORDER BY version_start_date DESC LIMIT 1
                """, (article_id,))
                version = cur.fetchone()

                # Add new version if the content has changed or there is no version
                if not version or version[1].strip() != content.strip():
                    # Mark previous version as outdated
                    if version:
                        cur.execute("UPDATE article_versions SET version_end_date = %s WHERE id = %s", 
                                    (date.today(), version[0]))
                        logger.info(f"Updated end date for the previous version of article {article_number}")
                    
                    # Add new version
                    cur.execute("""
                        INSERT INTO article_versions (article_id, content, version_start_date)
                        VALUES (%s, %s, %s)
                    """, (article_id, content, date.today()))
                    logger.info(f"Added new version of article {article_number}")
                else:
                    logger.info(f"Article {article_number} content hasn't changed, skipping new version")
                
                success_count += 1
            except Exception as e:
                logger.error(f"Error processing article {article_number}: {e}")
                # Continue despite error with one article

        conn.commit()
        logger.info(f"Saved {success_count} of {len(articles)} articles in the database.")
        return success_count > 0
    except Exception as e:
        logger.error(f"Error saving to database: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def initialize_database():
    """
    Checks if tables exist in the database and creates them if they don't.
    
    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    logger.info("Database initialization...")
    
    # Connect to the database
    conn = connect_to_db()
    if not conn:
        logger.error("Cannot connect to database")
        return False
    
    try:
        cur = conn.cursor()
        
        # Check if the laws table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'laws'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            logger.info("Creating database table structure...")
            
            # Read the contents of the create_tables.sql file
            script_dir = os.path.dirname(os.path.abspath(__file__))
            sql_file_path = os.path.join(script_dir, "create_tables.sql")
            
            if not os.path.exists(sql_file_path):
                logger.error(f"SQL file not found: {sql_file_path}")
                return False
                
            with open(sql_file_path, "r") as f:
                sql_script = f.read()
            
            # Execute the SQL script
            cur.execute(sql_script)
            conn.commit()
            logger.info("Table structure has been created.")
        else:
            logger.info("Table structure already exists.")
        
        return True
    except Exception as e:
        logger.error(f"Error initializing table structure: {e}")
        conn.rollback()
        return False
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

def main():
    """
    Main program function.
    """
    try:
        logger.info("Starting VAT law database update")
        
        # Database initialization
        if not initialize_database():
            logger.error("Database initialization failed. Aborting.")
            return
        
        # Get PDF link
        logger.info("Looking for the latest PDF...")
        pdf_url = get_latest_pdf_url(ISAP_ID)
        logger.info(f"Found PDF link: {pdf_url}")
        
        # Download PDF
        path = download_pdf(pdf_url)
        
        # Parse articles
        logger.info("Parsing articles...")
        articles = extract_articles(path)
        
        if not articles:
            logger.error("No articles found to save. Aborting.")
            return
            
        logger.info(f"Found {len(articles)} articles.")
        
        # Save articles to database
        logger.info("Saving to database...")
        if save_to_db(articles, pdf_url):
            logger.info("Done ✅")
        else:
            logger.error("Problems occurred while saving to database ❌")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

# === EXECUTION ===
if __name__ == "__main__":
    main()
