import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from openai import OpenAI

load_dotenv()

es = Elasticsearch(
    os.getenv("ELASTICSEARCH_URL"),
    api_key=os.getenv("ELASTICSEARCH_API_KEY"),
)
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INDEX_NAME = "restaurant-reviews"


def query_reviews(question: str, restaurant_name: str, top_k: int = 20) -> list[dict]:
    result = es.search(
        index=INDEX_NAME,
        query={
            "bool": {
                "must": {"match": {"review_text_semantic": question}},
                "filter": {"term": {"restaurant_name": restaurant_name}},
            }
        },
        size=top_k,
    )
    reviews = []
    for hit in result["hits"]["hits"]:
        src = hit["_source"]
        reviews.append({
            "text": src.get("review_text", ""),
            "stars": src.get("stars"),
            "author": src.get("author", "Anonymous"),
            "date": src.get("published_date", ""),
        })
    return reviews


def summarize(question: str, restaurant_name: str, reviews: list[dict]) -> str:
    if not reviews:
        return f"No reviews found for {restaurant_name}."

    reviews_block = "\n\n".join(
        f"[{r['stars']}★] {r['text']} — {r['author']}, {r['date'][:10] if r['date'] else 'N/A'}"
        for r in reviews
    )

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a restaurant reputation analyst. Based on real Google Maps reviews, "
                    "provide a clear, structured analysis. Include:\n"
                    "1. Overall sentiment (positive/negative/mixed) with an approximate score\n"
                    "2. Top 3 things people love\n"
                    "3. Top 3 complaints\n"
                    "4. 2-3 notable direct quotes from reviewers\n"
                    "5. A one-paragraph summary a restaurant owner would want to read\n\n"
                    "Be specific and cite the reviews. Keep it concise."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Restaurant: {restaurant_name}\n"
                    f"Question: {question}\n"
                    f"Number of reviews analyzed: {len(reviews)}\n\n"
                    f"Reviews:\n{reviews_block}"
                ),
            },
        ],
        temperature=0.3,
    )
    return response.choices[0].message.content


def query_and_summarize(question: str, restaurant_name: str) -> str:
    reviews = query_reviews(question, restaurant_name)
    print(f"  Found {len(reviews)} matching reviews")
    return summarize(question, restaurant_name, reviews)


if __name__ == "__main__":
    restaurant = "Uchi Austin"
    question = "What are people saying about Uchi this month?"

    print(f"Querying reviews for {restaurant}...")
    reviews = query_reviews(question, restaurant)
    print(f"  Found {len(reviews)} reviews")
    for r in reviews:
        print(f"    [{r['stars']}★] {r['text'][:80]}...")

    print(f"\nGenerating summary...")
    summary = query_and_summarize(question, restaurant)
    print(f"\n{'='*60}")
    print(summary)
