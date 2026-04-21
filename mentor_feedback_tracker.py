# app.py
# Mentor Pool Dashboard V5 (GitHub Auto + Manual Upload)
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

st.title("📊 Mentor Pool Dashboard V5")
st.caption("Analyse your mentor network using GitHub auto-load or manual upload")

# =====================================================
# CONFIG - UPDATE THESE 2 URLS
# =====================================================
MENTOR_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/Mentors_List.xlsx"
FEEDBACK_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/Merntor_Feedback.xlsx"

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
        sheets[s] = normalize_cols(
            pd.read_excel(file, sheet_name=s)
        )

    return sheets


# =====================================================
# SIDEBAR
# =====================================================
st.sidebar.header("⚙️ Data Source")

source = st.sidebar.radio(
    "Load files from:",
    ["GitHub Auto", "Manual Upload"]
)

mentor_file = None
feedback_file = None

if source == "GitHub Auto":

    try:
        mentor_file = load_github_file(MENTOR_URL)
        feedback_file = load_github_file(FEEDBACK_URL)
        st.sidebar.success("✅ Files loaded from GitHub")

    except Exception as e:
        st.sidebar.error(f"GitHub load failed: {e}")
        st.stop()

else:
    mentor_file = st.sidebar.file_uploader(
        "Upload Mentors_List.xlsx",
        type=["xlsx"]
    )

    feedback_file = st.sidebar.file_uploader(
        "Upload Mentor_Feedback.xlsx",
        type=["xlsx"]
    )

    if not mentor_file or not feedback_file:
        st.info("Please upload both files.")
        st.stop()

# =====================================================
# LOAD DATA
# =====================================================
mentor_data = load_excel(mentor_file)
feedback_data = load_excel(feedback_file)

mentor_df = list(mentor_data.values())[0]

if "Feedback from Founders" in feedback_data:
    fb_df = feedback_data["Feedback from Founders"]
else:
    fb_df = list(feedback_data.values())[0]

# =====================================================
# VENTURE PROGRAM MAP
# =====================================================
venture_program_map = {}

if "Ventures" in feedback_data:

    ventures_df = feedback_data["Ventures"]

    venture_name_col = safe_find_col(
        ventures_df,
        ["venture", "startup"]
    )

    venture_program_col = safe_find_col(
        ventures_df,
        ["program"]
    )

    if venture_name_col and venture_program_col:

        venture_program_map = dict(
            zip(
                ventures_df[venture_name_col].astype(str).str.strip(),
                ventures_df[venture_program_col].astype(str).str.strip()
            )
        )

# =====================================================
# COLUMN DETECTION
# =====================================================
mentor_col_master = safe_find_col(
    mentor_df,
    ["mentor name", "name", "mentor"]
)

linkedin_col = safe_find_col(
    mentor_df,
    ["linkedin"]
)

skills_col = safe_find_col(
    mentor_df,
    ["skills", "expertise"]
)

sector_col = safe_find_col(
    mentor_df,
    ["sector", "industry", "domain"]
)

program_col_master = safe_find_col(
    mentor_df,
    ["program"]
)

exp_col = safe_find_col(
    mentor_df,
    ["experience", "years"]
)

mentor_col_fb = safe_find_col(
    fb_df,
    ["mentor"]
)

venture_col = safe_find_col(
    fb_df,
    ["venture"]
)

rating_raw_col = safe_find_col(
    fb_df,
    ["how useful", "useful"]
)

comment_col = safe_find_col(
    fb_df,
    ["anything you'd like", "experience"]
)

rn_col = safe_find_col(
    fb_df,
    ["rn remarks"]
)

connected_col = safe_find_col(
    fb_df,
    ["connected"]
)

# =====================================================
# MASTER DATA
# =====================================================
master = pd.DataFrame()

master["mentor"] = mentor_df[mentor_col_master].astype(str).str.strip()
master["linkedin"] = mentor_df[linkedin_col] if linkedin_col else ""
master["skills"] = mentor_df[skills_col] if skills_col else ""
master["sector"] = mentor_df[sector_col] if sector_col else ""
master["program"] = mentor_df[program_col_master] if program_col_master else ""
master["experience"] = mentor_df[exp_col] if exp_col else ""

master = master.drop_duplicates(subset=["mentor"])

