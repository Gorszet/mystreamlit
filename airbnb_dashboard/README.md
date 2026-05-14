# Airbnb Analytics Dashboard

A Streamlit dashboard visualising MongoDB's `sample_airbnb.listingsAndReviews` dataset.

## Credential Security Model

| Environment | How credentials are stored | Committed to git? |
|---|---|---|
| Local dev | `.streamlit/secrets.toml` (gitignored) | ❌ Never |
| Streamlit Cloud | Encrypted Secrets UI | ❌ Never |
| CI/CD | Repository secret env var | ❌ Never |

The app reads `MONGODB_URI` in priority order:
1. `os.getenv("MONGODB_URI")` — shell env var / `.env` file
2. `st.secrets["MONGODB_URI"]` — Streamlit Secrets (cloud)

**The password never appears in source code.**

## Local Setup

```bash
git clone <your-repo>
cd airbnb_dashboard
pip install -r requirements.txt

# Copy template and fill in your Atlas URI
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# edit secrets.toml with your real URI

streamlit run app.py
```

## Deploy to Streamlit Community Cloud (free)

1. Push this repo to GitHub (`.streamlit/secrets.toml` is gitignored — safe).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → select your repo.
3. In **Advanced settings → Secrets**, paste:
   ```toml
   MONGODB_URI = "mongodb+srv://user:password@cluster.mongodb.net/..."
   ```
4. Click **Deploy**. Streamlit encrypts and injects the secret at runtime.

## Features

- KPI row: median price, avg rating, superhost %, median reviews, median amenities
- Price distribution by room type (box plot)
- Property type breakdown (donut)
- Median price by market (horizontal bar)
- Rating vs Price scatter (bubble sized by review count)
- Cancellation policy distribution
- Amenity count histogram
- Superhost vs Regular Host radar comparison
- Top-rated listings table

## Sidebar Filters

Country · Property Type · Room Type · Price Range · Minimum Reviews · Superhost Only
