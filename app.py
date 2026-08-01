import os
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from apify_client import ApifyClient
from elasticsearch import Elasticsearch, helpers
from datetime import datetime, timezone
import requests

load_dotenv()

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
apify = ApifyClient(os.getenv("APIFY_API_TOKEN"))
es = Elasticsearch(os.getenv("ELASTICSEARCH_URL"), api_key=os.getenv("ELASTICSEARCH_API_KEY"))
GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
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

# --- Pipeline functions ---

def extract_restaurant(user_message: str) -> str:
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract the restaurant name from the user's message. "
                    "Return ONLY the restaurant name followed by the city and state abbreviation. "
                    "If no city is mentioned, assume Austin TX. "
                    "Example output: Uchi Austin TX"
                ),
            },
            {"role": "user", "content": user_message},
        ],
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def get_place_url(restaurant_name: str) -> tuple[str, str]:
    resp = requests.post(
        "https://places.googleapis.com/v1/places:searchText",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_API_KEY,
            "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.googleMapsUri",
        },
        json={"textQuery": restaurant_name},
    )
    resp.raise_for_status()
    place = resp.json()["places"][0]
    display_name = place["displayName"]["text"]
    return place["googleMapsUri"], display_name


def scrape_reviews(place_url: str, max_reviews: int = 50) -> list[dict]:
    run = apify.actor("compass/google-maps-reviews-scraper").call(run_input={
        "startUrls": [{"url": place_url}],
        "maxReviews": max_reviews,
        "reviewsSort": "newest",
        "language": "en",
        "personalData": True,
    })
    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
    return list(apify.dataset(dataset_id).iterate_items())


def ensure_index():
    if not es.indices.exists(index=INDEX_NAME):
        es.indices.create(index=INDEX_NAME, body=MAPPING)


def index_reviews(reviews: list[dict], restaurant_name: str) -> int:
    ensure_index()
    now = datetime.now(timezone.utc).isoformat()

    def actions():
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

    success, _ = helpers.bulk(es, actions(), raise_on_error=False)
    return success


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
    return [
        {
            "text": hit["_source"].get("review_text", ""),
            "stars": hit["_source"].get("stars"),
            "author": hit["_source"].get("author", "Anonymous"),
            "date": hit["_source"].get("published_date", ""),
        }
        for hit in result["hits"]["hits"]
    ]


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


# --- Streamlit UI ---

st.set_page_config(page_title="Restaurant Reputation Agent", page_icon="🍽️", layout="wide")
st.title("🍽️ Restaurant Reputation Agent")
st.caption("Ask about any Austin restaurant — powered by Apify, Elasticsearch & OpenAI")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "restaurant_name" not in st.session_state:
    st.session_state.restaurant_name = None
if "reviews_scraped" not in st.session_state:
    st.session_state.reviews_scraped = False

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask about any Austin restaurant..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not st.session_state.reviews_scraped:
            # First message: full pipeline
            with st.status("Running reputation analysis pipeline...", expanded=True) as status:
                st.write("🔍 Extracting restaurant name...")
                search_query = extract_restaurant(prompt)
                st.write(f"Found: **{search_query}**")

                st.write("📍 Looking up restaurant on Google Maps...")
                place_url, display_name = get_place_url(search_query)
                st.session_state.restaurant_name = display_name
                st.write(f"Found: **{display_name}**")

                st.write("⭐ Scraping latest Google Maps reviews...")
                reviews = scrape_reviews(place_url, max_reviews=50)
                st.write(f"Scraped **{len(reviews)}** reviews")

                st.write("📊 Indexing reviews into Elasticsearch...")
                indexed = index_reviews(reviews, display_name)
                es.indices.refresh(index=INDEX_NAME)
                st.write(f"Indexed **{indexed}** reviews with semantic embeddings")

                st.write("🤖 Analyzing sentiment and generating summary...")
                matched = query_reviews(prompt, display_name)
                summary = summarize(prompt, display_name, matched)
                st.write(f"Analyzed **{len(matched)}** relevant reviews")

                status.update(label="Pipeline complete!", state="complete", expanded=False)

            st.session_state.reviews_scraped = True
            st.markdown(summary)
            st.session_state.messages.append({"role": "assistant", "content": summary})
        else:
            # Follow-up: just query existing index
            restaurant = st.session_state.restaurant_name
            with st.status(f"Querying reviews for {restaurant}...", expanded=True) as status:
                st.write("🔎 Searching indexed reviews...")
                matched = query_reviews(prompt, restaurant)
                st.write(f"Found **{len(matched)}** relevant reviews")

                st.write("🤖 Generating response...")
                summary = summarize(prompt, restaurant, matched)
                status.update(label="Done!", state="complete", expanded=False)

            st.markdown(summary)
            st.session_state.messages.append({"role": "assistant", "content": summary})
