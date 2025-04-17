# Claro - AI-Powered Legal Assistance Application

Claro is an AI-powered application designed to assist users in searching for legal regulations, such as tax law, and their amendments introduced at a later date. Users can input a phrase, and the application searches the database to find relevant laws and their versions.

## Features

- Full-text search in legal regulations.
- Version control for laws with effective dates.
- Automatic processing of PDF files, splitting them into articles, and saving them in the database.
- Integration with OpenAI API for advanced natural language processing and embeddings.
- Modern cloud-based deployment with Vercel and Neon PostgreSQL.

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

5. **Cloud Infrastructure**:
   - Frontend and serverless backend functions are hosted on Vercel for optimal performance and scalability.
   - Database is managed by Neon PostgreSQL, providing scalable and serverless PostgreSQL capabilities.

## Architecture Diagram

```
[React Frontend] → [Vercel Serverless Functions] → [Neon PostgreSQL]
                               ↓
                    [OpenAI API (GPT / embeddings)]
```

## Technologies

- **Backend**: Python, PostgreSQL, Vercel Serverless Functions
- **Frontend**: React, Vite
- **AI**: OpenAI API
- **Cloud**: Vercel (hosting, serverless functions), Neon PostgreSQL (database)

## Example User Interaction

1. Search for legal regulations in the frontend application by entering a phrase in the search field.

**Question:** "Can I deduct VAT on the purchase of a car?"

**Answer:**  
Based on the provisions in Articles 86 and 90 of the VAT Act:

- Article 86 states that a taxpayer has the right to deduct VAT if the purchased goods or services are used for taxable activities.
- Article 90 specifies limitations on VAT deductions, particularly when the purchased car is used for both business and private purposes. In such cases, the VAT deduction may be proportional to the extent the vehicle is used for business purposes.

It is recommended to consult a tax advisor to determine whether full or partial VAT deduction is possible in your specific case.
