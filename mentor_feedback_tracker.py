# app.py
# Mentor Pool Dashboard V7
# Run: streamlit run app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO

# =====================================================
# PAGE CONFIG
# =====================================================
st.set_page_config(
    page_title="Mentor Pool Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Mentor Pool Dashboard")
st.caption("Auto-loaded from GitHub")

# =====================================================
# UPDATE THESE URLs
# =====================================================
MENTOR_URL = "https://raw.githubusercontent.com/meenusaun/Mentor_Feedback/main/Mentors_List.xlsx"
FEEDBACK_URL = "https://raw.githubusercontent.com/meenusaun/Mentor_Feedback/main/Merntor_Feedback.xlsx"

# =====================================================
# HELPERS
# =====================================================
def normalize_cols(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def safe_find_col(df, keywords):
    for col in df.columns:
        for key in keywords:
            if key.lower() in col.lower():
                return col
    return None


def classify_rating(val):
    val = str(val).strip().lower()
    if val in ["extremely useful", "very useful"]:
        return "Good"
    elif val == "moderately useful":
        return "Average"
    elif val in ["slightly useful", "not useful"]:
        return "Poor"
    return None


def get_status(row):
    if row["meetings"] >= 5 and row["good_pct"] >= 80:
        return "⭐ High Performer"
    elif row["meetings"] <= 2 and row["good_pct"] >= 80 and row["meetings"] > 0:
        return "💎 Hidden Gem"
    elif row["poor"] >= 3:
        return "🚨 Needs Review"
    elif row["meetings"] == 0:
        return "😴 Dormant"
    return "🟡 Active"


def split_multi_values(series):
    vals = []
    for item in series.fillna("").astype(str):
        for part in item.split(","):
            part = part.strip()
            if part and part != "0":
                vals.append(part)
    return pd.Series(vals)


def multiselect_filter(df, col, label, key):
    options = sorted(df[col].dropna().unique().tolist())
    chosen = st.multiselect(label, options, key=key)
    if chosen:
        return df[df[col].isin(chosen)]
    return df


@st.cache_data
def load_github_file(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return BytesIO(r.content)


@st.cache_data
def load_excel(file):
    xls = pd.ExcelFile(file)
    sheets = {}
    for s in xls.sheet_names:
        sheets[s] = normalize_cols(pd.read_excel(file, sheet_name=s))
    return sheets


# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.header("⚙️ Data Source")
st.sidebar.success("✅ Files loaded from GitHub")

# =====================================================
# LOAD FILES FROM GITHUB
# =====================================================
try:
    mentor_file = load_github_file(MENTOR_URL)
    feedback_file = load_github_file(FEEDBACK_URL)
except Exception as e:
    st.error(f"GitHub load failed: {e}")
    st.stop()

# =====================================================
# LOAD DATA
# =====================================================
mentor_data = load_excel(mentor_file)
feedback_data = load_excel(feedback_file)

mentor_df = list(mentor_data.values())[0]

# Use 'Feedback from Founders' sheet (has Program & Hub columns)
if "Feedback from Founders" in feedback_data:
    fb_df = feedback_data["Feedback from Founders"]
else:
    fb_df = list(feedback_data.values())[0]

# =====================================================
# VENTURES LOOKUP  (Program comes from Ventures sheet)
# =====================================================
venture_program_map = {}
venture_hub_map = {}

if "Ventures" in feedback_data:
    ventures_df = feedback_data["Ventures"]
    v_name_col = safe_find_col(ventures_df, ["venture name", "venture"])
    v_prog_col = safe_find_col(ventures_df, ["program"])
    v_hub_col  = safe_find_col(ventures_df, ["hub"])
    if v_name_col and v_prog_col:
        venture_program_map = dict(
            zip(ventures_df[v_name_col].astype(str).str.strip(),
                ventures_df[v_prog_col].astype(str).str.strip())
        )
    if v_name_col and v_hub_col:
        venture_hub_map = dict(
            zip(ventures_df[v_name_col].astype(str).str.strip(),
                ventures_df[v_hub_col].astype(str).str.strip())
        )

# =====================================================
# DETECT COLUMNS – MENTOR MASTER
# =====================================================
mentor_col_master  = safe_find_col(mentor_df, ["name"])
linkedin_col       = safe_find_col(mentor_df, ["linkedin"])
skills_col         = safe_find_col(mentor_df, ["primary expertise"])
sector_col         = safe_find_col(mentor_df, ["primary sector"])
program_col_master = safe_find_col(mentor_df, ["program suitability"])
exp_col            = safe_find_col(mentor_df, ["years of experience"])

# =====================================================
# DETECT COLUMNS – FEEDBACK
# =====================================================
mentor_col_fb  = safe_find_col(fb_df, ["who was your mentor", "mentor"])
venture_col_fb = safe_find_col(fb_df, ["venture name", "venture"])
rating_raw_col = safe_find_col(fb_df, ["how useful"])
comment_col    = safe_find_col(fb_df, ["anything you'd like", "experience"])
rn_col         = safe_find_col(fb_df, ["rn remarks"])
connected_col  = safe_find_col(fb_df, ["connected"])
prog_col_fb    = safe_find_col(fb_df, ["program"])
hub_col_fb     = safe_find_col(fb_df, ["hub"])

# =====================================================
# BUILD MASTER DF
# =====================================================
master = pd.DataFrame()
master["mentor"]     = mentor_df[mentor_col_master].astype(str).str.strip()
master["linkedin"]   = mentor_df[linkedin_col] if linkedin_col else ""
master["skills"]     = mentor_df[skills_col] if skills_col else ""
master["sector"]     = mentor_df[sector_col] if sector_col else ""
master["program"]    = mentor_df[program_col_master] if program_col_master else ""
master["experience"] = mentor_df[exp_col] if exp_col else ""
master = master.drop_duplicates(subset=["mentor"])

# =====================================================
# BUILD FEEDBACK DF
# =====================================================
fb = pd.DataFrame()
fb["mentor"]    = fb_df[mentor_col_fb].astype(str).str.strip() if mentor_col_fb else ""
fb["venture"]   = fb_df[venture_col_fb].astype(str).str.strip() if venture_col_fb else ""
fb["rating_raw"]= fb_df[rating_raw_col] if rating_raw_col else ""
fb["rating"]    = fb["rating_raw"].apply(classify_rating)
fb["comment"]   = fb_df[comment_col] if comment_col else ""
fb["rn_remarks"]= fb_df[rn_col] if rn_col else ""
fb["connected"] = fb_df[connected_col] if connected_col else ""

# Venture program: prefer inline column from feedback sheet, fallback to Ventures sheet lookup
if prog_col_fb:
    fb["venture_program"] = fb_df[prog_col_fb].astype(str).str.strip().replace("nan", "")
    fb["venture_program"] = fb["venture_program"].where(
        fb["venture_program"] != "", fb["venture"].map(venture_program_map).fillna("")
    )
else:
    fb["venture_program"] = fb["venture"].map(venture_program_map).fillna("")

if hub_col_fb:
    fb["venture_hub"] = fb_df[hub_col_fb].astype(str).str.strip().replace("nan", "")
else:
    fb["venture_hub"] = fb["venture"].map(venture_hub_map).fillna("")

fb = fb[fb["mentor"].str.strip() != ""]

# =====================================================
# SUMMARY (mentor-level)
# =====================================================
summary = fb.groupby("mentor").agg(
    meetings=("mentor", "count"),
    good=("rating", lambda x: (x == "Good").sum()),
    average=("rating", lambda x: (x == "Average").sum()),
    poor=("rating", lambda x: (x == "Poor").sum())
).reset_index()

summary["good_pct"] = (summary["good"] / summary["meetings"] * 100).round(1)

# =====================================================
# MERGE → FINAL
# =====================================================
final = master.merge(summary, on="mentor", how="left").fillna(0)
final["meetings"] = final["meetings"].astype(int)
final["good"]     = final["good"].astype(int)
final["average"]  = final["average"].astype(int)
final["poor"]     = final["poor"].astype(int)
final["status"]   = final.apply(get_status, axis=1)

# =====================================================
# TOP METRICS
# =====================================================
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Mentors",  len(final))
c2.metric("Active Mentors", (final["meetings"] > 0).sum())
c3.metric("Dormant",        (final["meetings"] == 0).sum())
c4.metric("Total Meetings", final["meetings"].sum())

st.divider()

# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3 = st.tabs([
    "👤 Mentor Pool",
    "📋 Feedback Analysis",
    "🏢 Venture-wise Feedback"
])

