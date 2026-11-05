import streamlit as st

from common import backend_online
from theme import apply_theme, render_footer, render_header

st.set_page_config(page_title="SPHEREx Mission Explorer", page_icon="🌌", layout="wide", initial_sidebar_state="expanded")

apply_theme()
render_header(backend_online())

navigation = st.navigation(
    [
        st.Page("pages/overview.py", title="Overview", default=True),
        st.Page("pages/detail.py", title="Candidate Detail", url_path="detail"),
    ]
)
navigation.run()

render_footer()