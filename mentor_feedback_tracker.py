# app.py  –  Mentor Pool Dashboard V8
# Run: streamlit run app.py

import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO

# ─────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="Mentor Pool Dashboard", page_icon="📊", layout="wide")
st.title("📊 Mentor Pool Dashboard")
st.caption("Auto-loaded from GitHub")

# ─────────────────────────────────────────────────────────
# GITHUB URLs  ← update as needed
# ─────────────────────────────────────────────────────────
MENTOR_URL   = "https://raw.githubusercontent.com/meenusaun/Mentor_Feedback/main/Mentors_List.xlsx"
FEEDBACK_URL = "https://raw.githubusercontent.com/meenusaun/Mentor_Feedback/main/Merntor_Feedback.xlsx"
VENTURES_URL = "https://raw.githubusercontent.com/meenusaun/Mentor_Feedback/main/VenturesList.xlsx"

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────
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
    v = str(val).strip().lower()
    if v in ["extremely useful", "very useful"]:  return "Good"
    if v == "moderately useful":                  return "Average"
    if v in ["slightly useful", "not useful"]:    return "Poor"
    return None

def get_status(row):
    if row["meetings"] >= 5 and row["good_pct"] >= 80:                          return "⭐ High Performer"
    if row["meetings"] <= 2 and row["good_pct"] >= 80 and row["meetings"] > 0:  return "💎 Hidden Gem"
    if row["poor"] >= 3:                                                          return "🚨 Needs Review"
    if row["meetings"] == 0:                                                      return "😴 Dormant"
    return "🟡 Active"

def split_multi(series):
    vals = []
    for item in series.fillna("").astype(str):
        for p in item.split(","):
            p = p.strip()
            if p and p != "0" and p.lower() != "nan":
                vals.append(p)
    return pd.Series(vals)

def clean_str(series):
    return series.astype(str).str.strip().replace({"nan": "", "NaT": ""})

