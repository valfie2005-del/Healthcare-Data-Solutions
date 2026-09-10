"""
apps.py
-------
Single-page Streamlit app, gated behind login/signup.

Flow:
1. If not logged in -> show Login/Sign Up tabs, halt (st.stop())
2. Once logged in -> show the search UI:
   a. User types a keyword
   b. Fetch top 50 articles from PubMed
   c. Save them to MySQL
   d. Run RAG ranking (position-weighted) to get top 10 relevant authors
   e. Display the top 10, with role (first/senior/co-author) shown
"""

import streamlit as st
from pubmed_fetcher import search_pubmed, fetch_articles
from db import setup_database, save_search_results, create_user, verify_user
from rag_engine import get_top_doctors

# Make sure the database/tables exist (safe to call every run)
setup_database()

st.set_page_config(page_title="Top Doctors Finder", page_icon="🩺", layout="centered")

# --- Custom CSS for the result cards ---
st.markdown("""
<style>
.doctor-card {
    background-color: #ffffff;
    border: 1px solid #e3e6eb;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.doctor-name { font-size: 1.05rem; font-weight: 700; color: #111827 !important; }
.doctor-title { margin-top: 8px; color: #374151 !important; font-style: italic; }
.doctor-score { margin-top: 6px; color: #6b7280 !important; font-size: 0.85rem; }
.rank-badge {
    display: inline-block; background-color: #2563eb; color: #ffffff !important;
    font-weight: 600; border-radius: 50%; width: 28px; height: 28px;
    text-align: center; line-height: 28px; margin-right: 10px;
}
.role-badge {
    display: inline-block; font-size: 0.75rem; font-weight: 600;
    padding: 2px 9px; border-radius: 12px; margin-left: 8px; vertical-align: middle;
}
.role-first { background-color: #dcfce7; color: #166534 !important; }
.role-senior { background-color: #dbeafe; color: #1e40af !important; }
.role-coauthor { background-color: #f3f4f6; color: #4b5563 !important; }
.role-sole { background-color: #fef9c3; color: #854d0e !important; }
</style>
""", unsafe_allow_html=True)

ROLE_STYLES = {
    "First author": "role-first",
    "Senior/last author": "role-senior",
    "Co-author": "role-coauthor",
    "Sole author": "role-sole",
}


# --- Login / Signup screen ---
def show_login_signup():
    """
    Renders the login/signup screen. Updates st.session_state directly
    when the user successfully logs in or signs up.
    """
    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        login_username = st.text_input("Username", key="login_user")
        login_password = st.text_input("Password", type="password", key="login_pass")

        if st.button("Log In"):
            if verify_user(login_username, login_password):
                st.session_state.logged_in = True
                st.session_state.username = login_username
                st.rerun()
            else:
                st.error("Invalid username or password.")

    with tab2:
        new_username = st.text_input("Choose a username", key="signup_user")
        new_password = st.text_input("Choose a password", type="password", key="signup_pass")
        confirm_password = st.text_input("Confirm password", type="password", key="signup_confirm")

        if st.button("Sign Up"):
            if not new_username or not new_password:
                st.warning("Please fill in all fields.")
            elif new_password != confirm_password:
                st.warning("Passwords do not match.")
            else:
                success = create_user(new_username, new_password)
                if success:
                    st.success("Account created! Please log in using the Login tab.")
                else:
                    st.error("That username is already taken.")


# --- THE GATE ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🩺 Top Doctors Finder")
    show_login_signup()
    st.stop()  # halts here - nothing below runs until logged in


# --- Sidebar: logged-in status + logout ---
with st.sidebar:
    st.write(f"Logged in as **{st.session_state.username}**")
    if st.button("Log Out"):
        st.session_state.logged_in = False
        st.rerun()


# --- Main search UI (only reached once logged in) ---
st.title("🩺 Top Doctors Finder")
st.caption("Enter a medical/research topic and get the top 10 most relevant authors, powered by PubMed + RAG.")

col1, col2 = st.columns([4, 1])
with col1:
    keyword = st.text_input(
        "Keyword",
        placeholder="e.g. breast cancer, immunotherapy, diabetes",
        label_visibility="collapsed"
    )
with col2:
    search_clicked = st.button("🔍 Search", use_container_width=True)

if search_clicked:
    if not keyword.strip():
        st.warning("Please enter a keyword.")
    else:
        progress = st.progress(0, text=f"Fetching articles for '{keyword}'...")
        pmid_list = search_pubmed(keyword)
        progress.progress(40, text="Saving results...")

        if not pmid_list:
            progress.empty()
            st.error("No articles found. Try a different keyword.")
        else:
            articles = fetch_articles(pmid_list)
            save_search_results(keyword, articles)

            progress.progress(70, text="Ranking authors by relevance (RAG)...")
            top_doctors = get_top_doctors(keyword, articles, top_n=10)
            progress.progress(100, text="Done!")
            progress.empty()

            if not top_doctors:
                st.warning("Found articles, but couldn't rank any authors (missing abstracts).")
            else:
                m1, m2, m3 = st.columns(3)
                m1.metric("Articles scanned", len(articles))
                m2.metric("Doctors ranked", len(top_doctors))
                m3.metric("Top score", f"{top_doctors[0]['score']:.2f}")

                st.subheader(f"Top {len(top_doctors)} Doctors for \u201c{keyword}\u201d")

                for i, doc in enumerate(top_doctors, start=1):
                    role_class = ROLE_STYLES.get(doc["role"], "role-coauthor")
                    st.markdown(f"""
                    <div class="doctor-card">
                        <span class="rank-badge">{i}</span>
                        <span class="doctor-name">{doc['author']}</span>
                        <span class="role-badge {role_class}">{doc['role']}</span>
                        <div class="doctor-title">📄 {doc['matched_title']}</div>
                        <div class="doctor-score">Relevance score: <b>{doc['score']:.3f}</b></div>
                    </div>
                    """, unsafe_allow_html=True)