# app.py
# Internal Mentor Pool Dashboard V1
# Run: streamlit run app.py

import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from collections import defaultdict
import plotly.express as px
from datetime import datetime

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="Mentor Pool Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Internal Mentor Pool Dashboard")
st.caption("Upload Mentor Master + Feedback files to analyse mentor network health")

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
def normalize_cols(df):
    df.columns = [str(c).strip() for c in df.columns]
    return df


def classify_rating(text):
    text = str(text).strip().lower()

    if text in ["extremely useful", "very useful"]:
        return "Good"

    elif text == "moderately useful":
        return "Moderate"

    elif text in ["slightly useful", "not useful"]:
        return "Poor"

    return None


def safe_find_col(df, options):
    """
    Finds first matching column from possible names.
    """
    cols = [c.lower() for c in df.columns]

    for opt in options:
        for actual in df.columns:
            if opt.lower() in actual.lower():
                return actual

    return None


# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------
st.sidebar.header("📁 Upload Files")

mentor_file = st.sidebar.file_uploader(
    "Upload Mentor Master File",
    type=["xlsx"],
    key="mentor_file"
)

feedback_file = st.sidebar.file_uploader(
    "Upload Mentor Feedback File",
    type=["xlsx"],
    key="feedback_file"
)

if not mentor_file or not feedback_file:
    st.info("Please upload both files to continue.")
    st.stop()

# ---------------------------------------------------
# LOAD FILES
# ---------------------------------------------------
@st.cache_data
def load_excel(file):
    xls = pd.ExcelFile(file)
    sheets = xls.sheet_names

    data = {}

    for s in sheets:
        data[s] = normalize_cols(pd.read_excel(file, sheet_name=s))

    return data


mentor_data = load_excel(mentor_file)
feedback_data = load_excel(feedback_file)

# ---------------------------------------------------
# FIND MAIN SHEETS
# ---------------------------------------------------
mentor_df = list(mentor_data.values())[0]

if "Feedback from Founders" in feedback_data:
    fb_df = feedback_data["Feedback from Founders"]
else:
    fb_df = list(feedback_data.values())[0]

mentor_df = normalize_cols(mentor_df)
fb_df = normalize_cols(fb_df)

# ---------------------------------------------------
# COLUMN DETECTION
# ---------------------------------------------------
mentor_name_col_master = safe_find_col(
    mentor_df,
    ["mentor name", "name", "mentor"]
)

linkedin_col = safe_find_col(
    mentor_df,
    ["linkedin"]
)

skills_col = safe_find_col(
    mentor_df,
    ["skills", "key skills", "expertise"]
)

program_col_master = safe_find_col(
    mentor_df,
    ["program"]
)

exp_col = safe_find_col(
    mentor_df,
    ["experience", "years"]
)

mentor_name_col_fb = safe_find_col(
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
    ["anything you'd like", "experience", "share"]
)

rn_col = safe_find_col(
    fb_df,
    ["rn remarks"]
)

connected_col = safe_find_col(
    fb_df,
    ["connected by us", "connected by rn", "connected"]
)

date_col = safe_find_col(
    fb_df,
    ["date", "timestamp"]
)

# ---------------------------------------------------
# VALIDATION
# ---------------------------------------------------
if mentor_name_col_master is None:
    st.error("Could not detect Mentor Name column in mentor file.")
    st.stop()

if mentor_name_col_fb is None:
    st.error("Could not detect Mentor column in feedback file.")
    st.stop()

# ---------------------------------------------------
# PREP MASTER
# ---------------------------------------------------
master = pd.DataFrame()

master["mentor"] = mentor_df[mentor_name_col_master].astype(str).str.strip()

master["linkedin"] = (
    mentor_df[linkedin_col] if linkedin_col else ""
)

master["skills"] = (
    mentor_df[skills_col] if skills_col else ""
)

master["program"] = (
    mentor_df[program_col_master] if program_col_master else ""
)

master["experience"] = (
    mentor_df[exp_col] if exp_col else ""
)

master = master.drop_duplicates(subset=["mentor"])

# ---------------------------------------------------
# PREP FEEDBACK
# ---------------------------------------------------
fb = pd.DataFrame()

fb["mentor"] = fb_df[mentor_name_col_fb].astype(str).str.strip()

fb["venture"] = (
    fb_df[venture_col].astype(str).str.strip()
    if venture_col else ""
)

fb["rating_raw"] = (
    fb_df[rating_raw_col].astype(str).str.strip()
    if rating_raw_col else ""
)

fb["rating"] = fb["rating_raw"].apply(classify_rating)

fb["comment"] = (
    fb_df[comment_col].astype(str).str.strip()
    if comment_col else ""
)

fb["rn_remarks"] = (
    fb_df[rn_col].astype(str).str.strip()
    if rn_col else ""
)

fb["connected"] = (
    fb_df[connected_col].astype(str).str.strip()
    if connected_col else ""
)

if date_col:
    fb["session_date"] = pd.to_datetime(
        fb_df[date_col],
        errors="coerce"
    )
else:
    fb["session_date"] = pd.NaT

fb = fb[fb["mentor"] != ""]
fb = fb.dropna(subset=["mentor"])

