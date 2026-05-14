import os
import certifi
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pymongo import MongoClient

st.set_page_config(
    page_title="Airbnb Analytics Dashboard",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand palette ─────────────────────────────────────────────────────────────
RED    = "#FF5A5F"
TEAL   = "#00A699"
ORANGE = "#FC642D"
DARK   = "#484848"
GRAY   = "#767676"

SEQ_COLORS = [RED, TEAL, ORANGE, "#8B5CF6", "#F59E0B", "#10B981", "#3B82F6", DARK]


def chart_layout(**extra):
    return dict(
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(color=DARK, family="Arial, sans-serif"),
        margin=dict(l=0, r=0, t=30, b=0),
        **extra,
    )


def kpi_card(col, value: str, label: str, color: str = RED) -> None:
    col.markdown(
        f"""
        <div style="background:white;border-radius:14px;padding:22px 18px;
                    box-shadow:0 2px 12px rgba(0,0,0,.08);text-align:center;">
          <div style="height:4px;border-radius:2px;background:{color};
                      margin-bottom:14px;"></div>
          <div style="font-size:2rem;font-weight:700;color:#222;
                      line-height:1.1;">{value}</div>
          <div style="font-size:.75rem;color:{GRAY};text-transform:uppercase;
                      letter-spacing:.06em;margin-top:6px;">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── MongoDB connection ────────────────────────────────────────────────────────
MONGO_URI = st.secrets.get("MONGODB_URI", os.getenv("MONGODB_URI"))

if not MONGO_URI:
    st.error("Missing MONGODB_URI. Add it to Streamlit secrets.")
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
            "cancellation_policy": 1,
            "amenities": 1,
            "review_scores": 1,
            "host.host_is_superhost": 1,
            "address.country": 1,
            "address.market": 1,
        },
    ).limit(limit)

    rows = []
    for doc in cursor:
        rs   = doc.get("review_scores", {})
        addr = doc.get("address", {})
        host = doc.get("host", {})
        rows.append(
            {
                "name":          doc.get("name", ""),
                "property_type": doc.get("property_type", "Unknown"),
                "room_type":     doc.get("room_type", "Unknown"),
                "price":         float(str(doc.get("price", 0) or 0)),
                "bedrooms":      int(doc.get("bedrooms", 0) or 0),
                "reviews":       int(doc.get("number_of_reviews", 0) or 0),
                "rating":        rs.get("review_scores_rating"),
                "cleanliness":   rs.get("review_scores_cleanliness"),
                "location_sc":   rs.get("review_scores_location"),
                "value_sc":      rs.get("review_scores_value"),
                "is_superhost":  bool(host.get("host_is_superhost", False)),
                "amenities":     len(doc.get("amenities", [])),
                "cancellation":  doc.get("cancellation_policy", "Unknown"),
                "country":       addr.get("country", "Unknown"),
                "market":        addr.get("market", "Unknown"),
            }
        )
    return pd.DataFrame(rows)


# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading data from MongoDB…"):
    df = load_data()

if df.empty:
    st.warning("No data found in sample_airbnb.listingsAndReviews")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏠 Airbnb Analytics")
    st.markdown("---")
    st.markdown("### Filters")

    countries  = st.multiselect(
        "Country",
        sorted(df["country"].dropna().unique()),
        default=sorted(df["country"].dropna().unique()),
    )
    prop_types = st.multiselect(
        "Property Type",
        sorted(df["property_type"].dropna().unique()),
        default=sorted(df["property_type"].dropna().unique()),
    )
    price_cap   = int(df["price"].quantile(0.95)) or 500
    price_range = st.slider("Price / Night ($)", 0, price_cap, (0, price_cap))
    min_rating  = st.slider("Minimum Rating", 0, 100, 0)
    superhost   = st.checkbox("Superhosts Only")

    st.markdown("---")
    st.caption(f"Dataset: **{len(df):,}** listings")

# ── Filter ────────────────────────────────────────────────────────────────────
filt = df.copy()
if countries:
    filt = filt[filt["country"].isin(countries)]
if prop_types:
    filt = filt[filt["property_type"].isin(prop_types)]
filt = filt[(filt["price"] >= price_range[0]) & (filt["price"] <= price_range[1])]
filt = filt[filt["rating"].isna() | (filt["rating"] >= min_rating)]
if superhost:
    filt = filt[filt["is_superhost"]]

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("# 🏠 Airbnb Analytics Dashboard")
st.caption(
    f"Showing **{len(filt):,}** of {len(df):,} listings · MongoDB `sample_airbnb`"
)

# ── KPI cards ─────────────────────────────────────────────────────────────────
avg_price  = filt.loc[filt["price"] > 0, "price"].mean()
avg_rating = filt["rating"].dropna().mean()
sup_pct    = filt["is_superhost"].mean() * 100

k1, k2, k3, k4, k5 = st.columns(5)
kpi_card(k1, f"{len(filt):,}",                                        "Total Listings",    RED)
kpi_card(k2, f"${avg_price:.0f}" if pd.notna(avg_price) else "—",     "Avg Price / Night", ORANGE)
kpi_card(k3, f"{avg_rating:.1f}" if pd.notna(avg_rating) else "—",    "Avg Rating / 100",  TEAL)
kpi_card(k4, f"{sup_pct:.1f}%" if pd.notna(sup_pct) else "—",          "Superhost Rate",    "#8B5CF6")
kpi_card(k5, str(filt["country"].nunique()),                           "Countries",         DARK)

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🌍 Overview", "💰 Price Analysis", "⭐ Ratings & Quality", "📍 Markets", "📋 Data Explorer"]
)

# ════════════════════════════════════════════════════════════════════════
# Tab 1 — Overview
# ════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Global Listings Distribution")
    map_df = filt.groupby("country").size().reset_index(name="Listings")
    fig = px.choropleth(
        map_df,
        locations="country",
        locationmode="country names",
        color="Listings",
        color_continuous_scale="Reds",
        labels={"Listings": "Listings"},
    )
    fig.update_layout(
        **chart_layout(margin=dict(l=0, r=0, t=10, b=0)),
        geo=dict(
            showframe=False,
            showcoastlines=True,
            projection_type="natural earth",
            bgcolor="white",
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Property Type Mix")
        top8 = filt["property_type"].value_counts().head(8)
        fig = px.pie(
            values=top8.values,
            names=top8.index,
            hole=0.45,
            color_discrete_sequence=SEQ_COLORS,
        )
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(**chart_layout(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Room Type Breakdown")
        room_df = filt["room_type"].value_counts().reset_index()
        room_df.columns = ["Room Type", "Listings"]
        fig = px.bar(
            room_df,
            x="Room Type",
            y="Listings",
            color="Room Type",
            color_discrete_sequence=SEQ_COLORS,
            text="Listings",
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(**chart_layout(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# Tab 2 — Price Analysis
# ════════════════════════════════════════════════════════════════════════
with tab2:
    df_price = filt[filt["price"] > 0]

    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.subheader("Price Distribution")
        fig = px.histogram(
            df_price,
            x="price",
            nbins=60,
            color_discrete_sequence=[RED],
            labels={"price": "Price ($/night)"},
        )
        fig.update_layout(**chart_layout())
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Price by Room Type")
        fig = px.box(
            df_price,
            x="room_type",
            y="price",
            color="room_type",
            color_discrete_sequence=SEQ_COLORS,
            labels={"price": "Price ($/night)", "room_type": ""},
        )
        fig.update_layout(**chart_layout(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Median Price by Country (Map)")
    price_map = (
        df_price.groupby("country")["price"]
        .median()
        .reset_index()
    )
    price_map.columns = ["country", "Median Price ($/night)"]
    fig = px.choropleth(
        price_map,
        locations="country",
        locationmode="country names",
        color="Median Price ($/night)",
        color_continuous_scale="Oranges",
    )
    fig.update_layout(
        **chart_layout(margin=dict(l=0, r=0, t=10, b=0)),
        geo=dict(showframe=False, showcoastlines=True, projection_type="natural earth", bgcolor="white"),
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Median Price by Property Type")
        med = (
            df_price.groupby("property_type")["price"]
            .median()
            .sort_values(ascending=False)
            .reset_index()
        )
        med.columns = ["Property Type", "Median Price"]
        fig = px.bar(
            med,
            x="Median Price",
            y="Property Type",
            orientation="h",
            color="Median Price",
            color_continuous_scale="Reds",
        )
        fig.update_layout(**chart_layout(), coloraxis_showscale=False, yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Price vs Bedrooms")
        fig = px.box(
            df_price[df_price["bedrooms"] <= 6],
            x="bedrooms",
            y="price",
            color_discrete_sequence=[TEAL],
            labels={"price": "Price ($/night)", "bedrooms": "Bedrooms"},
        )
        fig.update_layout(**chart_layout())
        st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# Tab 3 — Ratings & Quality
# ════════════════════════════════════════════════════════════════════════
with tab3:
    df_rated = filt[filt["rating"].notna()]

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Rating Distribution")
        fig = px.histogram(
            df_rated,
            x="rating",
            nbins=40,
            color_discrete_sequence=[TEAL],
            labels={"rating": "Rating (out of 100)"},
        )
        fig.update_layout(**chart_layout())
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Rating vs Price")
        df_sc_base = df_rated[df_rated["price"] > 0]
        df_sc = df_sc_base.sample(min(800, len(df_sc_base)), random_state=42)
        fig = px.scatter(
            df_sc,
            x="price",
            y="rating",
            color="room_type",
            size="reviews",
            size_max=20,
            hover_data=["name", "country", "market", "property_type"],
            opacity=0.7,
            color_discrete_sequence=SEQ_COLORS,
            labels={
                "price": "Price ($/night)",
                "rating": "Rating (/ 100)",
                "room_type": "Room Type",
            },
        )
        fig.update_layout(**chart_layout())
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Superhost vs Regular Host — Quality Comparison")

    col_a, col_b = st.columns([2, 3])
    with col_a:
        summary = (
            filt.groupby("is_superhost")[
                ["rating", "cleanliness", "location_sc", "value_sc", "reviews"]
            ]
            .median()
            .rename(index={True: "⭐ Superhost", False: "Regular Host"})
            .round(1)
        )
        summary.columns = ["Rating", "Cleanliness", "Location", "Value", "Reviews"]
        st.dataframe(summary, use_container_width=True)

    with col_b:
        cats = ["Rating", "Cleanliness (×10)", "Location (×10)", "Value (×10)"]

        def _m(series) -> float:
            v = series.dropna().median()
            return float(v) if pd.notna(v) else 0.0

        fig_r = go.Figure()
        for is_super, label, color in [
            (True,  "Superhost",    RED),
            (False, "Regular Host", TEAL),
        ]:
            sub  = filt[filt["is_superhost"] == is_super]
            vals = [
                _m(sub["rating"]),
                _m(sub["cleanliness"]) * 10,
                _m(sub["location_sc"]) * 10,
                _m(sub["value_sc"])    * 10,
            ]
            fig_r.add_trace(
                go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=cats + [cats[0]],
                    fill="toself",
                    name=label,
                    line_color=color,
                    fillcolor=color,
                    opacity=0.3,
                )
            )
        fig_r.update_layout(
            polar=dict(
                bgcolor="#f9f9f9",
                radialaxis=dict(visible=True, range=[0, 100]),
            ),
            paper_bgcolor="white",
            margin=dict(l=20, r=20, t=20, b=30),
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig_r, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# Tab 4 — Markets
# ════════════════════════════════════════════════════════════════════════
with tab4:
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Top 15 Markets by Listings")
        top_m = filt["market"].value_counts().head(15).reset_index()
        top_m.columns = ["Market", "Listings"]
        fig = px.bar(
            top_m,
            x="Listings",
            y="Market",
            orientation="h",
            color="Listings",
            color_continuous_scale="Blues",
        )
        fig.update_layout(
            **chart_layout(),
            coloraxis_showscale=False,
            yaxis=dict(autorange="reversed", title=""),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("Cancellation Policy Breakdown")
        cancel_df = filt["cancellation"].value_counts().reset_index()
        cancel_df.columns = ["Policy", "Listings"]
        fig = px.pie(
            cancel_df,
            values="Listings",
            names="Policy",
            hole=0.45,
            color_discrete_sequence=SEQ_COLORS,
        )
        fig.update_traces(textposition="outside", textinfo="percent+label")
        fig.update_layout(**chart_layout(), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Median Price by Market — Top 20")
    market_price = (
        filt[filt["price"] > 0]
        .groupby("market")["price"]
        .agg(["median", "count"])
        .rename(columns={"median": "Median Price ($/night)", "count": "Listings"})
        .query("Listings >= 5")
        .sort_values("Median Price ($/night)", ascending=False)
        .head(20)
        .reset_index()
    )
    fig = px.bar(
        market_price,
        x="Median Price ($/night)",
        y="Market",
        orientation="h",
        color="Median Price ($/night)",
        color_continuous_scale="Oranges",
        hover_data=["Listings"],
    )
    fig.update_layout(
        **chart_layout(),
        coloraxis_showscale=False,
        yaxis=dict(autorange="reversed", title=""),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Amenity Count Distribution")
    fig = px.histogram(
        filt,
        x="amenities",
        nbins=30,
        color_discrete_sequence=[ORANGE],
        labels={"amenities": "Number of Amenities"},
    )
    fig.update_layout(**chart_layout())
    st.plotly_chart(fig, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════
# Tab 5 — Data Explorer
# ════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("Listings Explorer")

    search = st.text_input(
        "Search by name, country, or market",
        placeholder="e.g. Cozy Apartment, Hong Kong…",
    )
    display = filt.copy()
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
                "name", "country", "market", "property_type", "room_type",
                "price", "bedrooms", "rating", "cleanliness", "location_sc",
                "reviews", "is_superhost", "amenities", "cancellation",
            ]
        ]
        .rename(
            columns={
                "property_type": "type",
                "room_type":     "room",
                "location_sc":   "location",
                "reviews":       "# reviews",
                "is_superhost":  "superhost",
                "cancellation":  "cancel policy",
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
