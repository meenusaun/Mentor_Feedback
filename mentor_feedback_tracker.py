import streamlit as st
import pandas as pd
import openpyxl
from io import BytesIO
from collections import defaultdict
import anthropic
from openai import OpenAI
import os
import requests

# ─────────────────────────────────────────────
# GITHUB RAW URL  ← update filename if different
# ─────────────────────────────────────────────
GITHUB_RAW_URL = (
    "https://raw.githubusercontent.com/meenusaun/Mentor_Feedback/main/"
    "Merntor_Feedback.xlsx"
)

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Resources Network – Mentor Feedback Tracker",
    page_icon="📋",
    layout="wide",
)

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if os.path.exists("DP_BG1.png"):
        st.image("DP_BG1.png", width=150)
with col2:
    st.markdown(
        "<h2 style='text-align: center;'>"
        "📋 Resources Network – Mentor Feedback Tracker</h2>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────
# AI CLIENTS
# ─────────────────────────────────────────────
@st.cache_resource
def get_clients():
    oa_key = st.secrets.get("OPENAI_API_KEY",    os.environ.get("OPENAI_API_KEY",    ""))
    an_key = st.secrets.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
    oc = OpenAI(api_key=oa_key) if oa_key else None
    ac = anthropic.Anthropic(api_key=an_key) if an_key else None
    return oc, ac

openai_client, anthropic_client = get_clients()

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.title("⚙️ Settings")

ai_model = st.sidebar.radio(
    "AI Model for Insights:",
    ["GPT-4o Mini (OpenAI)", "Claude (Anthropic)"],
    index=1,
)
st.sidebar.markdown("---")

st.sidebar.subheader("📂 Data Source")
data_source = st.sidebar.radio(
    "Load from:",
    ["GitHub (auto)", "Upload file manually"],
    index=0,
)
uploaded_file = None
if data_source == "Upload file manually":
    uploaded_file = st.sidebar.file_uploader(
        "Upload Tracker Excel", type=["xlsx"], key="tracker_upload"
    )

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    for k in ["df", "completed_map", "venture_meta"]:
        st.session_state.pop(k, None)
    st.rerun()

st.sidebar.markdown("---")
if st.sidebar.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []
    st.rerun()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def classify(u):
    u = str(u).strip()
    if u in ("Extremely useful", "Very useful"):  return "Good"
    if u == "Moderately useful":                   return "Moderate"
    if u in ("Slightly useful", "Not useful"):     return "Poor"
    return None

def badge(label, bg, color):
    return (
        f"<span style='background:{bg};color:{color};padding:2px 9px;"
        f"border-radius:8px;font-size:12px;font-weight:600;'>{label}</span>"
    )

RATING_STYLE = {
    "Good":     ("#EAF3DE", "#27500A"),
    "Moderate": ("#FAEEDA", "#633806"),
    "Poor":     ("#FCEBEB", "#791F1F"),
}
RN_STYLE = {
    True:  ("By RN",     "#E6F1FB", "#0C447C"),
    False: ("Not by RN", "#EEEDFE", "#3C3489"),
}

# ─────────────────────────────────────────────
# DATA LOADING
# ─────────────────────────────────────────────
@st.cache_data(show_spinner="Fetching tracker from GitHub…")
def load_github_bytes():
    r = requests.get(GITHUB_RAW_URL, timeout=30)
    if r.status_code != 200:
        raise ValueError(
            f"GitHub fetch failed (HTTP {r.status_code}). "
            "Check GITHUB_RAW_URL and that the file is public."
        )
    return r.content

def parse_excel(file_bytes):
    wb = openpyxl.load_workbook(
        BytesIO(file_bytes), read_only=True, data_only=True
    )

    # Ventures → hub / program lookup
    venture_meta = {}
    if "Ventures" in wb.sheetnames:
        for i, r in enumerate(wb["Ventures"].iter_rows(values_only=True)):
            if i == 0 or not r[0]:
                continue
            venture_meta[str(r[0]).strip()] = {
                "program": str(r[1]).strip() if r[1] else "",
                "hub":     str(r[3]).strip() if r[3] else "",
            }

    # Mentor Connects → completed meeting count
    completed_map = defaultdict(int)
    if "Mentor Connects" in wb.sheetnames:
        for i, r in enumerate(wb["Mentor Connects"].iter_rows(values_only=True)):
            if i == 0:
                continue
            if r[4] and str(r[5]).strip() == "Connected":
                completed_map[str(r[4]).strip()] += 1

    # Feedback from Founders
    rows = []
    if "Feedback from Founders" not in wb.sheetnames:
        return pd.DataFrame(), dict(completed_map), venture_meta

    for i, r in enumerate(
        wb["Feedback from Founders"].iter_rows(values_only=True)
    ):
        if i == 0:
            continue
        resp_status  = str(r[22]).strip() if r[22] else ""
        connected_us = str(r[23]).strip() if r[23] else ""
        if resp_status == "Duplicate" or connected_us == "Duplicate":
            continue

        mentor  = str(r[15]).strip() if r[15] else ""
        venture = str(r[11]).strip() if r[11] else ""
        cat     = classify(str(r[16]).strip() if r[16] else "")
        if not mentor or not venture or not cat:
            continue

        meta = venture_meta.get(venture, {})
        rows.append({
            "mentor":       mentor,
            "venture":      venture,
            "rating_raw":   str(r[16]).strip() if r[16] else "",
            "rating":       cat,
            "by_rn":        connected_us == "Yes",
            "feedback":     str(r[19]).strip() if r[19] and str(r[19]).strip() not in ["None",""] else "",
            "rn_remarks":   str(r[20]).strip() if r[20] and str(r[20]).strip() not in ["None",""] else "",
            "action_items": str(r[17]).strip() if r[17] and str(r[17]).strip() not in ["None",""] else "",
            "meet_again":   str(r[18]).strip() if r[18] else "",
            "program":      meta.get("program", ""),
            "hub":          meta.get("hub", ""),
            "founder_name": str(r[10]).strip() if r[10] else "",
        })

    return pd.DataFrame(rows), dict(completed_map), venture_meta

# ─────────────────────────────────────────────
# AI CALL
# ─────────────────────────────────────────────
def call_ai(prompt, max_tokens=1500):
    if ai_model == "GPT-4o Mini (OpenAI)" and openai_client:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return resp.choices[0].message.content
    elif anthropic_client:
        resp = anthropic_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            temperature=0,
            system=(
                "You are an intelligent program operations assistant for NEN "
                "(National Entrepreneurship Network). You help the Resources Network "
                "team analyse mentor-founder session feedback, identify patterns, flag "
                "concerns, and surface actionable insights. Be concise, structured, "
                "and practical."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text
    return "⚠️ AI not configured. Please add API keys to st.secrets."

# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────
for k, v in {"df": None, "completed_map": {}, "venture_meta": {}, "chat_history": []}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
if st.session_state.df is None:
    try:
        if data_source == "GitHub (auto)":
            file_bytes = load_github_bytes()
        elif uploaded_file:
            file_bytes = uploaded_file.read()
        else:
            file_bytes = None

        if file_bytes:
            df, completed_map, venture_meta = parse_excel(file_bytes)
            st.session_state.df            = df
            st.session_state.completed_map = completed_map
            st.session_state.venture_meta  = venture_meta
            if not df.empty:
                st.sidebar.success(
                    f"✅ {df['mentor'].nunique()} mentors · {len(df)} feedbacks loaded"
                )
            else:
                st.sidebar.warning("⚠️ File loaded but no feedback rows found.")
        else:
            st.info("👈 Select 'Upload file manually' and upload the tracker Excel.")
            st.stop()

    except Exception as e:
        st.error(f"❌ Error loading data: {e}")
        st.stop()

df            = st.session_state.df
completed_map = st.session_state.completed_map

if df is None or df.empty:
    st.warning("No feedback data found. Check the Excel file.")
    st.stop()

# ─────────────────────────────────────────────
# DERIVED
# ─────────────────────────────────────────────
all_mentors  = sorted(df["mentor"].unique().tolist())
all_hubs     = sorted([h for h in df["hub"].unique()     if h])
all_programs = sorted([p for p in df["program"].unique() if p])

# ─────────────────────────────────────────────
# TOP METRICS
# ─────────────────────────────────────────────
st.markdown("---")
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("👤 Mentors",        df["mentor"].nunique())
m2.metric("🟢 Good",           (df["rating"] == "Good").sum())
m3.metric("🟡 Moderate",       (df["rating"] == "Moderate").sum())
m4.metric("🔴 Poor",           (df["rating"] == "Poor").sum())
m5.metric("🔵 Not by RN",      (~df["by_rn"]).sum())
st.markdown("---")

# ─────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(
    ["🔍 Mentor Lookup", "📊 All Mentors View", "🤖 AI Insights"]
)

# ════════════════════════════════════════════
# TAB 1 – MENTOR LOOKUP
# ════════════════════════════════════════════
with tab1:
    st.subheader("Search & Filter Mentor Feedback")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
    with c1:
        mentor_search = st.text_input(
            "🔎 Search mentor or venture", placeholder="e.g. Sriram or Bebe Burp"
        )
    with c2:
        rating_filter = st.multiselect("Rating", ["Good", "Moderate", "Poor"])
    with c3:
        hub_filter = st.multiselect("Hub", all_hubs)
    with c4:
        program_filter = st.multiselect("Program", all_programs)

    filtered = df.copy()
    if mentor_search:
        q = mentor_search.lower()
        filtered = filtered[
            filtered["mentor"].str.lower().str.contains(q, na=False) |
            filtered["venture"].str.lower().str.contains(q, na=False)
        ]
    if rating_filter:
        filtered = filtered[filtered["rating"].isin(rating_filter)]
    if hub_filter:
        filtered = filtered[filtered["hub"].isin(hub_filter)]
    if program_filter:
        filtered = filtered[filtered["program"].isin(program_filter)]

    mentors_in_view = sorted(filtered["mentor"].unique().tolist())
    st.caption(
        f"Showing **{len(mentors_in_view)} mentor(s)** · **{len(filtered)} entries**"
    )

    if not mentors_in_view:
        st.warning("No mentors match the current filters.")
    else:
        for mentor_name in mentors_in_view:
            mf  = filtered[filtered["mentor"] == mentor_name]
            all_mf = df[df["mentor"] == mentor_name]

            g  = (all_mf["rating"] == "Good").sum()
            mo = (all_mf["rating"] == "Moderate").sum()
            p  = (all_mf["rating"] == "Poor").sum()
            done     = completed_map.get(mentor_name, 0)
            total_fb = len(all_mf)

            with st.expander(
                f"**{mentor_name}**  ·  🟢 {g}  🟡 {mo}  🔴 {p}  "
                f"|  📅 {done} meetings completed  ·  💬 {total_fb} feedbacks",
                expanded=False,
            ):
                st.markdown(
                    badge(f"🟢 {g} Good",     "#EAF3DE", "#27500A") + "&nbsp;" +
                    badge(f"🟡 {mo} Moderate","#FAEEDA", "#633806") + "&nbsp;" +
                    badge(f"🔴 {p} Poor",     "#FCEBEB", "#791F1F") + "&nbsp;&nbsp;" +
                    badge(f"📅 {done} meetings completed", "#E6F1FB", "#0C447C"),
                    unsafe_allow_html=True,
                )
                st.markdown("")

                sort_order = {"Poor": 0, "Moderate": 1, "Good": 2}
                for _, row in mf.assign(
                    _s=mf["rating"].map(sort_order)
                ).sort_values("_s").iterrows():

                    r_bg, r_color     = RATING_STYLE[row["rating"]]
                    rn_lbl, rn_bg, rn_col = RN_STYLE[row["by_rn"]]

                    ma_badge = (
                        "&nbsp;" + badge("Re-meet: " + row["meet_again"], "#F3E5F5", "#3C3489")
                        if row["meet_again"] and row["meet_again"].lower() not in ["", "none"]
                        else ""
                    )
                    fb_html = (
                        f'<p style="font-size:13px;color:#444;font-style:italic;margin:4px 0 2px;">'
                        f'"{row["feedback"]}"</p>'
                        if row["feedback"]
                        else '<p style="font-size:12px;color:#aaa;margin:4px 0 2px;">No founder comment.</p>'
                    )
                    rn_html = (
                        f'<p style="font-size:12px;color:#555;margin:2px 0;">'
                        f'<b>RN Remarks:</b> {row["rn_remarks"]}</p>'
                        if row["rn_remarks"] else ""
                    )
                    ai_html = (
                        f'<p style="font-size:12px;color:#555;margin:2px 0;">'
                        f'<b>Action Items:</b> {row["action_items"]}</p>'
                        if row["action_items"] else ""
                    )
                    meta_html = (
                        f'<p style="font-size:11px;color:#aaa;margin:4px 0 0;">'
                        f'Hub: {row["hub"]} · Program: {row["program"]}</p>'
                        if row["hub"] or row["program"] else ""
                    )

                    st.markdown(
                        f"""<div style='border-left:3px solid {r_color};
                            background:{r_bg}33;border-radius:6px;
                            padding:10px 14px;margin-bottom:8px;'>
                          <div style='display:flex;align-items:center;
                              gap:6px;flex-wrap:wrap;margin-bottom:2px;'>
                            <span style='font-weight:600;font-size:14px;
                                color:#1F3864;'>{row['venture']}</span>
                            {badge(row['rating'], r_bg, r_color)}
                            {badge(rn_lbl, rn_bg, rn_col)}
                            {ma_badge}
                          </div>
                          {fb_html}{rn_html}{ai_html}{meta_html}
                        </div>""",
                        unsafe_allow_html=True,
                    )

                if st.button(f"🤖 AI insight for {mentor_name}", key=f"ai_{mentor_name}"):
                    with st.spinner("Generating insight…"):
                        entries = "\n".join([
                            f"- {row['venture']} [{row['rating']}]"
                            f"[{'By RN' if row['by_rn'] else 'Not by RN'}]: "
                            f"{row['feedback'] or 'no comment'}"
                            + (f" | RN: {row['rn_remarks']}" if row["rn_remarks"] else "")
                            for _, row in all_mf.iterrows()
                        ])
                        prompt = (
                            f"Mentor: {mentor_name}\n"
                            f"Completed meetings: {done} | Feedbacks: {total_fb} "
                            f"(Good:{g} Moderate:{mo} Poor:{p})\n\n"
                            f"Entries:\n{entries}\n\n"
                            "Provide:\n1. Overall pattern (2-3 lines)\n"
                            "2. Strengths (bullets)\n3. Concerns/action items for RN (bullets)\n"
                            "Be specific. Use actual feedback text."
                        )
                        st.info(call_ai(prompt))

# ════════════════════════════════════════════
# TAB 2 – ALL MENTORS TABLE
# ════════════════════════════════════════════
with tab2:
    st.subheader("All Mentors — Summary Table")

    rows_s = []
    for mn in all_mentors:
        mdf = df[df["mentor"] == mn]
        rows_s.append({
            "Mentor":          mn,
            "Meetings Done":   completed_map.get(mn, 0),
            "Total Feedbacks": len(mdf),
            "🟢 Good":         (mdf["rating"] == "Good").sum(),
            "🟡 Moderate":     (mdf["rating"] == "Moderate").sum(),
            "🔴 Poor":         (mdf["rating"] == "Poor").sum(),
            "Not by RN":       (~mdf["by_rn"]).sum(),
            "Ventures":        ", ".join(sorted(mdf["venture"].unique())),
            "Hub(s)":          ", ".join(sorted([h for h in mdf["hub"].unique()     if h])),
            "Program(s)":      ", ".join(sorted([pr for pr in mdf["program"].unique() if pr])),
        })

    summary_df = pd.DataFrame(rows_s)

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        sort_col = st.selectbox(
            "Sort by", ["🟢 Good","Meetings Done","Total Feedbacks","🔴 Poor","🟡 Moderate"]
        )
    with fc2:
        sort_dir = st.radio("Order", ["Descending","Ascending"], horizontal=True)
    with fc3:
        hub_f2 = st.multiselect("Filter by Hub", all_hubs, key="hub_tab2")

    disp = summary_df.copy()
    if hub_f2:
        disp = disp[disp["Hub(s)"].apply(lambda x: any(h in x for h in hub_f2))]
    disp = disp.sort_values(sort_col, ascending=(sort_dir == "Ascending"))

    st.dataframe(disp, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download CSV", disp.to_csv(index=False).encode(),
        "mentor_feedback_summary.csv", "text/csv"
    )

# ════════════════════════════════════════════
# TAB 3 – AI INSIGHTS CHAT
# ════════════════════════════════════════════
with tab3:
    st.subheader("🤖 AI Insights — Ask anything about the feedback data")
    st.caption(
        "Try: *Which mentors have poor feedback?* · "
        "*Summarise Pune hub* · *Sessions not connected by us?*"
    )

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_q = st.chat_input("Ask about mentor feedback, patterns, or specific ventures…")

    if user_q:
        with st.chat_message("user"):
            st.markdown(user_q)
        st.session_state.chat_history.append({"role": "user", "content": user_q})

        with st.chat_message("assistant"):
            with st.spinner("Analysing…"):
                summaries = []
                for mn in all_mentors:
                    mdf = df[df["mentor"] == mn]
                    g  = (mdf["rating"] == "Good").sum()
                    mo = (mdf["rating"] == "Moderate").sum()
                    p  = (mdf["rating"] == "Poor").sum()
                    done = completed_map.get(mn, 0)
                    lines = [
                        f"    • {r['venture']} [{r['rating']}]"
                        f"[{'By RN' if r['by_rn'] else 'Not by RN'}]"
                        f"[{r['hub']}][{r['program']}]: "
                        f"{r['feedback'][:120] if r['feedback'] else 'no comment'}"
                        + (f" | RN:{r['rn_remarks'][:80]}" if r["rn_remarks"] else "")
                        for _, r in mdf.iterrows()
                    ]
                    summaries.append(
                        f"MENTOR: {mn} | Done:{done} | G:{g} M:{mo} P:{p}\n"
                        + "\n".join(lines)
                    )

                prev = "\n".join([
                    f"{'User' if m['role']=='user' else 'Asst'}: {m['content']}"
                    for m in st.session_state.chat_history[-6:]
                ])

                prompt = (
                    "You are assisting the NEN Resources Network team.\n\n"
                    "DATA:\n" + "\n\n".join(summaries[:50]) + "\n\n"
                    "PREVIOUS CHAT:\n" + prev + "\n\n"
                    f"QUESTION: {user_q}\n\n"
                    "Answer using the data. Be structured and concise. "
                    "Flag concerns proactively."
                )
                resp = call_ai(prompt, max_tokens=1500)
                st.markdown(resp)
                st.session_state.chat_history.append(
                    {"role": "assistant", "content": resp}
                )
