from __future__ import annotations

import streamlit as st

from radigest_ui.cleanup import cleanup_old_work, maybe_cleanup_old_work

st.set_page_config(
    page_title="radigest",
    page_icon="🧬",
    layout="wide",
)


@st.cache_resource(show_spinner=False)
def _startup_cleanup() -> dict[str, int]:
    return cleanup_old_work()


_startup_cleanup()
maybe_cleanup_old_work()

PAGES = {
    "radigest": [
        st.Page("app_pages/home.py", title="Home", icon="🏠", url_path="home"),
        st.Page(
            "app_pages/design.py", title="Design pairs", icon="🧪", url_path="design"
        ),
        st.Page("app_pages/results.py", title="Results", icon="📊", url_path="results"),
    ]
}

pg = st.navigation(PAGES, position="sidebar", expanded=True)
pg.run()
