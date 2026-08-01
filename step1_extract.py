import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def extract_restaurant(user_message: str) -> str:
    response = client.chat.completions.create(
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


if __name__ == "__main__":
    test_inputs = [
        "What are people saying about Uchi this month?",
        "How's the food at Franklin BBQ?",
        "Tell me about reviews for Ramen Tatsu-Ya",
    ]
    for msg in test_inputs:
        result = extract_restaurant(msg)
        print(f"Input:  {msg}")
        print(f"Output: {result}")
        print()