# ╔══════════════════════════════════════════════════╗
# ║  TAB 1 – MENTOR POOL                            ║
# ╚══════════════════════════════════════════════════╝
with tab1:
    st.subheader("Mentor Pool Intelligence")

    # ── Filters ──────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)

        with f1:
            name_search = st.text_input("Search Mentor Name", key="mp_name")

        with f2:
            # Rating category filter derived from fb data
            all_rating_cats = ["Good", "Average", "Poor"]
            sel_ratings = st.multiselect(
                "Feedback Category",
                all_rating_cats,
                key="mp_rating"
            )

        with f3:
            all_statuses = sorted(final["status"].unique().tolist())
            sel_statuses = st.multiselect("Mentor Status", all_statuses, key="mp_status")

        with f4:
            # Mentor's own program suitability from master list
            prog_options = sorted(set(
                p.strip()
                for val in final["program"].dropna().astype(str)
                for p in val.split(",")
                if p.strip() and p.strip() != "nan"
            ))
            sel_programs = st.multiselect("Mentor Program", prog_options, key="mp_program")

    # ── Apply filters ─────────────────────────────────
    disp = final.copy()

    if name_search:
        disp = disp[disp["mentor"].str.contains(name_search, case=False, na=False)]

    if sel_statuses:
        disp = disp[disp["status"].isin(sel_statuses)]

    if sel_programs:
        disp = disp[disp["program"].apply(
            lambda v: any(p in str(v) for p in sel_programs)
        )]

    if sel_ratings:
        # Keep mentors who have at least 1 session of the selected category
        def has_rating(mentor_name):
            rows = fb[fb["mentor"] == mentor_name]
            return any(rows["rating"].isin(sel_ratings))
        disp = disp[disp["mentor"].apply(has_rating)]

    st.caption(f"Showing {len(disp)} of {len(final)} mentors")

    st.dataframe(
        disp[["mentor", "skills", "sector", "program", "experience",
              "meetings", "good", "average", "poor", "good_pct", "status"]],
        use_container_width=True,
        hide_index=True
    )

    # ── Charts ────────────────────────────────────────
    c1, c2, c3 = st.columns(3)

    with c1:
        top10 = disp.sort_values("meetings", ascending=False).head(10)
        fig1 = px.bar(top10, x="mentor", y="meetings", title="Top Mentors by Meetings")
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        skill_series = split_multi_values(disp["skills"])
        if not skill_series.empty:
            sdf = skill_series.value_counts().head(10).reset_index()
            sdf.columns = ["Skill", "Count"]
            fig2 = px.bar(sdf, x="Skill", y="Count", title="Top Skills")
            st.plotly_chart(fig2, use_container_width=True)

    with c3:
        sector_series = split_multi_values(disp["sector"])
        if not sector_series.empty:
            sec = sector_series.value_counts().head(10).reset_index()
            sec.columns = ["Sector", "Count"]
            fig3 = px.pie(sec, names="Sector", values="Count", title="Sector Mix")
            st.plotly_chart(fig3, use_container_width=True)


