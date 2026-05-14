import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
import os

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Airbnb Analytics Dashboard",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background-color: #0f0f0f; }
    .stApp { background-color: #0f0f0f; }
    section[data-testid="stSidebar"] { background-color: #1a1a1a; }
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e, #2a2a3e);
        border: 1px solid #ff5a5f33;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 700; color: #ff5a5f; }
    .metric-label { font-size: 0.85rem; color: #aaa; margin-top: 4px; }
    h1, h2, h3 { color: #ffffff !important; }
    .stSelectbox label, .stSlider label, .stMultiSelect label { color: #ccc !important; }
</style>
""", unsafe_allow_html=True)

# ── MongoDB connection ────────────────────────────────────────────────────────
@st.cache_resource
def get_client():
    uri = os.getenv("MONGODB_URI", st.secrets.get("MONGODB_URI", ""))
    if not uri:
        st.error("❌ MONGODB_URI not set. Add it to `.env` (local) or Streamlit Secrets (cloud).")
        st.stop()
    return MongoClient(uri, serverSelectionTimeoutMS=8000)

@st.cache_data(ttl=300, show_spinner="Loading data from MongoDB…")
def load_data(limit: int = 5000) -> pd.DataFrame:
    client = get_client()
    col = client["sample_airbnb"]["listingsAndReviews"]
    pipeline = [
        {"$limit": limit},
        {"$project": {
            "name": 1,
            "property_type": 1,
            "room_type": 1,
            "bed_type": 1,
            "cancellation_policy": 1,
            "accommodates": 1,
            "bedrooms": 1,
            "beds": 1,
            "bathrooms": 1,
            "price": 1,
            "cleaning_fee": 1,
            "number_of_reviews": 1,
            "review_scores.review_scores_rating": 1,
            "review_scores.review_scores_cleanliness": 1,
            "review_scores.review_scores_location": 1,
            "host.host_is_superhost": 1,
            "host.host_response_time": 1,
            "address.market": 1,
            "address.country": 1,
            "amenities": 1,
            "minimum_nights": 1,
        }},
    ]
    docs = list(col.aggregate(pipeline))
    rows = []
    for d in docs:
        rs = d.get("review_scores", {})
        addr = d.get("address", {})
        host = d.get("host", {})
        rows.append({
            "name": d.get("name", ""),
            "property_type": d.get("property_type", ""),
            "room_type": d.get("room_type", ""),
            "bed_type": d.get("bed_type", ""),
            "cancellation_policy": d.get("cancellation_policy", ""),
            "accommodates": int(d.get("accommodates", 0) or 0),
            "bedrooms": int(d.get("bedrooms", 0) or 0),
            "beds": int(d.get("beds", 0) or 0),
            "bathrooms": float(str(d.get("bathrooms", 0) or 0)),
            "price": float(str(d.get("price", 0) or 0)),
            "cleaning_fee": float(str(d.get("cleaning_fee", 0) or 0)),
            "number_of_reviews": int(d.get("number_of_reviews", 0) or 0),
            "rating": rs.get("review_scores_rating", None),
            "cleanliness_score": rs.get("review_scores_cleanliness", None),
            "location_score": rs.get("review_scores_location", None),
            "is_superhost": bool(host.get("host_is_superhost", False)),
            "response_time": host.get("host_response_time", ""),
            "market": addr.get("market", "Unknown"),
            "country": addr.get("country", "Unknown"),
            "amenity_count": len(d.get("amenities", [])),
            "minimum_nights": int(d.get("minimum_nights", 1) or 1),
        })
    return pd.DataFrame(rows)

# ── Load data ─────────────────────────────────────────────────────────────────
df_raw = load_data()

# ── Sidebar filters ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔍 Filters")

    countries = sorted(df_raw["country"].dropna().unique())
    sel_countries = st.multiselect("Country", countries, default=countries[:5] if len(countries) > 5 else countries)

    prop_types = sorted(df_raw["property_type"].dropna().unique())
    sel_props = st.multiselect("Property Type", prop_types, default=["Apartment", "House"] if "Apartment" in prop_types else prop_types[:2])

    room_types = sorted(df_raw["room_type"].dropna().unique())
    sel_rooms = st.multiselect("Room Type", room_types, default=list(room_types))

    price_max = int(df_raw["price"].quantile(0.98)) or 1000
    price_range = st.slider("Price Range ($/night)", 0, price_max, (0, price_max))

    min_reviews = st.slider("Minimum Reviews", 0, 100, 0)

    superhost_only = st.checkbox("Superhosts Only", value=False)

    st.markdown("---")
    st.caption("Data: MongoDB `sample_airbnb`")

# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_raw.copy()
if sel_countries:
    df = df[df["country"].isin(sel_countries)]
if sel_props:
    df = df[df["property_type"].isin(sel_props)]
if sel_rooms:
    df = df[df["room_type"].isin(sel_rooms)]
df = df[(df["price"] >= price_range[0]) & (df["price"] <= price_range[1])]
df = df[df["number_of_reviews"] >= min_reviews]
if superhost_only:
    df = df[df["is_superhost"]]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🏠 Airbnb Analytics Dashboard")
st.markdown(f"Showing **{len(df):,}** listings · *{len(df_raw):,} total loaded*")
st.markdown("---")

# ── KPI row ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
kpis = [
    (c1, f"${df['price'].median():.0f}", "Median Price / Night"),
    (c2, f"{df['rating'].dropna().mean():.1f} / 100", "Avg Rating"),
    (c3, f"{df['is_superhost'].mean()*100:.1f}%", "Superhosts"),
    (c4, f"{df['number_of_reviews'].median():.0f}", "Median Reviews"),
    (c5, f"{df['amenity_count'].median():.0f}", "Median Amenities"),
]
for col, val, label in kpis:
    col.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{val}</div>
        <div class="metric-label">{label}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("###")

# ── Row 1: Price distribution + Room type breakdown ───────────────────────────
col_a, col_b = st.columns([3, 2])

with col_a:
    st.markdown("### Price Distribution by Room Type")
    df_price = df[df["price"] > 0]
    fig_box = px.box(
        df_price, x="room_type", y="price", color="room_type",
        color_discrete_sequence=["#ff5a5f", "#fc642d", "#00a699", "#484848"],
        labels={"price": "Price ($/night)", "room_type": "Room Type"},
    )
    fig_box.update_layout(
        plot_bgcolor="#1a1a2e", paper_bgcolor="#1a1a2e",
        font_color="#ccc", showlegend=False,
        yaxis=dict(gridcolor="#333"), xaxis=dict(gridcolor="#333", title=None),
        margin=dict(l=40, r=20, t=20, b=40),
        height=400,
    )
    st.plotly_chart(fig_box, use_container_width=True)

with col_b:
    st.markdown("### Property Type Mix")
    top_props = df["property_type"].value_counts().head(8)
    fig_pie = px.pie(
        values=top_props.values, names=top_props.index,
        color_discrete_sequence=["#ff5a5f", "#fc642d", "#e8735a", "#00a699", "#007a72", "#767676", "#484848", "#2a2a2a"],
        hole=0.45,
    )
    fig_pie.update_traces(
        textposition="inside",
        textinfo="percent",
        insidetextorientation="radial",
        hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
    )
    fig_pie.update_layout(
        plot_bgcolor="#1a1a2e", paper_bgcolor="#1a1a2e",
        font_color="#ccc",
        showlegend=True,
        legend=dict(
            bgcolor="#1a1a2e",
            bordercolor="#333",
            font=dict(size=11, color="#ccc"),
            orientation="v",
            x=1.02, y=0.5,
            xanchor="left",
            yanchor="middle",
        ),
        margin=dict(l=10, r=120, t=20, b=20),
    )
    st.plotly_chart(fig_pie, use_container_width=True)

# ── Row 2: Market avg price bar + Rating vs Price scatter ─────────────────────
col_c, col_d = st.columns(2)

with col_c:
    st.markdown("### Average Price by Market")
    market_avg = (
        df[df["price"] > 0]
        .groupby("market")["price"]
        .median()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
    )
    fig_bar = px.bar(
        market_avg, x="price", y="market", orientation="h",
        color="price", color_continuous_scale="reds",
        labels={"price": "Median Price ($/night)", "market": "Market"},
    )
    fig_bar.update_layout(
        plot_bgcolor="#1a1a2e", paper_bgcolor="#1a1a2e",
        font_color="#ccc", coloraxis_showscale=False,
        yaxis=dict(autorange="reversed", gridcolor="#333", tickfont=dict(size=11)),
        xaxis=dict(gridcolor="#333"),
        margin=dict(l=130, r=20, t=20, b=40),
        height=420,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with col_d:
    st.markdown("### Rating vs Price")
    df_scatter = df[(df["price"] > 0) & (df["rating"].notna())].sample(min(800, len(df)))
    fig_scatter = px.scatter(
        df_scatter, x="price", y="rating",
        color="room_type", size="number_of_reviews",
        size_max=20, opacity=0.7,
        color_discrete_sequence=["#ff5a5f", "#fc642d", "#00a699", "#484848"],
        labels={"price": "Price ($/night)", "rating": "Overall Rating"},
    )
    fig_scatter.update_layout(
        plot_bgcolor="#1a1a2e", paper_bgcolor="#1a1a2e",
        font_color="#ccc",
        xaxis=dict(gridcolor="#333"),
        yaxis=dict(gridcolor="#333"),
        legend=dict(bgcolor="#1a1a2e", bordercolor="#444", font=dict(size=11)),
        margin=dict(l=40, r=20, t=20, b=40),
        height=420,
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# ── Row 3: Cancellation policy + Amenity count histogram ──────────────────────
col_e, col_f = st.columns(2)

with col_e:
    st.markdown("### Cancellation Policy Distribution")
    cancel_counts = df["cancellation_policy"].value_counts().reset_index()
    cancel_counts.columns = ["policy", "count"]
    fig_cancel = px.bar(
        cancel_counts, x="policy", y="count", color="policy",
        color_discrete_sequence=["#ff5a5f", "#fc642d", "#00a699", "#767676", "#484848"],
        labels={"policy": "Policy", "count": "Listings"},
    )
    fig_cancel.update_layout(
        plot_bgcolor="#1a1a2e", paper_bgcolor="#1a1a2e",
        font_color="#ccc", showlegend=False,
        xaxis=dict(gridcolor="#333", tickangle=-25, tickfont=dict(size=11)),
        yaxis=dict(gridcolor="#333"),
        margin=dict(l=40, r=20, t=20, b=80),
        height=380,
    )
    st.plotly_chart(fig_cancel, use_container_width=True)

with col_f:
    st.markdown("### Amenity Count Distribution")
    fig_hist = px.histogram(
        df, x="amenity_count", nbins=30,
        color_discrete_sequence=["#00a699"],
        labels={"amenity_count": "Number of Amenities", "count": "Listings"},
    )
    fig_hist.update_layout(
        plot_bgcolor="#1a1a2e", paper_bgcolor="#1a1a2e",
        font_color="#ccc", bargap=0.05,
        xaxis=dict(gridcolor="#333"),
        yaxis=dict(gridcolor="#333"),
        margin=dict(l=40, r=20, t=20, b=40),
        height=380,
    )
    st.plotly_chart(fig_hist, use_container_width=True)

# ── Row 4: Superhost comparison radar ────────────────────────────────────────
st.markdown("### Superhost vs Regular Host — Score Comparison")
col_g, col_h = st.columns([2, 3])

with col_g:
    host_summary = (
        df.groupby("is_superhost")[["rating", "cleanliness_score", "location_score", "price", "number_of_reviews"]]
        .median()
        .rename(index={True: "Superhost", False: "Regular Host"})
        .round(1)
    )
    host_summary.columns = ["Rating", "Cleanliness", "Location", "Price", "Reviews"]
    st.dataframe(
        host_summary.style.background_gradient(cmap="Reds", axis=None),
        use_container_width=True,
    )

with col_h:
    categories = ["Rating", "Cleanliness", "Location", "Reviews (norm)"]
    fig_radar = go.Figure()
    for is_super, label, color in [(True, "Superhost", "#ff5a5f"), (False, "Regular Host", "#00a699")]:
        sub = df[df["is_superhost"] == is_super]
        vals = [
            sub["rating"].median() or 0,
            (sub["cleanliness_score"].median() or 0) * 10,
            (sub["location_score"].median() or 0) * 10,
            min(sub["number_of_reviews"].median() or 0, 100),
        ]
        fig_radar.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=categories + [categories[0]],
            fill="toself", name=label,
            line_color=color, fillcolor=color,
            opacity=0.35,
        ))
    fig_radar.update_layout(
        polar=dict(
            bgcolor="#1a1a2e",
            radialaxis=dict(visible=True, range=[0, 100], gridcolor="#444", color="#888"),
            angularaxis=dict(gridcolor="#444", color="#ccc"),
        ),
        paper_bgcolor="#1a1a2e", font_color="#ccc",
        legend=dict(bgcolor="#1a1a2e", bordercolor="#333", font=dict(size=12)),
        margin=dict(l=60, r=60, t=40, b=40),
        height=400,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

# ── Row 5: Top listings table ─────────────────────────────────────────────────
st.markdown("### Top-Rated Listings (min. 20 reviews)")
top = (
    df[df["number_of_reviews"] >= 20]
    .sort_values("rating", ascending=False)
    .head(10)[["name", "market", "country", "property_type", "room_type", "price", "rating", "number_of_reviews", "amenity_count"]]
    .rename(columns={
        "name": "Name", "market": "Market", "country": "Country",
        "property_type": "Type", "room_type": "Room",
        "price": "Price/Night", "rating": "Rating",
        "number_of_reviews": "Reviews", "amenity_count": "Amenities",
    })
    .reset_index(drop=True)
)
st.dataframe(top, use_container_width=True, height=380)

st.markdown("---")
st.caption("Built with Streamlit · MongoDB Atlas `sample_airbnb` · Credentials loaded from environment variables / Streamlit Secrets")
