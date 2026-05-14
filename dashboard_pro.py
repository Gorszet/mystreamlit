import os
import certifi
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pymongo import MongoClient

st.set_page_config(
    page_title="Airbnb Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Palette ───────────────────────────────────────────────────────────────────
BG     = "#0A0A0F"
SURF   = "#12121A"
CARD   = "#1A1A28"
BORDER = "#2A2A3E"
TEXT   = "#F1F5F9"
MUTED  = "#64748B"
GREEN  = "#10B981"
AMBER  = "#F59E0B"
RED    = "#EF4444"
BLUE   = "#3B82F6"
PURPLE = "#8B5CF6"
CAT    = [BLUE, GREEN, PURPLE, AMBER, RED, "#06B6D4", "#EC4899", "#F97316"]


def _dark(**kw):
    base = dict(
        plot_bgcolor=SURF,
        paper_bgcolor=BG,
        font=dict(color=MUTED, family="system-ui,-apple-system,sans-serif", size=11),
        margin=dict(l=0, r=0, t=30, b=0),
        hoverlabel=dict(bgcolor=CARD, bordercolor=BORDER, font_color=TEXT, font_size=12),
    )
    base.update(kw)
    return base


def _ax(**kw):
    return dict(gridcolor=BORDER, zeroline=False, linecolor=BORDER,
                tickcolor=MUTED, color=MUTED, **kw)


def traffic_kpi(col, value, label, status="info"):
    c = {"good": GREEN, "warn": AMBER, "bad": RED, "info": BLUE, "purple": PURPLE}.get(status, BLUE)
    col.markdown(
        f"""<div style="background:{c}11;border:1px solid {c}33;border-radius:14px;
                       padding:20px 16px;text-align:center">
<p style="margin:0;font-size:.63rem;color:{MUTED};text-transform:uppercase;letter-spacing:.1em">{label}</p>
<p style="margin:10px 0 0;font-size:2.1rem;font-weight:800;color:{c};line-height:1">{value}</p>
</div>""",
        unsafe_allow_html=True,
    )


def insight(text, color=BLUE):
    st.markdown(
        f"""<div style="background:{color}11;border-left:3px solid {color};
                       border-radius:0 8px 8px 0;padding:12px 16px;margin:16px 0 4px">
<span style="color:{color};font-size:.75rem;font-weight:700">💡 Intelligence Insight</span>
<p style="color:{MUTED};font-size:.82rem;margin:5px 0 0;line-height:1.55">{text}</p>
</div>""",
        unsafe_allow_html=True,
    )


def section(title):
    st.markdown(
        f'<p style="color:{TEXT};font-weight:600;font-size:.95rem;'
        f'margin:16px 0 8px;padding-bottom:6px;border-bottom:1px solid {BORDER}">{title}</p>',
        unsafe_allow_html=True,
    )


def _m(series) -> float:
    v = series.dropna().median()
    return float(v) if pd.notna(v) else 0.0


# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
.stApp {{ background-color:{BG}; }}
section[data-testid="stSidebar"] {{ background-color:{SURF};border-right:1px solid {BORDER}; }}
.stTabs [data-baseweb="tab-list"] {{ background-color:{CARD};border-radius:10px;gap:2px;padding:4px; }}
.stTabs [data-baseweb="tab"] {{ border-radius:8px;color:{MUTED};font-weight:500;padding:6px 18px; }}
.stTabs [data-baseweb="tab"][aria-selected="true"] {{ background-color:{BLUE}22;color:{TEXT}; }}
h1,h2,h3,h4,h5 {{ color:{TEXT} !important; }}
.stCaption, label {{ color:{MUTED} !important; }}
div[data-testid="stDecoration"] {{ display:none; }}
</style>
""", unsafe_allow_html=True)

# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGO_URI = st.secrets.get("MONGODB_URI", os.getenv("MONGODB_URI"))
if not MONGO_URI:
    st.error("Missing MONGODB_URI.")
    st.stop()


@st.cache_resource
def get_client():
    return MongoClient(MONGO_URI, tlsCAFile=certifi.where())


@st.cache_data(ttl=600)
def load_data(limit: int = 5000) -> pd.DataFrame:
    col = get_client()["sample_airbnb"]["listingsAndReviews"]
    cursor = col.find({}, {
        "name": 1, "property_type": 1, "room_type": 1,
        "price": 1, "cleaning_fee": 1,
        "bedrooms": 1, "accommodates": 1,
        "number_of_reviews": 1, "minimum_nights": 1,
        "cancellation_policy": 1, "amenities": 1,
        "review_scores": 1,
        "host.host_is_superhost": 1, "host.host_response_time": 1,
        "address.country": 1, "address.market": 1,
    }).limit(limit)

    rows = []
    for doc in cursor:
        rs   = doc.get("review_scores") or {}
        addr = doc.get("address") or {}
        host = doc.get("host") or {}
        price  = float(str(doc.get("price", 0) or 0))
        c_fee  = float(str(doc.get("cleaning_fee", 0) or 0))
        rows.append({
            "name":          doc.get("name", ""),
            "property_type": doc.get("property_type", "Unknown"),
            "room_type":     doc.get("room_type", "Unknown"),
            "price":         price,
            "cleaning_fee":  c_fee,
            "clean_pct":     round(c_fee / price * 100, 1) if price > 0 else 0,
            "bedrooms":      int(doc.get("bedrooms", 0) or 0),
            "accommodates":  int(doc.get("accommodates", 0) or 0),
            "reviews":       int(doc.get("number_of_reviews", 0) or 0),
            "min_nights":    int(doc.get("minimum_nights", 1) or 1),
            "cancellation":  doc.get("cancellation_policy", "Unknown"),
            "amenities":     len(doc.get("amenities") or []),
            "rating":        rs.get("review_scores_rating"),
            "cleanliness":   rs.get("review_scores_cleanliness"),
            "location_sc":   rs.get("review_scores_location"),
            "value_sc":      rs.get("review_scores_value"),
            "communication": rs.get("review_scores_communication"),
            "checkin_sc":    rs.get("review_scores_checkin"),
            "is_superhost":  bool(host.get("host_is_superhost", False)),
            "resp_time":     host.get("host_response_time") or "Unknown",
            "country":       addr.get("country", "Unknown"),
            "market":        addr.get("market", "Unknown"),
        })
    return pd.DataFrame(rows)


# ── Load ──────────────────────────────────────────────────────────────────────
with st.spinner("Connecting to MongoDB…"):
    df = load_data()

if df.empty:
    st.warning("No data found.")
    st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"### 📊 Airbnb Intelligence")
    st.markdown(f'<p style="color:{MUTED};font-size:.78rem;margin-top:-8px">Predictive Analytics Dashboard</p>', unsafe_allow_html=True)
    st.divider()

    countries  = st.multiselect("Country", sorted(df["country"].dropna().unique()), default=sorted(df["country"].dropna().unique()))
    room_types = st.multiselect("Room Type", sorted(df["room_type"].dropna().unique()), default=sorted(df["room_type"].dropna().unique()))
    price_cap  = int(df["price"].max()) or 500
    price_rng  = st.slider("Price Range ($/night)", 0, price_cap, (0, price_cap))
    min_rating = st.slider("Min Rating", 0, 100, 0)
    superhost_only = st.checkbox("Superhosts Only")

    st.divider()
    st.caption(f"Dataset: {len(df):,} listings")

# ── Filter ────────────────────────────────────────────────────────────────────
f = df.copy()
if countries:      f = f[f["country"].isin(countries)]
if room_types:     f = f[f["room_type"].isin(room_types)]
f = f[(f["price"] >= price_rng[0]) & (f["price"] <= price_rng[1])]
f = f[f["rating"].isna() | (f["rating"] >= min_rating)]
if superhost_only: f = f[f["is_superhost"]]

# ── Header ────────────────────────────────────────────────────────────────────
hc, ht = st.columns([5, 1])
hc.markdown("# 📊 Airbnb Intelligence Dashboard")
hc.caption(f"{len(f):,} listings · {f['country'].nunique()} countries · {f['market'].nunique()} markets")
ht.markdown(
    f'<div style="text-align:right;padding-top:20px">'
    f'<span style="background:{GREEN}22;color:{GREEN};padding:4px 14px;'
    f'border-radius:20px;font-size:.72rem;font-weight:600">● LIVE</span></div>',
    unsafe_allow_html=True,
)
st.markdown(f'<hr style="border:none;border-top:1px solid {BORDER};margin:8px 0 20px">', unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
avg_p   = f.loc[f["price"] > 0, "price"].mean()
avg_r   = f["rating"].dropna().mean()
sup_pct = f["is_superhost"].mean() * 100
avg_rev = f["reviews"].mean()

k1, k2, k3, k4, k5 = st.columns(5)
traffic_kpi(k1, f"{len(f):,}",                               "Total Listings",     "info")
traffic_kpi(k2, f"${avg_p:.0f}"  if pd.notna(avg_p) else "—", "Avg Price / Night",  "info")
traffic_kpi(k3, f"{avg_r:.1f}"   if pd.notna(avg_r) else "—", "Avg Rating / 100",
            "good" if pd.notna(avg_r) and avg_r >= 90 else "warn" if pd.notna(avg_r) and avg_r >= 80 else "bad")
traffic_kpi(k4, f"{sup_pct:.1f}%",                            "Superhost Rate",
            "good" if sup_pct >= 25 else "warn" if sup_pct >= 15 else "bad")
traffic_kpi(k5, f"{avg_rev:.0f}", "Avg Reviews / Listing",
            "good" if avg_rev >= 20 else "warn" if avg_rev >= 10 else "bad")

st.markdown("<br>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
t1, t2, t3, t4, t5 = st.tabs([
    "🎯  Executive", "💰  Pricing", "📈  Demand", "🗺️  Location", "⭐  Quality",
])

# ════════════════════════════════════════════════════════════════════════
# Tab 1 — Executive
# ════════════════════════════════════════════════════════════════════════
with t1:
    col_a, col_b = st.columns([3, 2])

    with col_a:
        section("Market Performance Matrix")
        mkt = (
            f.groupby("market")
            .agg(
                Listings=("name", "count"),
                Med_Price=("price", "median"),
                Avg_Rating=("rating", "median"),
                Avg_Reviews=("reviews", "mean"),
                Superhost_Pct=("is_superhost", "mean"),
            )
            .round(1)
            .sort_values("Listings", ascending=False)
            .head(10)
        )
        mkt["Superhost_Pct"] = (mkt["Superhost_Pct"] * 100).round(1)
        mkt.columns = ["Listings", "Med. Price ($)", "Avg Rating", "Avg Reviews", "Superhost %"]
        st.dataframe(
            mkt.style
               .background_gradient(cmap="Blues",  subset=["Listings"])
               .background_gradient(cmap="Greens", subset=["Avg Rating"])
               .format({"Med. Price ($)": "${:.0f}", "Superhost %": "{:.1f}%"}),
            use_container_width=True,
            height=370,
        )

    with col_b:
        section("Host Response Time Distribution")
        rt = f[f["resp_time"] != "Unknown"]["resp_time"].value_counts().reset_index()
        rt.columns = ["Response Time", "Listings"]
        fig = px.bar(
            rt, x="Listings", y="Response Time", orientation="h",
            color="Response Time", color_discrete_sequence=CAT, text="Listings",
        )
        fig.update_traces(textposition="outside", textfont_color=MUTED)
        fig.update_layout(**_dark(), showlegend=False,
                          xaxis=_ax(showgrid=False), yaxis=_ax(showgrid=False, title=""))
        st.plotly_chart(fig, use_container_width=True)

    top_market = f.groupby("market").size().idxmax() if len(f) else "N/A"
    insight(
        f"<b>{top_market}</b> leads in listing volume. "
        f"Superhost rate is <b>{sup_pct:.1f}%</b> — "
        f"{'healthy portfolio signal.' if sup_pct >= 25 else 'below 25% threshold; incentivising superhost certification would lift trust scores.'}"
        f" Avg rating <b>{avg_r:.1f}/100</b>: "
        f"{'strong performance.' if pd.notna(avg_r) and avg_r >= 90 else 'improvement opportunity — target bottom-quartile hosts for coaching.'}",
        color=BLUE,
    )

# ════════════════════════════════════════════════════════════════════════
# Tab 2 — Pricing
# ════════════════════════════════════════════════════════════════════════
with t2:
    p = f[f["price"] > 0]

    col_a, col_b = st.columns([3, 2])
    with col_a:
        section("Price Distribution by Room Type")
        fig = px.box(
            p, x="room_type", y="price", color="room_type",
            color_discrete_sequence=CAT,
            labels={"price": "$/night", "room_type": ""},
        )
        fig.update_layout(**_dark(), showlegend=False, xaxis=_ax(), yaxis=_ax())
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section("Cancellation Policy vs Avg Reviews")
        cancel = (
            f.groupby("cancellation")
            .agg(listings=("name", "count"), avg_reviews=("reviews", "mean"))
            .reset_index()
        )
        cancel.columns = ["Policy", "Listings", "Avg Reviews"]
        cancel = cancel[cancel["Policy"] != "Unknown"].sort_values("Avg Reviews")
        fig = px.bar(
            cancel, x="Avg Reviews", y="Policy", orientation="h",
            color="Avg Reviews", color_continuous_scale="Blues", text="Listings",
        )
        fig.update_traces(texttemplate="%{text} listings", textposition="outside", textfont_color=MUTED)
        fig.update_layout(**_dark(), coloraxis_showscale=False,
                          xaxis=_ax(), yaxis=_ax(showgrid=False, title=""))
        st.plotly_chart(fig, use_container_width=True)

    section("Cleaning Fee Burden by Market (Top 15)")
    cf = (
        p[p["cleaning_fee"] > 0]
        .groupby("market")["clean_pct"]
        .mean()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
    )
    cf.columns = ["Market", "Cleaning Fee (% of Nightly Price)"]
    fig = px.bar(
        cf, x="Market", y="Cleaning Fee (% of Nightly Price)",
        color="Cleaning Fee (% of Nightly Price)", color_continuous_scale="Reds",
        text="Cleaning Fee (% of Nightly Price)",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside", textfont_color=MUTED)
    fig.update_layout(**_dark(), coloraxis_showscale=False, xaxis=_ax(), yaxis=_ax())
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        section("Price vs Rating — Revenue Intelligence")
        sc = p[p["rating"].notna()].copy()
        sc["bubble"] = sc["reviews"].clip(lower=1)
        sc_s = sc.sample(min(600, len(sc)), random_state=42)
        fig = px.scatter(
            sc_s, x="price", y="rating",
            color="room_type", size="bubble", size_max=16,
            hover_name="name",
            hover_data={"market": True, "property_type": True, "reviews": True,
                        "price": ":.0f", "rating": ":.1f", "bubble": False},
            opacity=0.7, color_discrete_sequence=CAT,
            labels={"price": "$/night", "rating": "Rating /100", "room_type": "Room", "bubble": "Reviews"},
        )
        fig.update_layout(**_dark(), xaxis=_ax(), yaxis=_ax(),
                          legend=dict(bgcolor=CARD, bordercolor=BORDER, font_color=MUTED,
                                      orientation="h", y=-0.22, title=""))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section("Median Price by Property Type (Top 10)")
        pt = (
            p.groupby("property_type")["price"]
            .median()
            .sort_values(ascending=True)
            .tail(10)
            .reset_index()
        )
        pt.columns = ["Property Type", "Median Price ($)"]
        fig = px.bar(
            pt, x="Median Price ($)", y="Property Type", orientation="h",
            color="Median Price ($)", color_continuous_scale="Blues",
            text="Median Price ($)",
        )
        fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside", textfont_color=MUTED)
        fig.update_layout(**_dark(), coloraxis_showscale=False,
                          xaxis=_ax(), yaxis=_ax(showgrid=False, title=""))
        st.plotly_chart(fig, use_container_width=True)

    top_fee_mkt = cf.iloc[0]["Market"] if len(cf) else "N/A"
    top_fee_val = cf.iloc[0]["Cleaning Fee (% of Nightly Price)"] if len(cf) else 0
    insight(
        f"<b>{top_fee_mkt}</b> has the highest cleaning fee burden at <b>{top_fee_val:.1f}%</b> of nightly rate. "
        f"Hidden fees increase booking abandonment — consider flat-fee pricing strategies to improve conversion. "
        f"Flexible cancellation policies correlate with higher review velocity, suggesting lower booking hesitancy.",
        color=AMBER,
    )

# ════════════════════════════════════════════════════════════════════════
# Tab 3 — Demand Intelligence
# ════════════════════════════════════════════════════════════════════════
with t3:
    col_a, col_b = st.columns(2)

    with col_a:
        section("Review Velocity by Market — Demand Signal (Top 12)")
        rv = (
            f.groupby("market")["reviews"]
            .mean()
            .sort_values(ascending=False)
            .head(12)
            .reset_index()
        )
        rv.columns = ["Market", "Avg Reviews / Listing"]
        fig = px.bar(
            rv, x="Avg Reviews / Listing", y="Market", orientation="h",
            color="Avg Reviews / Listing", color_continuous_scale="Greens",
            text="Avg Reviews / Listing",
        )
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside", textfont_color=MUTED)
        fig.update_layout(**_dark(), coloraxis_showscale=False,
                          yaxis=_ax(autorange="reversed", showgrid=False, title=""),
                          xaxis=_ax())
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section("Minimum Nights Required — Booking Commitment Distribution")
        mn = f[f["min_nights"].between(1, 30)]
        fig = px.histogram(
            mn, x="min_nights", nbins=30,
            color_discrete_sequence=[PURPLE],
            labels={"min_nights": "Minimum Nights Required"},
        )
        fig.update_layout(**_dark(), xaxis=_ax(), yaxis=_ax(showgrid=False))
        st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        section("Accommodation Capacity vs Nightly Price")
        cap = f[f["price"] > 0][f["accommodates"].between(1, 10)]
        fig = px.box(
            cap, x="accommodates", y="price",
            color_discrete_sequence=[BLUE],
            labels={"price": "$/night", "accommodates": "Max Guests"},
        )
        fig.update_layout(**_dark(), xaxis=_ax(), yaxis=_ax())
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section("Amenity Count vs Guest Rating")
        am = f[f["rating"].notna()].sample(min(800, len(f[f["rating"].notna()])), random_state=42)
        fig = px.scatter(
            am, x="amenities", y="rating",
            color="room_type", opacity=0.55,
            color_discrete_sequence=CAT,
            labels={"amenities": "Number of Amenities", "rating": "Rating /100", "room_type": "Room"},
        )
        fig.update_layout(**_dark(), xaxis=_ax(), yaxis=_ax(),
                          legend=dict(bgcolor=CARD, bordercolor=BORDER, font_color=MUTED,
                                      orientation="h", y=-0.22, title=""))
        st.plotly_chart(fig, use_container_width=True)

    top_demand = rv.iloc[0]["Market"] if len(rv) else "N/A"
    insight(
        f"<b>{top_demand}</b> shows the highest review velocity — a strong proxy for booking demand. "
        f"Listings requiring 1–3 minimum nights have the broadest appeal. "
        f"Hosts offering more amenities tend to receive higher ratings — "
        f"amenity investment has measurable impact on guest satisfaction scores.",
        color=GREEN,
    )

# ════════════════════════════════════════════════════════════════════════
# Tab 4 — Location Intelligence
# ════════════════════════════════════════════════════════════════════════
with t4:
    col_a, col_b = st.columns(2)
    with col_a:
        section("Listing Density by Country")
        map1 = f.groupby("country").size().reset_index(name="Listings")
        fig = px.choropleth(
            map1, locations="country", locationmode="country names",
            color="Listings", color_continuous_scale="Blues",
        )
        fig.update_layout(
            **_dark(margin=dict(l=0, r=0, t=0, b=0)),
            geo=dict(showframe=False, showcoastlines=True, bgcolor=BG,
                     landcolor=SURF, coastlinecolor=BORDER, projection_type="natural earth"),
        )
        fig.update_coloraxes(colorbar=dict(thickness=8, len=0.45, tickcolor=MUTED, tickfont_color=MUTED))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section("Median Price by Country")
        map2 = f[f["price"] > 0].groupby("country")["price"].median().reset_index()
        map2.columns = ["country", "Median ($/night)"]
        fig = px.choropleth(
            map2, locations="country", locationmode="country names",
            color="Median ($/night)", color_continuous_scale="Oranges",
        )
        fig.update_layout(
            **_dark(margin=dict(l=0, r=0, t=0, b=0)),
            geo=dict(showframe=False, showcoastlines=True, bgcolor=BG,
                     landcolor=SURF, coastlinecolor=BORDER, projection_type="natural earth"),
        )
        fig.update_coloraxes(colorbar=dict(thickness=8, len=0.45, tickcolor=MUTED, tickfont_color=MUTED))
        st.plotly_chart(fig, use_container_width=True)

    section("Market Positioning — Blue Ocean Analysis")
    mkt_pos = (
        f[f["price"] > 0]
        .groupby("market")
        .agg(
            avg_price=("price", "median"),
            avg_rating=("rating", "median"),
            listings=("name", "count"),
            avg_reviews=("reviews", "mean"),
        )
        .dropna(subset=["avg_rating"])
        .reset_index()
    )
    mkt_pos = mkt_pos[mkt_pos["listings"] >= 5]

    med_price  = mkt_pos["avg_price"].median()
    med_rating = mkt_pos["avg_rating"].median()

    def _quadrant(row):
        hi_r = row["avg_rating"] >= med_rating
        lo_p = row["avg_price"]  <= med_price
        if lo_p and hi_r:     return "🔵 Blue Ocean"
        if not lo_p and hi_r: return "💎 Premium"
        if lo_p and not hi_r: return "⚠️ Struggling"
        return "💰 Overpriced"

    mkt_pos["Segment"] = mkt_pos.apply(_quadrant, axis=1)
    q_colors = {"🔵 Blue Ocean": BLUE, "💎 Premium": PURPLE, "⚠️ Struggling": RED, "💰 Overpriced": AMBER}

    fig = px.scatter(
        mkt_pos, x="avg_price", y="avg_rating",
        size="listings", size_max=45,
        color="Segment", color_discrete_map=q_colors,
        hover_name="market",
        hover_data={"listings": True, "avg_reviews": ":.1f",
                    "avg_price": ":.0f", "avg_rating": ":.1f", "Segment": False},
        labels={"avg_price": "Median Price ($/night)", "avg_rating": "Avg Rating /100"},
    )
    fig.add_hline(y=med_rating, line_dash="dash", line_color=BORDER, opacity=0.8)
    fig.add_vline(x=med_price,  line_dash="dash", line_color=BORDER, opacity=0.8)

    for label, color, xanchor, x, y in [
        ("🔵 High Quality · Affordable", BLUE,   "left",  mkt_pos["avg_price"].min(), mkt_pos["avg_rating"].max()),
        ("💎 Premium",                   PURPLE, "right", mkt_pos["avg_price"].max(), mkt_pos["avg_rating"].max()),
        ("⚠️ Needs Improvement",         RED,    "left",  mkt_pos["avg_price"].min(), mkt_pos["avg_rating"].min()),
        ("💰 Overpriced",                AMBER,  "right", mkt_pos["avg_price"].max(), mkt_pos["avg_rating"].min()),
    ]:
        fig.add_annotation(x=x, y=y, text=label, showarrow=False,
                           font_color=color, font_size=10, xanchor=xanchor)

    fig.update_layout(**_dark(margin=dict(l=0, r=0, t=10, b=40)),
                      xaxis=_ax(), yaxis=_ax(),
                      legend=dict(bgcolor=CARD, bordercolor=BORDER, font_color=MUTED,
                                  orientation="h", y=-0.12, title=""))
    st.plotly_chart(fig, use_container_width=True)

    blue = mkt_pos[mkt_pos["Segment"] == "🔵 Blue Ocean"]["market"].tolist()
    insight(
        f"Blue Ocean markets — high satisfaction, accessible pricing: "
        f"<b>{', '.join(blue[:4]) if blue else 'None with current filters'}</b>. "
        f"These represent the optimal entry point for new hosts or portfolio expansion "
        f"— strong guest demand without premium competition.",
        color=BLUE,
    )

# ════════════════════════════════════════════════════════════════════════
# Tab 5 — Quality & Experience
# ════════════════════════════════════════════════════════════════════════
with t5:
    col_a, col_b = st.columns([3, 2])

    with col_a:
        section("Superhost vs Regular Host — Quality Radar")
        dim_keys   = ["rating", "cleanliness", "location_sc", "value_sc", "communication", "checkin_sc"]
        dim_labels = ["Rating", "Cleanliness", "Location", "Value", "Communication", "Check-in"]
        fig = go.Figure()
        for is_s, label, color in [(True, "Superhost", GREEN), (False, "Regular Host", RED)]:
            sub  = f[f["is_superhost"] == is_s]
            vals = [_m(sub["rating"])]  + [_m(sub[k]) * 10 for k in dim_keys[1:]]
            fig.add_trace(go.Scatterpolar(
                r=vals + [vals[0]], theta=dim_labels + [dim_labels[0]],
                fill="toself", name=label,
                line_color=color, fillcolor=color, opacity=0.2, line_width=2,
            ))
        fig.update_layout(
            polar=dict(
                bgcolor=CARD,
                radialaxis=dict(visible=True, range=[0, 100], gridcolor=BORDER,
                                color=MUTED, tickfont_color=MUTED),
                angularaxis=dict(gridcolor=BORDER, color=MUTED),
            ),
            paper_bgcolor=BG,
            font=dict(color=MUTED, family="system-ui,-apple-system,sans-serif"),
            margin=dict(l=30, r=30, t=30, b=40),
            legend=dict(bgcolor=CARD, bordercolor=BORDER, font_color=MUTED,
                        orientation="h", y=-0.1),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        section("Score Components — Traffic Light View")
        scores = [f[k].dropna().mean() for k in dim_keys]
        scores_100 = [s * 10 if s and s <= 10 else s for s in scores]
        bar_colors = [GREEN if s >= 95 else AMBER if s >= 85 else RED for s in scores_100]

        fig = go.Figure(go.Bar(
            x=scores_100, y=dim_labels,
            orientation="h",
            marker_color=bar_colors,
            text=[f"{v:.1f}" if v else "N/A" for v in scores_100],
            textposition="outside",
            textfont_color=MUTED,
        ))
        fig.update_layout(**_dark(), showlegend=False,
                          xaxis=_ax(range=[0, 108]),
                          yaxis=_ax(showgrid=False, title=""))
        st.plotly_chart(fig, use_container_width=True)

    section("Score Heatmap — Top 15 Markets × Quality Dimensions")
    hm_raw = f.groupby("market")[["rating", "cleanliness", "location_sc", "value_sc"]].mean()
    hm_scaled = hm_raw.copy()
    for c in ["cleanliness", "location_sc", "value_sc"]:
        hm_scaled[c] = hm_scaled[c] * 10
    hm_scaled.columns = ["Rating", "Cleanliness", "Location", "Value"]
    hm_top = hm_scaled.dropna().sort_values("Rating", ascending=False).head(15)

    fig = px.imshow(
        hm_top,
        color_continuous_scale=[[0, "#EF4444"], [0.5, "#F59E0B"], [1, "#10B981"]],
        aspect="auto",
        text_auto=".1f",
        zmin=80, zmax=100,
    )
    fig.update_layout(**_dark(margin=dict(l=0, r=0, t=10, b=0)),
                      coloraxis_showscale=False,
                      xaxis=_ax(showgrid=False, tickfont_color=TEXT),
                      yaxis=_ax(showgrid=False, tickfont_color=MUTED))
    fig.update_traces(textfont_color=TEXT, textfont_size=11)
    st.plotly_chart(fig, use_container_width=True)

    worst_idx = scores_100.index(min(s for s in scores_100 if s))
    worst_dim = dim_labels[worst_idx]
    worst_val = scores_100[worst_idx]
    best_idx  = scores_100.index(max(s for s in scores_100 if s))
    best_dim  = dim_labels[best_idx]

    insight(
        f"Strongest dimension: <b>{best_dim}</b>. "
        f"Priority gap: <b>{worst_dim}</b> at {worst_val:.1f}/100 "
        f"{'— below 85 threshold, requires immediate intervention.' if worst_val < 85 else '— room for optimisation.'} "
        f"Superhosts consistently outperform across all 6 dimensions — "
        f"upskilling the {int((1 - f['is_superhost'].mean()) * len(f)):,} regular hosts "
        f"represents the highest-leverage quality improvement lever.",
        color=GREEN,
    )
