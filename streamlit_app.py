from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="radigest",
    page_icon="🧬",
    layout="wide",
)

PAGES = {
    "radigest": [
        st.Page("app_pages/home.py", title="Home", icon="🏠", url_path="home"),
        st.Page("app_pages/design.py", title="Design pairs", icon="🧪", url_path="design"),
        st.Page("app_pages/processing.py", title="Processing", icon="⚙️", url_path="processing"),
        st.Page("app_pages/results.py", title="Results", icon="📊", url_path="results"),
    ]
}

pg = st.navigation(PAGES, position="sidebar", expanded=True)
pg.run()
