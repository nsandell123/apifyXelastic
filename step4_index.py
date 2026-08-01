import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers

load_dotenv()

es = Elasticsearch(
    os.getenv("ELASTICSEARCH_URL"),
    api_key=os.getenv("ELASTICSEARCH_API_KEY"),
)

INDEX_NAME = "restaurant-reviews"

MAPPING = {
    "mappings": {
        "properties": {
            "restaurant_name": {"type": "keyword"},
            "review_text": {"type": "text", "copy_to": "review_text_semantic"},
            "review_text_semantic": {"type": "semantic_text"},
            "stars": {"type": "integer"},
            "author": {"type": "keyword"},
            "published_date": {"type": "date"},
            "review_url": {"type": "keyword"},
            "scraped_at": {"type": "date"},
        }
    }
}


def create_index():
    if es.indices.exists(index=INDEX_NAME):
        print(f"  Index '{INDEX_NAME}' already exists, skipping creation.")
        return
    es.indices.create(index=INDEX_NAME, body=MAPPING)
    print(f"  Index '{INDEX_NAME}' created.")


def index_reviews(reviews: list[dict], restaurant_name: str) -> int:
    now = datetime.now(timezone.utc).isoformat()

    def generate_actions():
        for r in reviews:
            text = r.get("text") or r.get("textTranslated") or ""
            if not text.strip():
                continue
            yield {
                "_index": INDEX_NAME,
                "_id": r.get("reviewId", ""),
                "_source": {
                    "restaurant_name": restaurant_name,
                    "review_text": text,
                    "stars": r.get("stars"),
                    "author": r.get("name", "Anonymous"),
                    "published_date": r.get("publishedAtDate"),
                    "review_url": r.get("reviewUrl", ""),
                    "scraped_at": now,
                },
            }

    success, errors = helpers.bulk(es, generate_actions(), raise_on_error=False)
    print(f"  Indexed {success} reviews, {len(errors) if isinstance(errors, list) else errors} errors")
    return success


if __name__ == "__main__":
    print("Testing Elasticsearch connection...")
    info = es.info()
    print(f"  Connected to: {info['cluster_name']}")

    print("\nCreating index...")
    create_index()

    print("\nIndexing sample reviews...")
    sample_reviews = [
        {
            "reviewId": "test-1",
            "text": "Phenomenal food. Really nice atmosphere. But at a high price.",
            "stars": 5,
            "name": "Safari Travelers",
            "publishedAtDate": "2026-07-30T15:36:05.842Z",
            "reviewUrl": "https://example.com/review1",
        },
        {
            "reviewId": "test-2",
            "text": "Maybe I'm spoiled but I didn't want to give it a 3 star. The omakase was disappointing.",
            "stars": 4,
            "name": "Michael Martinez",
            "publishedAtDate": "2026-07-29T23:16:55.950Z",
            "reviewUrl": "https://example.com/review2",
        },
        {
            "reviewId": "test-3",
            "text": "Amazing omakase! Very fresh and delicious",
            "stars": 5,
            "name": "Izi Honolulu",
            "publishedAtDate": "2026-07-28T12:00:00.000Z",
            "reviewUrl": "https://example.com/review3",
        },
    ]
    index_reviews(sample_reviews, "Uchi Austin")

    print("\nVerifying documents...")
    es.indices.refresh(index=INDEX_NAME)
    count = es.count(index=INDEX_NAME)
    print(f"  Total documents in index: {count['count']}")

    print("\nSample document:")
    result = es.search(index=INDEX_NAME, query={"match_all": {}}, size=1)
    if result["hits"]["hits"]:
        doc = result["hits"]["hits"][0]["_source"]
        for k, v in doc.items():
            if k != "review_text_semantic":
                print(f"    {k}: {v}")
        print(f"    review_text_semantic: {'(populated)' if 'review_text_semantic' in doc else '(missing)'}")