# ╔══════════════════════════════════════════════════╗
# ║  TAB 2 – FEEDBACK ANALYSIS                      ║
# ╚══════════════════════════════════════════════════╝
with tab2:
    st.subheader("Feedback Intelligence")

    # ── Filters ──────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        fa1, fa2, fa3 = st.columns(3)

        with fa1:
            mentor_options = ["All"] + sorted(fb["mentor"].dropna().unique().tolist())
            sel_mentor_fb = st.selectbox("Select Mentor", mentor_options, key="fa_mentor")

        with fa2:
            v_prog_options = ["All"] + sorted(
                p for p in fb["venture_program"].dropna().unique() if p and p != "nan"
            )
            sel_v_prog = st.selectbox("Venture Program", v_prog_options, key="fa_vprog")

        with fa3:
            # Mentor's program from master list
            mentor_prog_options = ["All"] + sorted(set(
                p.strip()
                for val in final["program"].dropna().astype(str)
                for p in val.split(",")
                if p.strip() and p.strip() != "nan"
            ))
            sel_m_prog = st.selectbox("Mentor Program", mentor_prog_options, key="fa_mprog")

    # ── Filter feedback ───────────────────────────────
    fb_view = fb.copy()

    if sel_mentor_fb != "All":
        fb_view = fb_view[fb_view["mentor"] == sel_mentor_fb]

    if sel_v_prog != "All":
        fb_view = fb_view[fb_view["venture_program"] == sel_v_prog]

    if sel_m_prog != "All":
        # Get mentors whose program field contains selected program
        matching_mentors = final[final["program"].apply(
            lambda v: sel_m_prog in str(v)
        )]["mentor"].tolist()
        fb_view = fb_view[fb_view["mentor"].isin(matching_mentors)]

    # ── Summary table ─────────────────────────────────
    summary2 = fb_view.groupby("mentor").agg(
        Good=("rating", lambda x: (x == "Good").sum()),
        Average=("rating", lambda x: (x == "Average").sum()),
        Poor=("rating", lambda x: (x == "Poor").sum()),
        Connected_By_Us=("connected", lambda x: x.astype(str).str.contains("yes", case=False).sum()),
        Total=("mentor", "count")
    ).reset_index()

    st.dataframe(summary2, use_container_width=True, hide_index=True)

    # ── Mentor drill-down ─────────────────────────────
    if sel_mentor_fb != "All":
        st.divider()
        st.markdown(f"#### 🔎 Venture Details for **{sel_mentor_fb}**")

        mentor_fb = fb_view[fb_view["mentor"] == sel_mentor_fb].copy()
        mentor_fb["venture_program_display"] = mentor_fb["venture_program"].replace("", "—")

        detail_cols = ["venture", "venture_program_display", "rating", "comment", "rn_remarks", "connected"]
        col_labels  = {
            "venture": "Venture",
            "venture_program_display": "Venture Program",
            "rating": "Rating",
            "comment": "Founder Comment",
            "rn_remarks": "RN Remarks",
            "connected": "Connected by Us"
        }

        avail_cols = [c for c in detail_cols if c in mentor_fb.columns]
        display_df = mentor_fb[avail_cols].rename(columns=col_labels)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Mini rating chart
        if not mentor_fb.empty:
            rc = mentor_fb["rating"].value_counts().reset_index()
            rc.columns = ["Rating", "Count"]
            fig_r = px.pie(rc, names="Rating", values="Count",
                           title=f"Rating Distribution – {sel_mentor_fb}",
                           color="Rating",
                           color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"})
            st.plotly_chart(fig_r, use_container_width=True)

    else:
        # Show aggregate charts when no specific mentor selected
        st.divider()
        col_a, col_b = st.columns(2)

        with col_a:
            top_fb = summary2.sort_values("Total", ascending=False).head(10)
            fig_top = px.bar(
                top_fb.melt(id_vars="mentor", value_vars=["Good", "Average", "Poor"]),
                x="mentor", y="value", color="variable", barmode="stack",
                title="Top 10 Mentors – Feedback Breakdown",
                color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}
            )
            st.plotly_chart(fig_top, use_container_width=True)

        with col_b:
            overall_ratings = fb_view["rating"].value_counts().reset_index()
            overall_ratings.columns = ["Rating", "Count"]
            fig_ov = px.pie(
                overall_ratings, names="Rating", values="Count",
                title="Overall Rating Mix",
                color="Rating",
                color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}
            )
            st.plotly_chart(fig_ov, use_container_width=True)


