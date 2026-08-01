import os
from dotenv import load_dotenv
from apify_client import ApifyClient

load_dotenv()

apify_client = ApifyClient(os.getenv("APIFY_API_TOKEN"))


def scrape_reviews(place_url: str, max_reviews: int = 50) -> list[dict]:
    run_input = {
        "startUrls": [{"url": place_url}],
        "maxReviews": max_reviews,
        "reviewsSort": "newest",
        "language": "en",
        "personalData": True,
    }

    print(f"  Starting Apify scrape (max {max_reviews} reviews)...")
    run = apify_client.actor("compass/google-maps-reviews-scraper").call(run_input=run_input)
    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else run.default_dataset_id
    print(f"  Scrape complete. Dataset: {dataset_id}")

    items = list(apify_client.dataset(dataset_id).iterate_items())
    print(f"  Got {len(items)} reviews")
    return items


if __name__ == "__main__":
    test_url = "https://maps.google.com/?cid=7800725174736543982"
    reviews = scrape_reviews(test_url, max_reviews=10)

    for r in reviews[:3]:
        print(f"\n{'='*60}")
        print(f"  Author: {r.get('name', 'N/A')}")
        print(f"  Stars:  {r.get('stars', 'N/A')}")
        print(f"  Date:   {r.get('publishedAtDate', 'N/A')}")
        print(f"  Text:   {(r.get('text') or 'No text')[:120]}")