@st.cache_data
def fetch_url(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return BytesIO(r.content)

@st.cache_data
def load_excel(file_bytes):
    xls = pd.ExcelFile(file_bytes)
    return {s: normalize_cols(pd.read_excel(file_bytes, sheet_name=s)) for s in xls.sheet_names}

# ─────────────────────────────────────────────────────────
# LOAD FILES
# ─────────────────────────────────────────────────────────
st.sidebar.header("⚙️ Data Source")
try:
    mentor_sheets   = load_excel(fetch_url(MENTOR_URL))
    feedback_sheets = load_excel(fetch_url(FEEDBACK_URL))
    ventures_sheets = load_excel(fetch_url(VENTURES_URL))
    st.sidebar.success("✅ All files loaded from GitHub")
except Exception as e:
    st.error(f"GitHub load failed: {e}")
    st.stop()

mentor_df   = list(mentor_sheets.values())[0]
fb_df       = feedback_sheets.get("Feedback from Founders", list(feedback_sheets.values())[0])
ventures_df = ventures_sheets.get("Ventures", list(ventures_sheets.values())[0])

# ─────────────────────────────────────────────────────────
# VENTURES LOOKUP  (VenturesList.xlsx is source of truth)
# ─────────────────────────────────────────────────────────
v_name_col = safe_find_col(ventures_df, ["venture name"])
v_prog_col = safe_find_col(ventures_df, ["program"])
v_hub_col  = safe_find_col(ventures_df, ["hub"])

venture_program_map: dict = {}
venture_hub_map: dict     = {}
if v_name_col:
    vnames = ventures_df[v_name_col].astype(str).str.strip()
    if v_prog_col:
        venture_program_map = dict(zip(vnames, ventures_df[v_prog_col].astype(str).str.strip()))
    if v_hub_col:
        venture_hub_map = dict(zip(vnames, ventures_df[v_hub_col].astype(str).str.strip()))

# ─────────────────────────────────────────────────────────
# MENTOR MASTER
# ─────────────────────────────────────────────────────────
mc_name   = safe_find_col(mentor_df, ["name"])
mc_li     = safe_find_col(mentor_df, ["linkedin"])
mc_skills = safe_find_col(mentor_df, ["primary expertise"])
mc_sector = safe_find_col(mentor_df, ["primary sector"])
mc_prog   = safe_find_col(mentor_df, ["program suitability"])
mc_exp    = safe_find_col(mentor_df, ["years of experience"])
mc_expcat = safe_find_col(mentor_df, ["experience category"])

master = pd.DataFrame({
    "mentor":      clean_str(mentor_df[mc_name]),
    "linkedin":    clean_str(mentor_df[mc_li])     if mc_li     else "",
    "skills":      clean_str(mentor_df[mc_skills]) if mc_skills else "",
    "sector":      clean_str(mentor_df[mc_sector]) if mc_sector else "",
    "program":     clean_str(mentor_df[mc_prog])   if mc_prog   else "",
    "experience":  clean_str(mentor_df[mc_exp])    if mc_exp    else "",
    "exp_category":clean_str(mentor_df[mc_expcat]) if mc_expcat else "",
}).drop_duplicates(subset=["mentor"])

# ─────────────────────────────────────────────────────────
# FEEDBACK DF  (Program & Hub always from VenturesList)
# ─────────────────────────────────────────────────────────
fc_mentor    = safe_find_col(fb_df, ["who was your mentor", "mentor"])
fc_venture   = safe_find_col(fb_df, ["venture name", "venture"])
fc_rating    = safe_find_col(fb_df, ["how useful"])
fc_comment   = safe_find_col(fb_df, ["anything you'd like", "experience"])
fc_rn        = safe_find_col(fb_df, ["rn remarks"])
fc_connected = safe_find_col(fb_df, ["connected"])

fb = pd.DataFrame({
    "mentor":     clean_str(fb_df[fc_mentor])    if fc_mentor    else "",
    "venture":    clean_str(fb_df[fc_venture])   if fc_venture   else "",
    "rating_raw": fb_df[fc_rating]               if fc_rating    else "",
    "comment":    clean_str(fb_df[fc_comment])   if fc_comment   else "",
    "rn_remarks": clean_str(fb_df[fc_rn])        if fc_rn        else "",
    "connected":  clean_str(fb_df[fc_connected]) if fc_connected else "",
})
fb["rating"]          = fb["rating_raw"].apply(classify_rating)
fb["venture_program"] = fb["venture"].map(venture_program_map).fillna("").replace("nan", "")
fb["venture_hub"]     = fb["venture"].map(venture_hub_map).fillna("").replace("nan", "")
fb = fb[fb["mentor"].str.strip() != ""]

# ─────────────────────────────────────────────────────────
# MENTOR SUMMARY → FINAL
# ─────────────────────────────────────────────────────────
summary = fb.groupby("mentor").agg(
    meetings=("mentor", "count"),
    good    =("rating", lambda x: (x == "Good").sum()),
    average =("rating", lambda x: (x == "Average").sum()),
    poor    =("rating", lambda x: (x == "Poor").sum()),
).reset_index()
summary["good_pct"] = (summary["good"] / summary["meetings"].replace(0, pd.NA) * 100).round(1).fillna(0)

final = master.merge(summary, on="mentor", how="left").fillna(0)
for col in ["meetings", "good", "average", "poor"]:
    final[col] = final[col].astype(int)
final["status"] = final.apply(get_status, axis=1)

# ─────────────────────────────────────────────────────────
# STAT ROW HELPERS  (all filter-aware)
# ─────────────────────────────────────────────────────────
def mentor_stats(df_f, fb_f=None):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Mentors",  len(df_f))
    c2.metric("Active Mentors", int((df_f["meetings"] > 0).sum()))
    c3.metric("Dormant",        int((df_f["meetings"] == 0).sum()))
    c4.metric("Total Meetings", int(df_f["meetings"].sum()))
    # Row 2: Mentor Status counts
    status_order = ["⭐ High Performer", "💎 Hidden Gem", "🟡 Active", "🚨 Needs Review", "😴 Dormant"]
    s_counts = df_f["status"].value_counts()
    st.caption("**Mentor Status Breakdown**")
    scols = st.columns(len(status_order))
    for i, s in enumerate(status_order):
        scols[i].metric(s, int(s_counts.get(s, 0)))
    # Row 3: Overall Experience counts (mentors with feedback only)
    if fb_f is not None and not fb_f.empty:
        exp_labels = {"😊 Positive": 0, "😐 Mixed": 0, "😟 Needs Attention": 0}
        for mname, grp in fb_f.groupby("mentor"):
            gp = (grp["rating"] == "Good").sum() / len(grp) * 100
            pc = (grp["rating"] == "Poor").sum()
            if gp >= 70:   exp_labels["😊 Positive"]       += 1
            elif pc >= 2:  exp_labels["😟 Needs Attention"] += 1
            else:          exp_labels["😐 Mixed"]           += 1
        st.caption("**Overall Experience Breakdown** (mentors with sessions)")
        ec1, ec2, ec3 = st.columns(3)
        ec1.metric("😊 Positive",        exp_labels["😊 Positive"])
        ec2.metric("😐 Mixed",           exp_labels["😐 Mixed"])
        ec3.metric("😟 Needs Attention", exp_labels["😟 Needs Attention"])

def feedback_stats(fb_f):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Sessions",     len(fb_f))
    c2.metric("Feedbacks Received", int(fb_f["rating"].notna().sum()))
    c3.metric("✅ Good",            int((fb_f["rating"] == "Good").sum()))
    c4.metric("🟡 Average",         int((fb_f["rating"] == "Average").sum()))
    c5.metric("🔴 Poor",            int((fb_f["rating"] == "Poor").sum()))

def venture_stats(fb_f):
    all_v  = fb_f["venture"].nunique()
    conn_v = fb_f[fb_f["connected"].str.lower().str.contains("yes", na=False)]["venture"].nunique()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Ventures",              all_v)
    c2.metric("Ventures w/ Mentor Connect",  conn_v)
    c3.metric("Total Sessions",              len(fb_f))

# ══════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["👤 Mentor Pool", "📋 Feedback Analysis", "🏢 Venture-wise Feedback"])


# ╔══════════════════════════════════════════════════╗
# ║  TAB 1 – MENTOR POOL                            ║
# ╚══════════════════════════════════════════════════╝
with tab1:
    st.subheader("Mentor Pool Intelligence")

    with st.expander("🔍 Filters", expanded=True):
        f1, f2, f3 = st.columns(3)
        name_search  = f1.text_input("Search Mentor Name", key="mp_name")
        sel_ratings  = f2.multiselect("Feedback Category", ["Good", "Average", "Poor"], key="mp_rating")
        sel_statuses = f3.multiselect("Mentor Status", sorted(final["status"].unique()), key="mp_status")

        f4, f5, f6 = st.columns(3)
        prog_opts    = sorted({
            p.strip() for val in final["program"].astype(str)
            for p in val.split(",") if p.strip() not in ("", "nan")
        })
        sel_programs  = f4.multiselect("Mentor Program", prog_opts, key="mp_program")
        exp_cat_opts  = sorted({v for v in final["exp_category"].unique() if v and v != ""})
        sel_exp_cats  = f5.multiselect("Experience Band", exp_cat_opts, key="mp_expcat")
        sel_ov_exp    = f6.multiselect("Overall Experience", ["😊 Positive", "😐 Mixed", "😟 Needs Attention"], key="mp_ovexp")

    # Pre-compute per-mentor overall experience label
    mentor_exp_map = {}
    for mentor_name, grp in fb.groupby("mentor"):
        good_pct = (grp["rating"] == "Good").sum() / len(grp) * 100
        poor_cnt = (grp["rating"] == "Poor").sum()
        if good_pct >= 70:   mentor_exp_map[mentor_name] = "😊 Positive"
        elif poor_cnt >= 2:  mentor_exp_map[mentor_name] = "😟 Needs Attention"
        else:                mentor_exp_map[mentor_name] = "😐 Mixed"

    disp = final.copy()
    if name_search:
        disp = disp[disp["mentor"].str.contains(name_search, case=False, na=False)]
    if sel_statuses:
        disp = disp[disp["status"].isin(sel_statuses)]
    if sel_programs:
        disp = disp[disp["program"].apply(lambda v: any(p in str(v) for p in sel_programs))]
    if sel_ratings:
        matched = fb[fb["rating"].isin(sel_ratings)]["mentor"].unique()
        disp = disp[disp["mentor"].isin(matched)]
    if sel_exp_cats:
        disp = disp[disp["exp_category"].isin(sel_exp_cats)]
    if sel_ov_exp:
        matched_exp = [m for m, label in mentor_exp_map.items() if label in sel_ov_exp]
        disp = disp[disp["mentor"].isin(matched_exp)]

    # Stats
    st.markdown("---")
    mentor_stats(disp, fb[fb["mentor"].isin(disp["mentor"])])
    st.markdown("---")

    st.caption(f"Showing {len(disp)} of {len(final)} mentors")
    if disp.empty:
        st.info("ℹ️ No mentors match the selected filters. Please adjust your filters.")
        st.stop()
    st.dataframe(
        disp[["mentor", "linkedin", "skills", "sector", "program", "experience", "exp_category",
              "meetings", "good", "average", "poor", "good_pct", "status"]],
        column_config={"linkedin": st.column_config.LinkColumn("LinkedIn", display_text="🔗 Profile")},
        use_container_width=True, hide_index=True
    )

    ch1, ch2, ch3 = st.columns(3)
    with ch1:
        top10 = disp.sort_values("meetings", ascending=False).head(10)
        st.plotly_chart(px.bar(top10, x="mentor", y="meetings", title="Top 10 by Meetings"),
                        use_container_width=True)
    with ch2:
        ss = split_multi(disp["skills"])
        if not ss.empty:
            sdf = ss.value_counts().head(10).reset_index()
            sdf.columns = ["Skill", "Count"]
            st.plotly_chart(px.bar(sdf, x="Skill", y="Count", title="Top Skills"),
                            use_container_width=True)
    with ch3:
        sec = split_multi(disp["sector"])
        if not sec.empty:
            sedf = sec.value_counts().head(10).reset_index()
            sedf.columns = ["Sector", "Count"]
            st.plotly_chart(px.pie(sedf, names="Sector", values="Count", title="Sector Mix"),
                            use_container_width=True)

    # ── Mentor Deep-dive ──────────────────────────────
    st.divider()
    st.markdown("#### 🔎 Mentor Deep-dive")
    dd_opts       = ["— Select a Mentor —"] + sorted(disp["mentor"].dropna().unique().tolist())
    sel_mentor_dd = st.selectbox("Select Mentor", dd_opts, key="mp_dd")

    if sel_mentor_dd != "— Select a Mentor —":
        mrow = disp[disp["mentor"] == sel_mentor_dd].iloc[0]
        mfb  = fb[fb["mentor"] == sel_mentor_dd].copy()

        pc1, pc2, pc3, pc4, pc5 = st.columns(5)
        pc1.metric("Sessions",   int(mrow["meetings"]))
        pc2.metric("✅ Good",    int(mrow["good"]))
        pc3.metric("🟡 Average", int(mrow["average"]))
        pc4.metric("🔴 Poor",    int(mrow["poor"]))
        pc5.metric("Good %",     f"{mrow['good_pct']}%")

        li_url = mrow["linkedin"]
        li_link = f"[🔗 LinkedIn Profile]({li_url})" if li_url and li_url not in ("", "nan") else "—"
        st.caption(
            f"**Status:** {mrow['status']}  |  **Skills:** {mrow['skills']}  |  "
            f"**Sector:** {mrow['sector']}  |  **Experience:** {mrow['experience']} yrs  |  "
            f"**Program:** {mrow['program']}  |  **LinkedIn:** {li_link}"
        )

        if mfb.empty:
            st.info("No feedback sessions recorded for this mentor yet.")
        else:
            mfb["vp"] = mfb["venture_program"].replace("", "—")
            mfb["vh"] = mfb["venture_hub"].replace("", "—")
            detail = mfb[["venture", "vp", "vh", "rating", "comment", "rn_remarks", "connected"]].rename(columns={
                "venture": "Venture", "vp": "Venture Program", "vh": "Hub",
                "rating": "Rating", "comment": "Founder Comment",
                "rn_remarks": "RN Remarks", "connected": "Connected by Us",
            })
            st.markdown("##### Ventures Connected & Feedback")
            st.dataframe(detail, use_container_width=True, hide_index=True)

            rc = mfb["rating"].dropna().value_counts().reset_index()
            rc.columns = ["Rating", "Count"]
            st.plotly_chart(
                px.pie(rc, names="Rating", values="Count",
                       title=f"Rating Mix – {sel_mentor_dd}", color="Rating",
                       color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}),
                use_container_width=True
            )