# ╔══════════════════════════════════════════════════╗
# ║  TAB 3 – VENTURE-WISE FEEDBACK                  ║
# ╚══════════════════════════════════════════════════╝
with tab3:
    st.subheader("Venture-wise Feedback")

    # ── Filters ──────────────────────────────────────
    with st.expander("🔍 Filters", expanded=True):
        vf1, vf2 = st.columns(2)

        with vf1:
            vp_options = ["All"] + sorted(
                p for p in fb["venture_program"].dropna().unique() if p and p != "nan"
            )
            sel_vp = st.selectbox("Venture Program", vp_options, key="vf_vprog")

        with vf2:
            hub_options = ["All"] + sorted(
                h for h in fb["venture_hub"].dropna().unique() if h and h != "nan"
            )
            sel_hub = st.selectbox("Hub", hub_options, key="vf_hub")

    # ── Filter fb ─────────────────────────────────────
    fb_v = fb.copy()
    if sel_vp != "All":
        fb_v = fb_v[fb_v["venture_program"] == sel_vp]
    if sel_hub != "All":
        fb_v = fb_v[fb_v["venture_hub"] == sel_hub]

    # ── Venture summary ───────────────────────────────
    venture_summary = fb_v.groupby("venture").agg(
        Mentors_Connected=("mentor", "nunique"),
        Good=("rating", lambda x: (x == "Good").sum()),
        Average=("rating", lambda x: (x == "Average").sum()),
        Poor=("rating", lambda x: (x == "Poor").sum()),
        Total_Sessions=("mentor", "count")
    ).reset_index()

    venture_summary["Good_%"] = (
        venture_summary["Good"] / venture_summary["Total_Sessions"] * 100
    ).round(1)

    def overall_experience(row):
        if row["Total_Sessions"] == 0:
            return "—"
        good_pct = row["Good_%"]
        poor_count = row["Poor"]
        if good_pct >= 70:
            return "😊 Positive"
        elif poor_count >= 2:
            return "😟 Needs Attention"
        return "😐 Mixed"

    venture_summary["Overall Experience"] = venture_summary.apply(overall_experience, axis=1)

    # Add program column
    venture_summary["Program"] = venture_summary["venture"].map(venture_program_map).fillna("—")

    display_vs = venture_summary[[
        "venture", "Program", "Mentors_Connected",
        "Good", "Average", "Poor", "Good_%", "Overall Experience"
    ]].rename(columns={"venture": "Venture"})

    st.caption(f"Showing {len(display_vs)} ventures")
    st.dataframe(display_vs, use_container_width=True, hide_index=True)

    # ── Top/bottom chart ──────────────────────────────
    col_x, col_y = st.columns(2)
    with col_x:
        top_v = venture_summary.sort_values("Good_%", ascending=False).head(10)
        fig_vt = px.bar(
            top_v, x="venture", y="Good_%",
            title="Top Ventures by % Good Ratings",
            color_discrete_sequence=["#2ecc71"]
        )
        fig_vt.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_vt, use_container_width=True)

    with col_y:
        exp_counts = venture_summary["Overall Experience"].value_counts().reset_index()
        exp_counts.columns = ["Experience", "Count"]
        fig_exp = px.pie(
            exp_counts, names="Experience", values="Count",
            title="Venture Experience Distribution",
            color="Experience",
            color_discrete_map={
                "😊 Positive": "#2ecc71",
                "😐 Mixed": "#f39c12",
                "😟 Needs Attention": "#e74c3c",
                "—": "#bdc3c7"
            }
        )
        st.plotly_chart(fig_exp, use_container_width=True)

    # ── Venture drill-down ────────────────────────────
    st.divider()
    st.markdown("#### 🔎 Venture Deep-dive")

    venture_options = ["— Select a Venture —"] + sorted(fb_v["venture"].dropna().unique().tolist())
    sel_venture = st.selectbox("Select Venture", venture_options, key="vf_select")

    if sel_venture != "— Select a Venture —":
        v_rows = fb_v[fb_v["venture"] == sel_venture].copy()

        # Header stats
        vc1, vc2, vc3, vc4 = st.columns(4)
        vc1.metric("Sessions", len(v_rows))
        vc2.metric("Mentors", v_rows["mentor"].nunique())
        vc3.metric("Good", int((v_rows["rating"] == "Good").sum()))
        vc4.metric("Poor", int((v_rows["rating"] == "Poor").sum()))

        prog_label = venture_program_map.get(sel_venture, "—")
        st.caption(f"**Program:** {prog_label}  |  **Hub:** {venture_hub_map.get(sel_venture, '—')}")

        st.markdown("##### Mentor Sessions")
        v_detail = v_rows[[
            "mentor", "rating", "comment", "rn_remarks", "connected"
        ]].rename(columns={
            "mentor": "Mentor",
            "rating": "Rating",
            "comment": "Founder Comment",
            "rn_remarks": "RN Remarks",
            "connected": "Connected by Us"
        })
        st.dataframe(v_detail, use_container_width=True, hide_index=True)

        # Per-mentor rating breakdown
        mentor_breakdown = v_rows.groupby("mentor").agg(
            Good=("rating", lambda x: (x == "Good").sum()),
            Average=("rating", lambda x: (x == "Average").sum()),
            Poor=("rating", lambda x: (x == "Poor").sum()),
            Sessions=("mentor", "count")
        ).reset_index()

        fig_mb = px.bar(
            mentor_breakdown.melt(id_vars="mentor", value_vars=["Good", "Average", "Poor"]),
            x="mentor", y="value", color="variable", barmode="stack",
            title=f"Mentor Rating Breakdown – {sel_venture}",
            labels={"mentor": "Mentor", "value": "Sessions", "variable": "Rating"},
            color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}
        )
        st.plotly_chart(fig_mb, use_container_width=True)

# =====================================================
# DOWNLOAD
# =====================================================
st.divider()
csv = final.to_csv(index=False).encode()
st.download_button("⬇ Download Mentor Report", csv, "mentor_pool_report.csv", "text/csv")