# ---------------------------------------------------
# AGGREGATE
# ---------------------------------------------------
summary = fb.groupby("mentor").agg(
    meetings=("mentor", "count"),
    good=("rating", lambda x: (x == "Good").sum()),
    moderate=("rating", lambda x: (x == "Moderate").sum()),
    poor=("rating", lambda x: (x == "Poor").sum()),
    last_session=("session_date", "max")
).reset_index()

summary["good_pct"] = (
    summary["good"] / summary["meetings"] * 100
).round(1)

summary["poor_pct"] = (
    summary["poor"] / summary["meetings"] * 100
).round(1)

# ---------------------------------------------------
# MERGE
# ---------------------------------------------------
final = master.merge(
    summary,
    on="mentor",
    how="left"
)

final["meetings"] = final["meetings"].fillna(0).astype(int)
final["good"] = final["good"].fillna(0).astype(int)
final["moderate"] = final["moderate"].fillna(0).astype(int)
final["poor"] = final["poor"].fillna(0).astype(int)
final["good_pct"] = final["good_pct"].fillna(0)
final["poor_pct"] = final["poor_pct"].fillna(0)

# ---------------------------------------------------
# FLAGS
# ---------------------------------------------------
def get_status(row):
    if row["meetings"] >= 5 and row["good_pct"] >= 80:
        return "⭐ High Performer"

    elif row["meetings"] <= 2 and row["good_pct"] >= 80 and row["meetings"] > 0:
        return "💎 Hidden Gem"

    elif row["poor"] >= 3:
        return "🚨 Needs Review"

    elif row["meetings"] == 0:
        return "😴 Dormant"

    else:
        return "🟡 Active"


final["status"] = final.apply(get_status, axis=1)

# ---------------------------------------------------
# TOP METRICS
# ---------------------------------------------------
total_mentors = len(final)
active_mentors = (final["meetings"] > 0).sum()
dormant = (final["meetings"] == 0).sum()
total_meetings = final["meetings"].sum()

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Mentors", total_mentors)
c2.metric("Active Mentors", active_mentors)
c3.metric("Dormant", dormant)
c4.metric("Meetings", total_meetings)

st.divider()

# ---------------------------------------------------
# FILTERS
# ---------------------------------------------------
col1, col2 = st.columns(2)

search = col1.text_input("Search Mentor")

status_filter = col2.multiselect(
    "Status",
    final["status"].unique().tolist()
)

view = final.copy()

if search:
    view = view[
        view["mentor"].str.lower().str.contains(search.lower())
    ]

if status_filter:
    view = view[
        view["status"].isin(status_filter)
    ]

# ---------------------------------------------------
# TABLE
# ---------------------------------------------------
st.subheader("👤 Mentor Pool Scorecards")

st.dataframe(
    view[
        [
            "mentor",
            "skills",
            "program",
            "experience",
            "meetings",
            "good",
            "moderate",
            "poor",
            "good_pct",
            "poor_pct",
            "status"
        ]
    ],
    use_container_width=True,
    hide_index=True
)

# ---------------------------------------------------
# CHARTS
# ---------------------------------------------------
st.subheader("📈 Insights")

col1, col2 = st.columns(2)

with col1:
    top10 = final.sort_values(
        "meetings",
        ascending=False
    ).head(10)

    fig = px.bar(
        top10,
        x="mentor",
        y="meetings",
        title="Top Mentors by Meetings"
    )

    st.plotly_chart(fig, use_container_width=True)

with col2:
    rating_counts = {
        "Good": fb["rating"].eq("Good").sum(),
        "Moderate": fb["rating"].eq("Moderate").sum(),
        "Poor": fb["rating"].eq("Poor").sum()
    }

    pie_df = pd.DataFrame({
        "Rating": list(rating_counts.keys()),
        "Count": list(rating_counts.values())
    })

    fig2 = px.pie(
        pie_df,
        names="Rating",
        values="Count",
        title="Overall Feedback Split"
    )

    st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------
# MENTOR DETAIL
# ---------------------------------------------------
st.subheader("🔍 Mentor Detail View")

mentor_pick = st.selectbox(
    "Select Mentor",
    sorted(final["mentor"].tolist())
)

md = final[final["mentor"] == mentor_pick].iloc[0]
mfb = fb[fb["mentor"] == mentor_pick]

st.markdown(f"### {mentor_pick}")
st.write(f"**Skills:** {md['skills']}")
st.write(f"**Program:** {md['program']}")
st.write(f"**Experience:** {md['experience']}")
st.write(f"**LinkedIn:** {md['linkedin']}")
st.write(f"**Status:** {md['status']}")
st.write(f"**Meetings:** {md['meetings']}")

st.markdown("### Feedback Entries")

for _, r in mfb.iterrows():
    st.markdown(f"""
**Venture:** {r['venture']}  
**Rating:** {r['rating']}  
**Founder Comment:** {r['comment']}  
**RN Remarks:** {r['rn_remarks']}  
---
""")

# ---------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------
csv = final.to_csv(index=False).encode()

st.download_button(
    "⬇ Download Mentor Pool Report",
    csv,
    "mentor_pool_report.csv",
    "text/csv"
)