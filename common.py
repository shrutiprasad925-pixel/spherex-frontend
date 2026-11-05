import os
from urllib.parse import quote

import numpy as np
import requests
import streamlit as st


def _get_api_url():
    """Environment variable first, then Streamlit secrets, then the local default."""
    url = os.environ.get("API_URL")
    if not url:
        try:
            url = st.secrets["API_URL"]
        except Exception:  # no secrets file, or no such key
            url = None
    return (url or "http://127.0.0.1:8000").rstrip("/")


API_URL = _get_api_url()

# Chart colours, shared by every page. Hues are spread across the spectrum so
# each source class stays distinguishable on the dark background.
COLORS = {
    "High Proper Motion Star": "#6C8BFF",
    "Interstellar H2O Ice Feature": "#3DE0FF",
    "Circumstellar CO2 Ice Feature": "#B45CFF",
    "Dense Core CO Ice Feature": "#3DFFA0",
    "Photometric Transient / Variable Star": "#FFB547",
    "Detector Artifact / Spike": "#FF3D5A",
    "Quiescent Galaxy SED": "#9AA6D6",
}
STATUS_COLORS = {
    "Confirmed": "#3DFFA0",
    "Plausible Candidate": "#6C8BFF",
    "Likely Artifact": "#FF3D5A",
    "Unreviewed": "#9AA6D6",
}
# Wavelength ribbon: short wavelengths violet, long wavelengths infrared red
RIBBON = [
    [0.0, "#B45CFF"], [0.18, "#6C7BFF"], [0.36, "#3DE0FF"], [0.54, "#3DFFA0"],
    [0.72, "#FFD166"], [0.86, "#FF8A3D"], [1.0, "#FF2D55"],
]

TEXT = "#E9EDFF"
MUTED = "#8590C0"
GRID = "rgba(140,160,255,.13)"
CLEAR = "rgba(0,0,0,0)"
PANEL = "rgba(4,6,20,.55)"
FONT_BODY = "Instrument Sans, Helvetica, Arial, sans-serif"
FONT_MONO = "Martian Mono, ui-monospace, Menlo, monospace"

# Hide the Plotly toolbar; the charts sit inside the glass panels
PLOT_CONFIG = {"displayModeBar": False, "displaylogo": False}


def style_fig(fig, height=340, legend=True, title=None):
    """One shared look for every Plotly chart."""
    fig.update_layout(
        height=height,
        paper_bgcolor=CLEAR,
        plot_bgcolor=PANEL,
        font=dict(color=TEXT, family=FONT_BODY, size=12),
        margin=dict(l=18, r=18, t=52 if title else 24, b=18),
        title=dict(text=title, x=0.01, font=dict(size=14, color="#FFFFFF", family=FONT_BODY)) if title else None,
        legend=dict(
            bgcolor=CLEAR, orientation="h", yanchor="top", y=-0.16, x=0,
            font=dict(size=10, color="#B9C4EC"),
        ) if legend else dict(visible=False),
        hoverlabel=dict(
            bgcolor="#0B1030", bordercolor="#3DE0FF",
            font=dict(family=FONT_MONO, size=11, color=TEXT),
        ),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(140,160,255,.25)",
                     tickfont=dict(family=FONT_MONO, size=10, color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(140,160,255,.25)",
                     tickfont=dict(family=FONT_MONO, size=10, color=MUTED))
    return fig


@st.cache_data(ttl=30)
def backend_online():
    try:
        r = requests.get(f"{API_URL}/api/v1/health", timeout=60)
        return r.ok
    except requests.exceptions.RequestException:
        return False


@st.cache_data(ttl=60)
def load_candidates():
    response = requests.get(
        f"{API_URL}/api/v1/candidates",
        params={"page": 1, "page_size": 100},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["items"]


@st.cache_data(ttl=60)
def load_candidate_detail(candidate_id):
    response = requests.get(
        f"{API_URL}/api/v1/candidates/{quote(candidate_id, safe='')}",
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def angular_sep_arcmin(ra1, dec1, ra2, dec2):
    """Haversine angular separation between two sky positions, in arcminutes."""
    ra1, dec1, ra2, dec2 = map(np.radians, [ra1, dec1, ra2, dec2])
    a = np.sin((dec2 - dec1) / 2) ** 2 + np.cos(dec1) * np.cos(dec2) * np.sin((ra2 - ra1) / 2) ** 2
    return np.degrees(2 * np.arcsin(np.sqrt(a))) * 60