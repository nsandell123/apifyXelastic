# Restaurant Reputation Agent

Real-time restaurant reputation analysis powered by Apify, Elasticsearch, and OpenAI. Built at the **Elastic x Apify Hack Night Austin 2026**.

## What it does

Type any restaurant name and the agent:

1. **Extracts** the restaurant name from your question (OpenAI)
2. **Finds** the restaurant on Google Maps (Google Places API)
3. **Scrapes** the latest reviews in real time (Apify)
4. **Indexes** reviews with semantic embeddings (Elasticsearch + ELSER)
5. **Summarizes** sentiment, praises, complaints, and notable quotes (OpenAI)

The full pipeline runs live in ~20 seconds.

## Tech Stack

- **Apify** — `compass/Google-Maps-Reviews-Scraper` for real-time review scraping
- **Elasticsearch Serverless** — `semantic_text` field with ELSER for hybrid search (keyword + vector)
- **Google Places API** — restaurant name → Google Maps URL resolution
- **OpenAI** — entity extraction and natural language summarization
- **Streamlit** — chat interface

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```
APIFY_API_TOKEN=your_token
GOOGLE_PLACES_API_KEY=your_key
ELASTICSEARCH_URL=your_url
ELASTICSEARCH_API_KEY=your_key
OPENAI_API_KEY=your_key
```

Run:

```bash
streamlit run app.py
```

## Architecture

```
User question
    │
    ▼
Extract restaurant name (OpenAI)
    │
    ▼
Resolve Google Maps URL (Places API)
    │
    ▼
Scrape reviews (Apify)
    │
    ▼
Index with semantic embeddings (Elasticsearch)
    │
    ▼
Query + Summarize (Elasticsearch → OpenAI)
    │
    ▼
Chat response with sentiment analysis
```