# ╔══════════════════════════════════════════════════╗
# ║  TAB 2 – FEEDBACK ANALYSIS                      ║
# ╚══════════════════════════════════════════════════╝
with tab2:
    st.subheader("Feedback Intelligence")

    with st.expander("🔍 Filters", expanded=True):
        fa1, fa2, fa3, fa4 = st.columns(4)

        mentor_fb_opts = ["All"] + sorted(fb["mentor"].dropna().unique().tolist())
        sel_mentor_fb  = fa1.selectbox("Select Mentor", mentor_fb_opts, key="fa_mentor")

        vp_vals = sorted({v for v in venture_program_map.values() if v and v not in ("nan", "")})
        sel_v_prog = fa2.selectbox("Venture Program", ["All"] + vp_vals, key="fa_vprog")

        mp_vals = sorted({
            p.strip() for val in final["program"].astype(str)
            for p in val.split(",") if p.strip() not in ("", "nan")
        })
        sel_m_prog = fa3.selectbox("Mentor Program (Suitability)", ["All"] + mp_vals, key="fa_mprog")

        sel_fb_cat2 = fa4.multiselect("Feedback Category", ["Good", "Average", "Poor"], key="fa_fbcat")

    fb_view = fb.copy()
    if sel_mentor_fb != "All":
        fb_view = fb_view[fb_view["mentor"] == sel_mentor_fb]
    if sel_v_prog != "All":
        fb_view = fb_view[fb_view["venture_program"] == sel_v_prog]
    if sel_m_prog != "All":
        m_in_prog = final[final["program"].apply(lambda v: sel_m_prog in str(v))]["mentor"].tolist()
        fb_view   = fb_view[fb_view["mentor"].isin(m_in_prog)]
    if sel_fb_cat2:
        fb_view = fb_view[fb_view["rating"].isin(sel_fb_cat2)]

    # Stats
    st.markdown("---")
    feedback_stats(fb_view)
    st.markdown("---")

    if fb_view.empty:
        st.info("ℹ️ No feedback data matches the selected filters. Please adjust your filters.")
        st.stop()

    # Summary table with mentor status, skills, sector
    sum2 = fb_view.groupby("mentor").agg(
        Good            =("rating", lambda x: (x == "Good").sum()),
        Average         =("rating", lambda x: (x == "Average").sum()),
        Poor            =("rating", lambda x: (x == "Poor").sum()),
        Connected_By_Us =("connected", lambda x: x.str.lower().str.contains("yes", na=False).sum()),
        Total           =("mentor", "count"),
    ).reset_index()
    sum2 = sum2.merge(final[["mentor", "status", "skills", "sector"]], on="mentor", how="left")
    sum2["Good_%"] = (sum2["Good"] / sum2["Total"].replace(0, pd.NA) * 100).round(1).fillna(0)
    sum2 = sum2[["mentor", "status", "skills", "sector", "Good", "Average", "Poor", "Good_%", "Connected_By_Us", "Total"]]
    sum2.columns = ["Mentor", "Status", "Skills", "Sector", "Good", "Average", "Poor", "Good %", "Connected By Us", "Total Sessions"]

    st.dataframe(sum2, use_container_width=True, hide_index=True)

    # ── Mentor drill-down ─────────────────────────────
    if sel_mentor_fb != "All":
        st.divider()
        st.markdown(f"#### 🔎 Venture Details for **{sel_mentor_fb}**")
        mfd = fb_view[fb_view["mentor"] == sel_mentor_fb].copy()
        mfd["vp"] = mfd["venture_program"].replace("", "—")
        mfd["vh"] = mfd["venture_hub"].replace("", "—")
        dd2 = mfd[["venture", "vp", "vh", "rating", "comment", "rn_remarks", "connected"]].rename(columns={
            "venture": "Venture", "vp": "Venture Program", "vh": "Hub",
            "rating": "Rating", "comment": "Founder Comment",
            "rn_remarks": "RN Remarks", "connected": "Connected by Us",
        })
        st.dataframe(dd2, use_container_width=True, hide_index=True)

        rc2 = mfd["rating"].dropna().value_counts().reset_index()
        rc2.columns = ["Rating", "Count"]
        if not rc2.empty:
            st.plotly_chart(
                px.pie(rc2, names="Rating", values="Count",
                       title=f"Rating Distribution – {sel_mentor_fb}", color="Rating",
                       color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}),
                use_container_width=True
            )
    else:
        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            top_fb = sum2.sort_values("Total Sessions", ascending=False).head(10)
            fig_top = px.bar(
                top_fb.melt(id_vars="Mentor", value_vars=["Good", "Average", "Poor"]),
                x="Mentor", y="value", color="variable", barmode="stack",
                title="Top 10 Mentors – Feedback Breakdown",
                color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}
            )
            st.plotly_chart(fig_top, use_container_width=True)
        with col_b:
            ov = fb_view["rating"].dropna().value_counts().reset_index()
            ov.columns = ["Rating", "Count"]
            st.plotly_chart(
                px.pie(ov, names="Rating", values="Count", title="Overall Rating Mix", color="Rating",
                       color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}),
                use_container_width=True
            )


