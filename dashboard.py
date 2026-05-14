import os
import certifi
import pandas as pd
import streamlit as st
from pymongo import MongoClient

# ---------- Page Config ----------
st.set_page_config(page_title="Airbnb MongoDB Dashboard", layout="wide")
st.title("🏠 Airbnb Dashboard (MongoDB + Streamlit)")

# ---------- Secure MongoDB Connection ----------
# For local dev: set MONGODB_URI in .streamlit/secrets.toml or environment variable
MONGO_URI = st.secrets.get("MONGODB_URI", os.getenv("MONGODB_URI"))

if not MONGO_URI:
    st.error("Missing MongoDB connection string. Add MONGODB_URI to Streamlit secrets.")
    st.stop()

@st.cache_resource
def get_client():
    return MongoClient(MONGO_URI, tlsCAFile=certifi.where())

client = get_client()
collection = client["sample_airbnb"]["listingsAndReviews"]

# ---------- Load Data ----------
@st.cache_data(ttl=600)
def load_data(limit=5000):
    cursor = collection.find(
        {},
        {
            "name": 1,
            "property_type": 1,
            "price": 1,
            "bedrooms": 1,
            "review_scores.review_scores_rating": 1,
            "address.country": 1,
        },
    ).limit(limit)

    rows = []
    for doc in cursor:
        rows.append({
            "name": doc.get("name"),
            "property_type": doc.get("property_type"),
            "price": float(str(doc.get("price", 0) or 0)),
            "bedrooms": doc.get("bedrooms", 0),
            "rating": doc.get("review_scores", {}).get("review_scores_rating"),
            "country": doc.get("address", {}).get("country"),
        })

    return pd.DataFrame(rows)


df = load_data()

if df.empty:
    st.warning("No data found in sample_airbnb.listingsAndReviews")
    st.stop()

# ---------- Sidebar Filters ----------
st.sidebar.header("Filters")
country = st.sidebar.selectbox("Country", ["All"] + sorted(df["country"].dropna().unique().tolist()))
ptype = st.sidebar.selectbox("Property Type", ["All"] + sorted(df["property_type"].dropna().unique().tolist()))

filtered = df.copy()
if country != "All":
    filtered = filtered[filtered["country"] == country]
if ptype != "All":
    filtered = filtered[filtered["property_type"] == ptype]

# ---------- KPIs ----------
col1, col2, col3 = st.columns(3)
col1.metric("Listings", len(filtered))
col2.metric("Avg Price", f"${filtered['price'].mean():.2f}")
col3.metric("Avg Rating", f"{filtered['rating'].mean():.1f}")

# ---------- Charts ----------
st.subheader("Price Distribution")
st.bar_chart(filtered.groupby("property_type")["price"].mean().sort_values(ascending=False))

st.subheader("Listings by Country")
st.bar_chart(filtered["country"].value_counts())

# ---------- Raw Data ----------
st.subheader("Sample Data")
st.dataframe(filtered.head(100), use_container_width=True)
