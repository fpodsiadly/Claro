# Claro - AI-Powered Legal Assistance Application

Claro is an AI-powered application designed to assist users in searching for legal regulations, such as tax law, and their amendments introduced at a later date. Users can input a phrase, and the application searches the database to find relevant laws and their versions.

## Features
- Full-text search in legal regulations.
- Version control for laws with effective dates.
- Automatic processing of PDF files, splitting them into articles, and saving them in the database.
- Integration with OpenAI API for advanced natural language processing and embeddings.
- Storage of PDF files and logs in AWS S3.

## Installation

### Prerequisites
- Python 3.9 or later
- Node.js

### Quick Setup
1. Clone the repository:
   ```bash
   git clone <repo-url>
   cd Claro
   ```

2. Run the setup script to install all dependencies:
   ```bash
   bash setup.sh
   ```

## How the Application Works
1. **Processing PDF Files**:
   - PDF files are processed using the PyMuPDF (`fitz`) library.
   - Text is split into articles based on the pattern `Art. X.`.
   - Articles are saved in the database with effective dates.

2. **Searching for Laws**:
   - Users input a phrase in the application interface.
   - The backend searches the database using a GIN index and PostgreSQL full-text search functions.
   - Results are returned to the user along with information about amendments.

3. **Version Control for Laws**:
   - Each article in the database has assigned effective dates.
   - The application automatically includes amendments in the search results.

4. **Integration with OpenAI API**:
   - The application uses OpenAI's GPT models for advanced natural language understanding and embeddings.
   - Embeddings are used to enhance search accuracy and relevance.

5. **Storage in AWS S3**:
   - PDF files and logs are stored in AWS S3 for easy access and scalability.

## Architecture Diagram
```
[React Frontend]  →  [API Gateway] → [AWS Lambda (backend)] → [RDS PostgreSQL (laws)]
                                                ↓
                                     [OpenAI API (GPT / embeddings)]
                                                ↓
                                     [S3 (PDFs, logs)]
```

## Technologies
- **Backend**: Python, PostgreSQL, AWS Lambda
- **Frontend**: React, Vite
- **AI**: OpenAI API
- **Cloud**: AWS (S3, RDS, API Gateway, Lambda)

## Example Usage
1. Process a PDF file and save articles in the database:
   ```python
   from insert_pdf import process_pdf_and_store_articles_with_versions

   process_pdf_and_store_articles_with_versions("path/to/file.pdf", "vat", "2025-04-07")
   ```

2. Search for legal regulations in the frontend application by entering a phrase in the search field.

## Support
If you encounter any issues, please contact us through the issue tracker in the GitHub repository.