# =====================================================
# FEEDBACK DATA
# =====================================================
fb = pd.DataFrame()

fb["mentor"] = fb_df[mentor_col_fb].astype(str).str.strip()
fb["venture"] = fb_df[venture_col].astype(str).str.strip() if venture_col else ""

fb["rating_raw"] = fb_df[rating_raw_col] if rating_raw_col else ""
fb["rating"] = fb["rating_raw"].apply(classify_rating)

fb["comment"] = fb_df[comment_col] if comment_col else ""
fb["rn_remarks"] = fb_df[rn_col] if rn_col else ""
fb["connected"] = fb_df[connected_col] if connected_col else ""

fb["venture_program"] = fb["venture"].map(
    venture_program_map
).fillna("")

fb = fb[fb["mentor"] != ""]

# =====================================================
# SUMMARY
# =====================================================
summary = fb.groupby("mentor").agg(
    meetings=("mentor", "count"),
    good=("rating", lambda x: (x == "Good").sum()),
    average=("rating", lambda x: (x == "Average").sum()),
    poor=("rating", lambda x: (x == "Poor").sum())
).reset_index()

summary["good_pct"] = (
    summary["good"] / summary["meetings"] * 100
).round(1)

# =====================================================
# MERGE
# =====================================================
final = master.merge(
    summary,
    on="mentor",
    how="left"
).fillna(0)

final["meetings"] = final["meetings"].astype(int)
final["good"] = final["good"].astype(int)
final["average"] = final["average"].astype(int)
final["poor"] = final["poor"].astype(int)

final["status"] = final.apply(get_status, axis=1)

# =====================================================
# TOP METRICS
# =====================================================
c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Mentors", len(final))
c2.metric("Active Mentors", (final["meetings"] > 0).sum())
c3.metric("Dormant", (final["meetings"] == 0).sum())
c4.metric("Meetings", final["meetings"].sum())

st.divider()

# =====================================================
# TABS
# =====================================================
tab1, tab2 = st.tabs([
    "👤 Mentor Pool",
    "📋 Feedback Analysis"
])

# =====================================================
# TAB 1
# =====================================================
with tab1:

    st.subheader("Mentor Pool Intelligence")

    st.dataframe(
        final[
            [
                "mentor",
                "skills",
                "sector",
                "program",
                "experience",
                "meetings",
                "good",
                "average",
                "poor",
                "good_pct",
                "status"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        top10 = final.sort_values(
            "meetings",
            ascending=False
        ).head(10)

        fig1 = px.bar(
            top10,
            x="mentor",
            y="meetings",
            title="Top Mentors by Meetings"
        )
        st.plotly_chart(fig1, use_container_width=True)

    with c2:
        skill_series = split_multi_values(final["skills"])

        if not skill_series.empty:
            sdf = skill_series.value_counts().head(10).reset_index()
            sdf.columns = ["Skill", "Count"]

            fig2 = px.bar(
                sdf,
                x="Skill",
                y="Count",
                title="Top Skills"
            )
            st.plotly_chart(fig2, use_container_width=True)

    with c3:
        sector_series = split_multi_values(final["sector"])

        if not sector_series.empty:
            sec = sector_series.value_counts().head(10).reset_index()
            sec.columns = ["Sector", "Count"]

            fig3 = px.pie(
                sec,
                names="Sector",
                values="Count",
                title="Sector Mix"
            )
            st.plotly_chart(fig3, use_container_width=True)

# =====================================================
# TAB 2
# =====================================================
with tab2:

    st.subheader("Feedback Intelligence")

    summary2 = fb.groupby("mentor").agg(
        Good=("rating", lambda x: (x == "Good").sum()),
        Average=("rating", lambda x: (x == "Average").sum()),
        Poor=("rating", lambda x: (x == "Poor").sum()),
        Connected_By_Us=("connected", lambda x: x.astype(str).str.contains("yes", case=False).sum()),
        Total=("mentor", "count")
    ).reset_index()

    st.dataframe(
        summary2,
        use_container_width=True,
        hide_index=True
    )

# =====================================================
# DOWNLOAD
# =====================================================
csv = final.to_csv(index=False).encode()

st.download_button(
    "⬇ Download Report",
    csv,
    "mentor_pool_report.csv",
    "text/csv"
)