# ╔══════════════════════════════════════════════════╗
# ║  TAB 3 – VENTURE-WISE FEEDBACK                  ║
# ╚══════════════════════════════════════════════════╝
with tab3:
    st.subheader("Venture-wise Feedback")

    with st.expander("🔍 Filters", expanded=True):
        vf1, vf2, vf3, vf4 = st.columns(4)
        vp3_vals = sorted({v for v in venture_program_map.values() if v and v not in ("nan", "")})
        sel_vp3  = vf1.selectbox("Venture Program", ["All"] + vp3_vals, key="vf_vprog")

        hub3_vals = sorted({h.strip() for h in venture_hub_map.values() if h and h not in ("nan", "")})
        sel_hub3  = vf2.selectbox("Hub", ["All"] + hub3_vals, key="vf_hub")

        exp_label_opts = ["😊 Positive", "😐 Mixed", "😟 Needs Attention"]
        sel_exp_labels = vf3.multiselect("Overall Experience", exp_label_opts, key="vf_explabel")

        sel_fb_cat3 = vf4.multiselect("Feedback Category", ["Good", "Average", "Poor"], key="vf_fbcat")

    fb_v = fb.copy()
    if sel_vp3 != "All":
        fb_v = fb_v[fb_v["venture_program"] == sel_vp3]
    if sel_hub3 != "All":
        fb_v = fb_v[fb_v["venture_hub"].str.contains(sel_hub3, na=False)]
    if sel_fb_cat3:
        fb_v = fb_v[fb_v["rating"].isin(sel_fb_cat3)]
    if sel_exp_labels:
        # Compute per-venture experience label and filter ventures matching selection
        tmp = fb_v.groupby("venture").agg(
            Good  =("rating", lambda x: (x == "Good").sum()),
            Poor  =("rating", lambda x: (x == "Poor").sum()),
            Total =("mentor", "count"),
        ).reset_index()
        tmp["Good_%"] = (tmp["Good"] / tmp["Total"].replace(0, pd.NA) * 100).round(1).fillna(0)
        def _exp(row):
            if row["Good_%"] >= 70: return "😊 Positive"
            if row["Poor"] >= 2:    return "😟 Needs Attention"
            return "😐 Mixed"
        tmp["exp_label"] = tmp.apply(_exp, axis=1)
        matching_ventures = tmp[tmp["exp_label"].isin(sel_exp_labels)]["venture"].tolist()
        fb_v = fb_v[fb_v["venture"].isin(matching_ventures)]

    # Stats
    st.markdown("---")
    venture_stats(fb_v)
    st.markdown("---")

    if fb_v.empty:
        st.info("ℹ️ No data matches the selected filters. Please adjust your filters.")
        st.stop()

    vent_sum = fb_v.groupby("venture").agg(
        Mentors_Connected=("mentor", "nunique"),
        Good    =("rating", lambda x: (x == "Good").sum()),
        Average =("rating", lambda x: (x == "Average").sum()),
        Poor    =("rating", lambda x: (x == "Poor").sum()),
        Total   =("mentor", "count"),
    ).reset_index()
    vent_sum["Good_%"]  = (vent_sum["Good"] / vent_sum["Total"].replace(0, pd.NA) * 100).round(1).fillna(0)
    vent_sum["Program"] = vent_sum["venture"].map(venture_program_map).fillna("—").replace("nan", "—")
    vent_sum["Hub"]     = vent_sum["venture"].map(venture_hub_map).fillna("—").replace("nan", "—")

    def overall_exp(row):
        if row["Total"] == 0:      return "—"
        if row["Good_%"] >= 70:    return "😊 Positive"
        if row["Poor"] >= 2:       return "😟 Needs Attention"
        return "😐 Mixed"
    vent_sum["Experience"] = vent_sum.apply(overall_exp, axis=1)

    disp_vs = vent_sum[["venture", "Program", "Hub", "Mentors_Connected",
                         "Good", "Average", "Poor", "Good_%", "Experience"]].rename(columns={
        "venture": "Venture", "Mentors_Connected": "Mentors Connected", "Good_%": "Good %"
    })
    st.caption(f"Showing {len(disp_vs)} ventures")
    st.dataframe(disp_vs, use_container_width=True, hide_index=True)

    cx, cy = st.columns(2)
    with cx:
        top_v = vent_sum.sort_values("Good_%", ascending=False).head(10)
        fig_vt = px.bar(top_v, x="venture", y="Good_%",
                        title="Top Ventures by % Good Ratings",
                        color_discrete_sequence=["#2ecc71"])
        fig_vt.update_layout(xaxis_tickangle=-30)
        st.plotly_chart(fig_vt, use_container_width=True)
    with cy:
        ec = vent_sum["Experience"].value_counts().reset_index()
        ec.columns = ["Experience", "Count"]
        st.plotly_chart(
            px.pie(ec, names="Experience", values="Count",
                   title="Venture Experience Distribution", color="Experience",
                   color_discrete_map={"😊 Positive": "#2ecc71", "😐 Mixed": "#f39c12",
                                       "😟 Needs Attention": "#e74c3c", "—": "#bdc3c7"}),
            use_container_width=True
        )

    # ── Venture Deep-dive ─────────────────────────────
    st.divider()
    st.markdown("#### 🔎 Venture Deep-dive")
    v_dd_opts   = ["— Select a Venture —"] + sorted(fb_v["venture"].dropna().unique().tolist())
    sel_venture = st.selectbox("Select Venture", v_dd_opts, key="vf_select")

    if sel_venture != "— Select a Venture —":
        v_rows = fb_v[fb_v["venture"] == sel_venture].copy()

        vc1, vc2, vc3, vc4 = st.columns(4)
        vc1.metric("Sessions",  len(v_rows))
        vc2.metric("Mentors",   v_rows["mentor"].nunique())
        vc3.metric("✅ Good",   int((v_rows["rating"] == "Good").sum()))
        vc4.metric("🔴 Poor",   int((v_rows["rating"] == "Poor").sum()))

        st.caption(
            f"**Program:** {venture_program_map.get(sel_venture, '—')}  |  "
            f"**Hub:** {venture_hub_map.get(sel_venture, '—')}"
        )

        st.markdown("##### Mentor Sessions")
        vd = v_rows.merge(
            final[["mentor", "linkedin", "skills"]],
            on="mentor", how="left"
        )[["mentor", "linkedin", "skills", "rating", "comment", "rn_remarks", "connected"]].rename(columns={
            "mentor": "Mentor", "linkedin": "LinkedIn", "skills": "Key Skills",
            "rating": "Rating", "comment": "Founder Comment",
            "rn_remarks": "RN Remarks", "connected": "Connected by Us",
        })
        st.dataframe(
            vd,
            column_config={"LinkedIn": st.column_config.LinkColumn("LinkedIn", display_text="🔗 Profile")},
            use_container_width=True, hide_index=True
        )

        mb = v_rows.groupby("mentor").agg(
            Good    =("rating", lambda x: (x == "Good").sum()),
            Average =("rating", lambda x: (x == "Average").sum()),
            Poor    =("rating", lambda x: (x == "Poor").sum()),
            Sessions=("mentor", "count"),
        ).reset_index()
        fig_mb = px.bar(
            mb.melt(id_vars="mentor", value_vars=["Good", "Average", "Poor"]),
            x="mentor", y="value", color="variable", barmode="stack",
            title=f"Mentor Ratings – {sel_venture}",
            labels={"mentor": "Mentor", "value": "Sessions", "variable": "Rating"},
            color_discrete_map={"Good": "#2ecc71", "Average": "#f39c12", "Poor": "#e74c3c"}
        )
        st.plotly_chart(fig_mb, use_container_width=True)

# ─────────────────────────────────────────────────────────
# DOWNLOAD
# ─────────────────────────────────────────────────────────
st.divider()
st.download_button(
    "⬇ Download Mentor Report",
    final.to_csv(index=False).encode(),
    "mentor_pool_report.csv", "text/csv"
)
