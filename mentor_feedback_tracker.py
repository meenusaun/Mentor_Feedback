import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from collections import defaultdict
from openai import OpenAI
import os

# -----------------------------------
# PAGE CONFIG
# -----------------------------------
st.set_page_config(
    page_title="Mentor Feedback Review App",
    page_icon="📋",
    layout="wide"
)

st.title("📋 Mentor Feedback Review App")
st.caption("Upload Mentor Feedback Excel and analyse mentor quality")

# -----------------------------------
# OPENAI CLIENT
# -----------------------------------
@st.cache_resource
def get_client():
    key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    if key:
        return OpenAI(api_key=key)
    return None

client = get_client()

# -----------------------------------
# HELPERS
# -----------------------------------
def classify_rating(text):
    text = str(text).strip()

    if text in ["Extremely useful", "Very useful"]:
        return "Good"

    elif text == "Moderately useful":
        return "Moderate"

    elif text in ["Slightly useful", "Not useful"]:
        return "Poor"

    return None


def ask_ai(prompt):
    if not client:
        return "⚠️ OpenAI API key not configured."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


# -----------------------------------
# EXCEL PARSER
# -----------------------------------
def parse_excel(uploaded_file):
    wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)

    venture_meta = {}

    # Ventures Sheet
    if "Ventures" in wb.sheetnames:
        ws = wb["Ventures"]

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                continue

            if row[0]:
                venture = str(row[0]).strip()

                venture_meta[venture] = {
                    "program": str(row[1]).strip() if row[1] else "",
                    "hub": str(row[3]).strip() if row[3] else ""
                }

    rows = []

    if "Feedback from Founders" not in wb.sheetnames:
        return pd.DataFrame()

    ws = wb["Feedback from Founders"]

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue

        mentor = str(row[15]).strip() if row[15] else ""
        venture = str(row[11]).strip() if row[11] else ""
        session_rating = str(row[16]).strip() if row[16] else ""
        founder_comment = str(row[19]).strip() if row[19] else ""
        action_items = str(row[17]).strip() if row[17] else ""
        meet_again = str(row[18]).strip() if row[18] else ""

        rating = classify_rating(session_rating)

        if not mentor or not venture or not rating:
            continue

        meta = venture_meta.get(venture, {})

        rows.append({
            "mentor": mentor,
            "venture": venture,
            "rating": rating,
            "rating_raw": session_rating,
            "feedback": founder_comment,
            "action_items": action_items,
            "meet_again": meet_again,
            "hub": meta.get("hub", ""),
            "program": meta.get("program", "")
        })

    return pd.DataFrame(rows)


# -----------------------------------
# FILE UPLOAD
# -----------------------------------
uploaded_file = st.sidebar.file_uploader(
    "Upload Excel File",
    type=["xlsx"]
)

if not uploaded_file:
    st.info("Upload your mentor feedback tracker Excel file.")
    st.stop()

df = parse_excel(uploaded_file)

if df.empty:
    st.warning("No valid feedback found.")
    st.stop()

# -----------------------------------
# TOP METRICS
# -----------------------------------
c1, c2, c3, c4 = st.columns(4)

c1.metric("Mentors", df["mentor"].nunique())
c2.metric("Good", (df["rating"] == "Good").sum())
c3.metric("Moderate", (df["rating"] == "Moderate").sum())
c4.metric("Poor", (df["rating"] == "Poor").sum())

st.divider()

# -----------------------------------
# FILTERS
# -----------------------------------
all_hubs = sorted(df["hub"].dropna().unique())
all_programs = sorted(df["program"].dropna().unique())

col1, col2, col3 = st.columns(3)

search = col1.text_input("Search Mentor / Venture")

rating_filter = col2.multiselect(
    "Rating",
    ["Good", "Moderate", "Poor"]
)

hub_filter = col3.multiselect(
    "Hub",
    all_hubs
)

filtered = df.copy()

if search:
    q = search.lower()

    filtered = filtered[
        filtered["mentor"].str.lower().str.contains(q) |
        filtered["venture"].str.lower().str.contains(q)
    ]

if rating_filter:
    filtered = filtered[filtered["rating"].isin(rating_filter)]

if hub_filter:
    filtered = filtered[filtered["hub"].isin(hub_filter)]

# -----------------------------------
# MENTOR VIEW
# -----------------------------------
mentors = sorted(filtered["mentor"].unique())

for mentor in mentors:

    mdf = filtered[filtered["mentor"] == mentor]

    g = (mdf["rating"] == "Good").sum()
    m = (mdf["rating"] == "Moderate").sum()
    p = (mdf["rating"] == "Poor").sum()

    with st.expander(
        f"{mentor} | 🟢 {g} 🟡 {m} 🔴 {p}"
    ):

        for _, row in mdf.iterrows():

            st.markdown(f"""
**{row['venture']}**  
Rating: {row['rating']}  
Feedback: {row['feedback']}  
Action Items: {row['action_items']}  
Meet Again: {row['meet_again']}  
Hub: {row['hub']} | Program: {row['program']}
---
""")

        if st.button(f"AI Review {mentor}", key=mentor):

            entries = "\n".join([
                f"{r['venture']} [{r['rating']}]: {r['feedback']}"
                for _, r in mdf.iterrows()
            ])

            prompt = f"""
You are reviewing mentor quality.

Mentor Name: {mentor}

Entries:
{entries}

Give:

1. Neutral summary
2. Strengths
3. Concerns
4. Should this mentor be promoted / monitored / reviewed
"""

            st.info(ask_ai(prompt))

# -----------------------------------
# DOWNLOAD SUMMARY
# -----------------------------------
summary = df.groupby(["mentor", "rating"]).size().unstack(fill_value=0).reset_index()

st.download_button(
    "⬇ Download Summary CSV",
    summary.to_csv(index=False).encode(),
    "mentor_summary.csv",
    "text/csv"
)