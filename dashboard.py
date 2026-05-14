import os
import certifi
import pandas as pd
import plotly.express as px
import streamlit as st
from pymongo import MongoClient

st.set_page_config(page_title="Airbnb Analytics", page_icon="🏠", layout="wide")

# ---------- MongoDB connection ----------
MONGO_URI = st.secrets.get("MONGODB_URI", os.getenv("MONGODB_URI"))

if not MONGO_URI:
    st.error("Missing MongoDB connection string. Add MONGODB_URI to Streamlit secrets.")
    st.stop()


@st.cache_resource
def get_client():
    return MongoClient(MONGO_URI, tlsCAFile=certifi.where())


@st.cache_data(ttl=600)
def load_data(limit: int = 5000) -> pd.DataFrame:
    col = get_client()["sample_airbnb"]["listingsAndReviews"]
    cursor = col.find(
        {},
        {
            "name": 1,
            "property_type": 1,
            "room_type": 1,
            "price": 1,
            "bedrooms": 1,
            "number_of_reviews": 1,
            "review_scores.review_scores_rating": 1,
            "address.country": 1,
            "address.market": 1,
        },
    ).limit(limit)

    rows = []
    for doc in cursor:
        rs = doc.get("review_scores", {})
        addr = doc.get("address", {})
        rows.append(
            {
                "name": doc.get("name", ""),
                "property_type": doc.get("property_type", "Unknown"),
                "room_type": doc.get("room_type", "Unknown"),
                "price": float(str(doc.get("price", 0) or 0)),
                "bedrooms": int(doc.get("bedrooms", 0) or 0),
                "reviews": int(doc.get("number_of_reviews", 0) or 0),
                "rating": rs.get("review_scores_rating"),
                "country": addr.get("country", "Unknown"),
                "market": addr.get("market", "Unknown"),
            }
        )
    return pd.DataFrame(rows)


# ---------- Load ----------
with st.spinner("Loading data…"):
    df = load_data()

if df.empty:
    st.warning("No data found in sample_airbnb.listingsAndReviews")
    st.stop()

# ---------- Sidebar filters ----------
with st.sidebar:
    st.title("🔍 Filters")

    all_countries = sorted(df["country"].dropna().unique())
    countries = st.multiselect("Country", all_countries, default=all_countries)

    all_types = sorted(df["property_type"].dropna().unique())
    prop_types = st.multiselect("Property Type", all_types, default=all_types)

    price_max = int(df["price"].quantile(0.95)) or 500
    price_range = st.slider("Price Range ($/night)", 0, price_max, (0, price_max))

    min_rating = st.slider("Minimum Rating", 0, 100, 0)

    st.caption(f"Total loaded: {len(df):,} listings")

# ---------- Filter ----------
filtered = df.copy()
if countries:
    filtered = filtered[filtered["country"].isin(countries)]
if prop_types:
    filtered = filtered[filtered["property_type"].isin(prop_types)]
filtered = filtered[
    (filtered["price"] >= price_range[0]) & (filtered["price"] <= price_range[1])
]
filtered = filtered[filtered["rating"].isna() | (filtered["rating"] >= min_rating)]

# ---------- Header ----------
st.title("🏠 Airbnb Analytics Dashboard")
st.caption(
    f"Showing **{len(filtered):,}** of {len(df):,} listings · MongoDB `sample_airbnb`"
)

# ---------- KPIs ----------
k1, k2, k3, k4 = st.columns(4)
avg_price = filtered.loc[filtered["price"] > 0, "price"].mean()
avg_rating = filtered["rating"].dropna().mean()

k1.metric("Listings", f"{len(filtered):,}")
k2.metric("Avg Price / Night", f"${avg_price:.2f}" if len(filtered) else "—")
k3.metric("Avg Rating", f"{avg_rating:.1f} / 100" if pd.notna(avg_rating) else "—")
k4.metric("Countries", filtered["country"].nunique())

st.divider()

# ---------- Tabs ----------
tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "💰 Prices", "⭐ Ratings", "📋 Data"])

