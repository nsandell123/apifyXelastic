import os
import requests
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")


def get_place_url(restaurant_name: str) -> str:
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
    data = resp.json()
    place = data["places"][0]
    print(f"  Found: {place['displayName']['text']} — {place['formattedAddress']}")
    return place["googleMapsUri"]


if __name__ == "__main__":
    test_inputs = [
        "Uchi Austin TX",
        "Franklin BBQ Austin TX",
        "Ramen Tatsu-Ya Austin TX",
    ]
    for name in test_inputs:
        url = get_place_url(name)
        print(f"Input:  {name}")
        print(f"URL:    {url}")
        print()
