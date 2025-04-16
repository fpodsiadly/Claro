import json
import os
import psycopg2
import openai

def lambda_handler(event, context):
    query = json.loads(event["body"]).get("query", "")

    # connect to DB
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"]
    )
    cur = conn.cursor()

    # get articles (basic logic for now)
    cur.execute("SELECT article_number, content FROM articles WHERE content ILIKE %s LIMIT 3", (f"%{query}%",))
    results = cur.fetchall()
    articles_text = "\n\n".join([f"{a[0]}: {a[1][:500]}..." for a in results])

    # ask GPT (basic RAG style)
    openai.api_key = os.environ["OPENAI_API_KEY"]
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Jesteś prawnikiem specjalizującym się w VAT."},
            {"role": "user", "content": f"Pytanie: {query}\n\nPowiazane przepisy:\n{articles_text}"}
        ]
    )
    answer = response.choices[0].message.content

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"answer": answer})
    }