# ── Overview ──────────────────────────────────────────────────────────────────
with tab1:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Listings by Country")
        country_df = (
            filtered["country"].value_counts().reset_index()
        )
        country_df.columns = ["Country", "Listings"]
        fig = px.bar(
            country_df,
            x="Listings",
            y="Country",
            orientation="h",
            color="Listings",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            coloraxis_showscale=False,
            yaxis_title="",
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Property Type Mix")
        top8 = filtered["property_type"].value_counts().head(8)
        fig = px.pie(
            values=top8.values,
            names=top8.index,
            hole=0.45,
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Room Type Breakdown")
    room_df = filtered["room_type"].value_counts().reset_index()
    room_df.columns = ["Room Type", "Listings"]
    fig = px.bar(
        room_df,
        x="Room Type",
        y="Listings",
        color="Room Type",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ── Prices ────────────────────────────────────────────────────────────────────
with tab2:
    df_price = filtered[filtered["price"] > 0]

    st.subheader("Price Distribution")
    fig = px.histogram(
        df_price,
        x="price",
        nbins=60,
        color_discrete_sequence=["#636EFA"],
        labels={"price": "Price ($/night)"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Median Price by Property Type")
        med_type = (
            df_price.groupby("property_type")["price"]
            .median()
            .sort_values(ascending=False)
            .reset_index()
        )
        med_type.columns = ["Property Type", "Median Price"]
        fig = px.bar(
            med_type,
            x="Median Price",
            y="Property Type",
            orientation="h",
            color="Median Price",
            color_continuous_scale="Reds",
            labels={"Median Price": "Median Price ($/night)"},
        )
        fig.update_layout(
            coloraxis_showscale=False,
            yaxis_title="",
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Median Price by Country")
        med_country = (
            df_price.groupby("country")["price"]
            .median()
            .sort_values(ascending=False)
            .reset_index()
        )
        med_country.columns = ["Country", "Median Price"]
        fig = px.bar(
            med_country,
            x="Median Price",
            y="Country",
            orientation="h",
            color="Median Price",
            color_continuous_scale="Oranges",
            labels={"Median Price": "Median Price ($/night)"},
        )
        fig.update_layout(
            coloraxis_showscale=False,
            yaxis_title="",
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

# ── Ratings ───────────────────────────────────────────────────────────────────
with tab3:
    df_rated = filtered[filtered["rating"].notna()]

    st.subheader("Rating Distribution")
    fig = px.histogram(
        df_rated,
        x="rating",
        nbins=40,
        color_discrete_sequence=["#00CC96"],
        labels={"rating": "Rating (out of 100)"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Rating vs Price")
    df_scatter = df_rated[df_rated["price"] > 0]
    sample_size = min(800, len(df_scatter))
    fig = px.scatter(
        df_scatter.sample(sample_size, random_state=42),
        x="price",
        y="rating",
        color="room_type",
        size="reviews",
        size_max=20,
        hover_data=["name", "country", "market", "property_type"],
        opacity=0.7,
        labels={
            "price": "Price ($/night)",
            "rating": "Rating (out of 100)",
            "room_type": "Room Type",
        },
    )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

# ── Data ──────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Listings Explorer")

    search = st.text_input(
        "Search by name, country, or market",
        placeholder="e.g. Apartment, Hong Kong…",
    )
    display = filtered.copy()
    if search:
        mask = (
            display["name"].str.contains(search, case=False, na=False)
            | display["country"].str.contains(search, case=False, na=False)
            | display["market"].str.contains(search, case=False, na=False)
        )
        display = display[mask]

    st.caption(f"{len(display):,} results")
    st.dataframe(
        display[
            [
                "name", "country", "market", "property_type",
                "room_type", "price", "bedrooms", "rating", "reviews",
            ]
        ]
        .rename(
            columns={
                "property_type": "type",
                "room_type": "room",
                "reviews": "# reviews",
            }
        )
        .sort_values("rating", ascending=False)
        .reset_index(drop=True),
        use_container_width=True,
        height=450,
    )

    st.download_button(
        "⬇️ Download filtered data as CSV",
        display.to_csv(index=False),
        file_name="airbnb_filtered.csv",
        mime="text/csv",
    )
