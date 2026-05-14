import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import numpy as np

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Airbnb Analytics",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Theme: clean white ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Serif+Display&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #FFFFFF;
    color: #1A1A2E;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #F8F8FA;
    border-right: 1px solid #EBEBEB;
}
[data-testid="stSidebar"] .stMarkdown h2 {
    font-family: 'DM Serif Display', serif;
    font-size: 22px;
    color: #1A1A2E;
    letter-spacing: -0.3px;
}

/* Top-level metric cards */
[data-testid="stMetric"] {
    background: #F8F8FA;
    border: 1px solid #EBEBEB;
    border-radius: 12px;
    padding: 18px 20px;
}
[data-testid="stMetricLabel"] { color: #777 !important; font-size: 13px !important; }
[data-testid="stMetricValue"] { color: #1A1A2E !important; font-size: 26px !important; font-weight: 600 !important; }
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* Section headings */
.section-title {
    font-family: 'DM Serif Display', serif;
    font-size: 17px;
    color: #1A1A2E;
    margin: 0 0 2px 0;
    letter-spacing: -0.2px;
}
.section-sub {
    font-size: 12px;
    color: #999;
    margin-bottom: 12px;
}

/* Card wrapper */
.card {
    background: #FFFFFF;
    border: 1px solid #EBEBEB;
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 4px;
}

/* Pills / badges */
.pill {
    display: inline-block;
    padding: 3px 11px;
    border-radius: 99px;
    font-size: 12px;
    font-weight: 500;
    margin-right: 5px;
    margin-bottom: 4px;
}
.pill-red   { background: #FFF0F0; color: #D63031; }
.pill-blue  { background: #EBF5FF; color: #0984E3; }
.pill-green { background: #EDFDF5; color: #00B894; }
.pill-amber { background: #FFF8ED; color: #E67E22; }

/* Plotly chart backgrounds */
.js-plotly-plot .plotly { background: transparent !important; }

/* Hide Streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* Divider */
hr { border: none; border-top: 1px solid #EBEBEB; margin: 20px 0; }

/* Dataframe */
[data-testid="stDataFrame"] { border: 1px solid #EBEBEB; border-radius: 10px; }

/* Selectbox / slider label */
label { color: #555 !important; font-size: 13px !important; }
</style>
""", unsafe_allow_html=True)

# ─── Plotly base template ────────────────────────────────────────────────────
PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="DM Sans", color="#1A1A2E"),
    margin=dict(l=0, r=0, t=30, b=0),
    xaxis=dict(gridcolor="#F0F0F0", linecolor="#EBEBEB", tickfont=dict(size=11, color="#888")),
    yaxis=dict(gridcolor="#F0F0F0", linecolor="#EBEBEB", tickfont=dict(size=11, color="#888")),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=12, color="#555")),
    colorway=["#0984E3", "#00B894", "#E17055", "#6C5CE7", "#FDCB6E", "#74B9FF"],
)

COLORS = {
    "blue":   "#0984E3",
    "teal":   "#00B894",
    "coral":  "#E17055",
    "purple": "#6C5CE7",
    "amber":  "#FDCB6E",
    "red":    "#D63031",
    "gray":   "#B2BEC3",
}

# ─── MongoDB connection ──────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_client():
    uri = st.secrets["mongodb"]["uri"]
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")
    return client

@st.cache_data(show_spinner=False, ttl=3600)
def load_data():
    client = get_client()
    db = client["sample_airbnb"]
    col = db["listingsAndReviews"]
    docs = list(col.find({}, {
        "_id": 1, "name": 1, "property_type": 1, "room_type": 1,
        "price": 1, "bedrooms": 1, "beds": 1, "bathrooms": 1,
        "accommodates": 1, "amenities": 1, "number_of_reviews": 1,
        "review_scores": 1, "address": 1, "host": 1,
        "cancellation_policy": 1, "minimum_nights": 1,
        "availability": 1, "first_review": 1,
    }))

    rows = []
    for d in docs:
        def num(v):
            if isinstance(v, dict):
                return float(v.get("$numberDecimal", v.get("$numberInt", 0) or 0) or 0)
            return float(v) if v else 0.0

        addr = d.get("address", {})
        loc  = addr.get("location", {}).get("coordinates", [None, None])
        rs   = d.get("review_scores", {})
        host = d.get("host", {})
        avail = d.get("availability", {})

        rows.append({
            "id":               str(d.get("_id", "")),
            "name":             d.get("name", ""),
            "property_type":    d.get("property_type", "Other"),
            "room_type":        d.get("room_type", "Other"),
            "price":            num(d.get("price")),
            "bedrooms":         num(d.get("bedrooms")),
            "beds":             num(d.get("beds")),
            "bathrooms":        num(d.get("bathrooms")),
            "accommodates":     num(d.get("accommodates")),
            "amenities_count":  len(d.get("amenities", [])),
            "num_reviews":      num(d.get("number_of_reviews")),
            "cancellation":     d.get("cancellation_policy", "unknown"),
            "minimum_nights":   num(d.get("minimum_nights")),
            "country":          addr.get("country", "Unknown"),
            "market":           addr.get("market", "Unknown"),
            "lon":              float(loc[0]) if loc[0] is not None else None,
            "lat":              float(loc[1]) if loc[1] is not None else None,
            "is_superhost":     host.get("host_is_superhost", False),
            "host_name":        host.get("host_name", ""),
            "score_rating":     num(rs.get("review_scores_rating")),
            "score_accuracy":   num(rs.get("review_scores_accuracy")),
            "score_cleanliness":num(rs.get("review_scores_cleanliness")),
            "score_checkin":    num(rs.get("review_scores_checkin")),
            "score_comm":       num(rs.get("review_scores_communication")),
            "score_location":   num(rs.get("review_scores_location")),
            "score_value":      num(rs.get("review_scores_value")),
            "avail_30":         num(avail.get("availability_30")),
            "avail_365":        num(avail.get("availability_365")),
        })

    return pd.DataFrame(rows)

# ─── Load ────────────────────────────────────────────────────────────────────
with st.spinner("Connecting to MongoDB…"):
    try:
        df_raw = load_data()
    except Exception as e:
        st.error(f"**Connection failed:** {e}\n\nCheck your `secrets.toml` and MongoDB URI.")
        st.stop()

# ─── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏠 Airbnb\nAnalytics")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        ["📊 Overview", "🌍 By Country", "🏡 Properties", "⭐ Reviews", "💰 Pricing"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("**Filters**")

    countries = ["All"] + sorted(df_raw["country"].dropna().unique().tolist())
    sel_country = st.selectbox("Country", countries)

    room_types = ["All"] + sorted(df_raw["room_type"].dropna().unique().tolist())
    sel_room = st.selectbox("Room type", room_types)

    price_min, price_max = int(df_raw["price"].min()), min(int(df_raw["price"].max()), 2000)
    price_range = st.slider("Price / night ($)", price_min, price_max, (price_min, 500))

    st.markdown("---")
    st.caption(f"Dataset: **{len(df_raw):,}** listings · MongoDB sample\\_airbnb")

# ─── Apply filters ───────────────────────────────────────────────────────────
df = df_raw.copy()
if sel_country != "All":
    df = df[df["country"] == sel_country]
if sel_room != "All":
    df = df[df["room_type"] == sel_room]
df = df[(df["price"] >= price_range[0]) & (df["price"] <= price_range[1])]

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.markdown('<p class="section-title">Overview</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">High-level snapshot of the filtered dataset</p>', unsafe_allow_html=True)

    # KPI row
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total listings",     f"{len(df):,}")
    k2.metric("Avg. price / night", f"${df['price'].mean():.0f}" if len(df) else "—")
    k3.metric("Avg. review score",  f"{df[df['score_rating']>0]['score_rating'].mean():.1f}" if len(df) else "—")
    k4.metric("Superhosts",         f"{df['is_superhost'].sum():,}  ({df['is_superhost'].mean()*100:.0f}%)" if len(df) else "—")
    k5.metric("Countries covered",  str(df["country"].nunique()))

    st.markdown("<br>", unsafe_allow_html=True)

    # Row 1: listings by country + room type donut
    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<p class="section-title">Listings by country</p>', unsafe_allow_html=True)
        cnt = df.groupby("country").size().reset_index(name="count").sort_values("count", ascending=True)
        fig = px.bar(cnt, x="count", y="country", orientation="h",
                     color="count", color_continuous_scale=["#B3D9FF", "#0984E3"])
        fig.update_layout(**PLOT_LAYOUT, height=300, coloraxis_showscale=False)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<p class="section-title">Room type</p>', unsafe_allow_html=True)
        rt = df.groupby("room_type").size().reset_index(name="count")
        fig2 = px.pie(rt, names="room_type", values="count", hole=0.6,
                      color_discrete_sequence=[COLORS["blue"], COLORS["coral"], COLORS["gray"]])
        fig2.update_layout(**PLOT_LAYOUT, height=300,
                           legend=dict(orientation="h", y=-0.1, font=dict(size=11)))
        fig2.update_traces(textinfo="percent", textfont_size=12)
        st.plotly_chart(fig2, use_container_width=True)

    # Row 2: price distribution + cancellation policy
    c3, c4 = st.columns([3, 2])
    with c3:
        st.markdown('<p class="section-title">Price distribution (< $1,000/night)</p>', unsafe_allow_html=True)
        df_p = df[df["price"] < 1000]
        fig3 = px.histogram(df_p, x="price", nbins=40,
                            color_discrete_sequence=[COLORS["teal"]])
        fig3.update_layout(**PLOT_LAYOUT, height=260,
                           bargap=0.05,
                           xaxis_title="Price ($)", yaxis_title="Listings")
        fig3.update_traces(marker_line_width=0)
        st.plotly_chart(fig3, use_container_width=True)

    with c4:
        st.markdown('<p class="section-title">Cancellation policy</p>', unsafe_allow_html=True)
        cp = df.groupby("cancellation").size().reset_index(name="count").sort_values("count")
        fig4 = px.bar(cp, x="count", y="cancellation", orientation="h",
                      color_discrete_sequence=[COLORS["purple"]])
        fig4.update_layout(**PLOT_LAYOUT, height=260, xaxis_title="Listings", yaxis_title="")
        fig4.update_traces(marker_line_width=0)
        st.plotly_chart(fig4, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 2 — BY COUNTRY
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🌍 By Country":
    st.markdown('<p class="section-title">By Country</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Pricing, volume, and review scores broken down by country</p>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">Avg. price by country ($)</p>', unsafe_allow_html=True)
        avg_p = df.groupby("country")["price"].mean().reset_index().sort_values("price", ascending=True)
        fig = px.bar(avg_p, x="price", y="country", orientation="h",
                     color="price", color_continuous_scale=["#FFF8ED", "#E67E22"])
        fig.update_layout(**PLOT_LAYOUT, height=320, coloraxis_showscale=False)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<p class="section-title">Avg. review score by country</p>', unsafe_allow_html=True)
        avg_r = (df[df["score_rating"] > 0]
                 .groupby("country")["score_rating"].mean()
                 .reset_index()
                 .sort_values("score_rating", ascending=True))
        fig2 = px.bar(avg_r, x="score_rating", y="country", orientation="h",
                      color="score_rating", color_continuous_scale=["#EDFDF5", "#00B894"])
        fig2.update_layout(**PLOT_LAYOUT, height=320, coloraxis_showscale=False)
        fig2.update_traces(marker_line_width=0)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # Map
    st.markdown('<p class="section-title">Geographic distribution</p>', unsafe_allow_html=True)
    df_map = df[df["lat"].notna() & df["lon"].notna()].copy()
    df_map["price_capped"] = df_map["price"].clip(upper=500)
    if not df_map.empty:
        fig_map = px.scatter_map(
            df_map, lat="lat", lon="lon",
            color="price_capped",
            size_max=8,
            zoom=1,
            hover_name="name",
            hover_data={"country": True, "price": True, "room_type": True,
                        "lat": False, "lon": False, "price_capped": False},
            color_continuous_scale=["#B3D9FF", "#0984E3", "#003D7A"],
            labels={"price_capped": "Price ($)"},
            map_style="carto-positron",
        )
        fig_map.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=0, b=0),
            height=420,
            coloraxis_colorbar=dict(title="Price ($)", thickness=12, len=0.5),
        )
        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("No coordinate data available for current filters.")

    st.markdown("---")

    # Country summary table
    st.markdown('<p class="section-title">Country summary table</p>', unsafe_allow_html=True)
    summary = df.groupby("country").agg(
        Listings=("id", "count"),
        Avg_Price=("price", "mean"),
        Median_Price=("price", "median"),
        Superhosts=("is_superhost", "sum"),
        Avg_Rating=("score_rating", lambda x: x[x > 0].mean()),
    ).reset_index().rename(columns={"country": "Country"})
    summary["Avg_Price"] = summary["Avg_Price"].round(0).astype(int)
    summary["Median_Price"] = summary["Median_Price"].round(0).astype(int)
    summary["Avg_Rating"] = summary["Avg_Rating"].round(1)
    summary = summary.sort_values("Listings", ascending=False)
    st.dataframe(summary, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 3 — PROPERTIES
# ═══════════════════════════════════════════════════════════════════════════
elif page == "🏡 Properties":
    st.markdown('<p class="section-title">Properties</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Property types, bedroom distributions, and amenities</p>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">Top 10 property types</p>', unsafe_allow_html=True)
        pt = df.groupby("property_type").size().reset_index(name="count") \
               .sort_values("count", ascending=False).head(10)
        pt = pt.sort_values("count", ascending=True)
        fig = px.bar(pt, x="count", y="property_type", orientation="h",
                     color="count", color_continuous_scale=["#E6EEFF", "#6C5CE7"])
        fig.update_layout(**PLOT_LAYOUT, height=340, coloraxis_showscale=False)
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<p class="section-title">Bedroom distribution</p>', unsafe_allow_html=True)
        bd = df[df["bedrooms"] > 0].copy()
        bd["bedrooms"] = bd["bedrooms"].clip(upper=6).astype(int)
        bd_cnt = bd.groupby("bedrooms").size().reset_index(name="count")
        fig2 = px.bar(bd_cnt, x="bedrooms", y="count",
                      color_discrete_sequence=[COLORS["coral"]])
        fig2.update_layout(**PLOT_LAYOUT, height=340,
                           xaxis_title="Bedrooms", yaxis_title="Listings")
        fig2.update_traces(marker_line_width=0)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    c3, c4 = st.columns(2)
    with c3:
        st.markdown('<p class="section-title">Price by property type (top 8)</p>', unsafe_allow_html=True)
        top8 = df.groupby("property_type")["price"].mean() \
                  .sort_values(ascending=False).head(8).reset_index()
        top8.columns = ["property_type", "avg_price"]
        top8 = top8.sort_values("avg_price", ascending=True)
        fig3 = px.bar(top8, x="avg_price", y="property_type", orientation="h",
                      color="avg_price", color_continuous_scale=["#FFF8ED", "#E67E22"])
        fig3.update_layout(**PLOT_LAYOUT, height=320, coloraxis_showscale=False,
                           xaxis_title="Avg. price ($)")
        fig3.update_traces(marker_line_width=0)
        st.plotly_chart(fig3, use_container_width=True)

    with c4:
        st.markdown('<p class="section-title">Accommodates capacity</p>', unsafe_allow_html=True)
        ac = df[df["accommodates"] > 0].copy()
        ac["accommodates"] = ac["accommodates"].clip(upper=12).astype(int)
        ac_cnt = ac.groupby("accommodates").size().reset_index(name="count")
        fig4 = px.bar(ac_cnt, x="accommodates", y="count",
                      color_discrete_sequence=[COLORS["teal"]])
        fig4.update_layout(**PLOT_LAYOUT, height=320,
                           xaxis_title="Guests", yaxis_title="Listings")
        fig4.update_traces(marker_line_width=0)
        st.plotly_chart(fig4, use_container_width=True)

    # Superhost vs non-superhost price
    st.markdown("---")
    st.markdown('<p class="section-title">Superhost vs. Regular host — price comparison</p>', unsafe_allow_html=True)
    df_sh = df[df["price"] < 1000].copy()
    df_sh["host_type"] = df_sh["is_superhost"].map({True: "Superhost", False: "Regular host"})
    fig5 = px.box(df_sh, x="host_type", y="price", color="host_type",
                  color_discrete_map={"Superhost": COLORS["teal"], "Regular host": COLORS["gray"]})
    fig5.update_layout(**PLOT_LAYOUT, height=320, showlegend=False,
                       yaxis_title="Price / night ($)", xaxis_title="")
    st.plotly_chart(fig5, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 4 — REVIEWS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "⭐ Reviews":
    st.markdown('<p class="section-title">Reviews</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Review scores across all six dimensions</p>', unsafe_allow_html=True)

    df_r = df[df["score_rating"] > 0].copy()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg. overall rating",   f"{df_r['score_rating'].mean():.1f} / 100")
    k2.metric("Avg. cleanliness",      f"{df_r['score_cleanliness'].mean():.2f} / 10")
    k3.metric("Avg. communication",    f"{df_r['score_comm'].mean():.2f} / 10")
    k4.metric("Avg. value",            f"{df_r['score_value'].mean():.2f} / 10")

    st.markdown("<br>", unsafe_allow_html=True)

    # Radar chart — avg scores by room type
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">Score dimensions (avg)</p>', unsafe_allow_html=True)
        score_cols = ["score_accuracy", "score_cleanliness", "score_checkin",
                      "score_comm", "score_location", "score_value"]
        score_labels = ["Accuracy", "Cleanliness", "Check-in",
                        "Communication", "Location", "Value"]
        avgs = [df_r[c].mean() for c in score_cols]

        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=avgs + [avgs[0]],
            theta=score_labels + [score_labels[0]],
            fill="toself",
            fillcolor="rgba(9,132,227,0.12)",
            line=dict(color=COLORS["blue"], width=2),
            name="All listings",
        ))
        fig_radar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            polar=dict(
                radialaxis=dict(visible=True, range=[6, 10], gridcolor="#EBEBEB",
                                tickfont=dict(size=10, color="#999")),
                angularaxis=dict(gridcolor="#EBEBEB", tickfont=dict(size=12, color="#444")),
                bgcolor="rgba(0,0,0,0)",
            ),
            font=dict(family="DM Sans"),
            margin=dict(l=40, r=40, t=40, b=40),
            height=340,
            showlegend=False,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with c2:
        st.markdown('<p class="section-title">Rating distribution</p>', unsafe_allow_html=True)
        fig_hist = px.histogram(df_r, x="score_rating", nbins=30,
                                color_discrete_sequence=[COLORS["teal"]])
        fig_hist.update_layout(**PLOT_LAYOUT, height=340,
                               xaxis_title="Overall rating (0–100)",
                               yaxis_title="Listings", bargap=0.05)
        fig_hist.update_traces(marker_line_width=0)
        st.plotly_chart(fig_hist, use_container_width=True)

    st.markdown("---")

    # Score by country
    st.markdown('<p class="section-title">Average scores by country</p>', unsafe_allow_html=True)
    score_by_country = (df_r.groupby("country")[score_cols].mean()
                            .reset_index()
                            .rename(columns=dict(zip(score_cols, score_labels))))
    score_melt = score_by_country.melt(id_vars="country", var_name="Dimension", value_name="Score")
    fig6 = px.bar(score_melt, x="country", y="Score", color="Dimension",
                  barmode="group",
                  color_discrete_sequence=[COLORS["blue"], COLORS["teal"], COLORS["coral"],
                                           COLORS["purple"], COLORS["amber"], COLORS["red"]])
    fig6.update_layout(**PLOT_LAYOUT, height=360,
                       xaxis_title="", yaxis_title="Score (out of 10)",
                       yaxis_range=[6, 10])
    fig6.update_traces(marker_line_width=0)
    st.plotly_chart(fig6, use_container_width=True)

    # Score vs price scatter
    st.markdown("---")
    st.markdown('<p class="section-title">Price vs. overall rating</p>', unsafe_allow_html=True)
    df_sc = df_r[df_r["price"].between(10, 1000)].copy()
    fig7 = px.scatter(df_sc, x="price", y="score_rating",
                      color="room_type", opacity=0.55, size_max=6,
                      hover_name="name",
                      hover_data={"country": True, "price": True, "score_rating": True},
                      color_discrete_sequence=[COLORS["blue"], COLORS["coral"], COLORS["gray"]])
    fig7.update_layout(**PLOT_LAYOUT, height=360,
                       xaxis_title="Price / night ($)", yaxis_title="Overall rating (0–100)")
    st.plotly_chart(fig7, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════
# PAGE 5 — PRICING
# ═══════════════════════════════════════════════════════════════════════════
elif page == "💰 Pricing":
    st.markdown('<p class="section-title">Pricing Analysis</p>', unsafe_allow_html=True)
    st.markdown('<p class="section-sub">Price trends, distributions, and correlations</p>', unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Median price",      f"${df['price'].median():.0f}")
    k2.metric("Avg. price",        f"${df['price'].mean():.0f}")
    k3.metric("Budget (< $100)",   f"{(df['price'] < 100).sum():,} listings")
    k4.metric("Luxury (> $500)",   f"{(df['price'] > 500).sum():,} listings")

    st.markdown("<br>", unsafe_allow_html=True)

    # Violin by room type
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<p class="section-title">Price distribution by room type</p>', unsafe_allow_html=True)
        df_v = df[df["price"].between(5, 1000)].copy()
        fig = px.violin(df_v, x="room_type", y="price", color="room_type",
                        box=True, points=False,
                        color_discrete_sequence=[COLORS["blue"], COLORS["coral"], COLORS["gray"]])
        fig.update_layout(**PLOT_LAYOUT, height=340, showlegend=False,
                          xaxis_title="", yaxis_title="Price / night ($)")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown('<p class="section-title">Price vs. number of bedrooms</p>', unsafe_allow_html=True)
        df_bd = df[(df["bedrooms"] > 0) & (df["price"].between(5, 1000))].copy()
        df_bd["bedrooms"] = df_bd["bedrooms"].clip(upper=6).astype(int)
        avg_bd = df_bd.groupby("bedrooms")["price"].mean().reset_index()
        fig2 = px.line(avg_bd, x="bedrooms", y="price",
                       markers=True, color_discrete_sequence=[COLORS["coral"]])
        fig2.update_layout(**PLOT_LAYOUT, height=340,
                           xaxis_title="Bedrooms", yaxis_title="Avg. price ($)")
        fig2.update_traces(line_width=2.5, marker_size=8)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")

    # Price heatmap: country × room type
    st.markdown('<p class="section-title">Avg. price heatmap — country × room type</p>', unsafe_allow_html=True)
    hm = df[df["price"] < 1000].groupby(["country", "room_type"])["price"].mean().reset_index()
    hm_pivot = hm.pivot(index="country", columns="room_type", values="price")
    fig3 = px.imshow(hm_pivot, text_auto=".0f",
                     color_continuous_scale=["#EBF5FF", "#0984E3"],
                     aspect="auto")
    fig3.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#1A1A2E"),
        margin=dict(l=0, r=0, t=10, b=0),
        height=360,
        xaxis=dict(title="", tickfont=dict(size=12)),
        yaxis=dict(title="", tickfont=dict(size=12)),
        coloraxis_colorbar=dict(title="Avg. price ($)", thickness=12),
    )
    st.plotly_chart(fig3, use_container_width=True)

    # Price vs. amenities scatter
    st.markdown("---")
    st.markdown('<p class="section-title">Price vs. number of amenities</p>', unsafe_allow_html=True)
    df_am = df[df["price"].between(5, 1000)].copy()
    fig4 = px.scatter(df_am, x="amenities_count", y="price",
                      color="room_type", opacity=0.45, trendline="ols",
                      hover_name="name",
                      color_discrete_sequence=[COLORS["blue"], COLORS["coral"], COLORS["gray"]])
    fig4.update_layout(**PLOT_LAYOUT, height=360,
                       xaxis_title="Number of amenities", yaxis_title="Price / night ($)")
    st.plotly_chart(fig4, use_container_width=True)
