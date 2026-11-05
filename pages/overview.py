import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from common import (
    COLORS, FONT_MONO, MUTED, PLOT_CONFIG, STATUS_COLORS, angular_sep_arcmin,
    load_candidates, style_fig,
)
from theme import panel_heading, render_deck, render_gallery, render_scale_strip, section


def sky_map(frame):
    """All-sky Mollweide map, the projection astronomers use for full-sky data."""
    fig = go.Figure()
    for cls, group in frame.groupby("scientific_interpretation"):
        colour = COLORS.get(str(cls), "#9AA6D6")
        lon = 180 - group["ra"]  # RA increases to the left on a sky map
        # soft halo under each marker
        fig.add_trace(go.Scattergeo(
            lon=lon, lat=group["dec"], mode="markers", hoverinfo="skip", showlegend=False,
            marker=dict(size=30, color=colour, opacity=0.16),
        ))
        fig.add_trace(go.Scattergeo(
            lon=lon, lat=group["dec"], mode="markers", name=str(cls),
            marker=dict(size=13, color=colour, opacity=1, line=dict(width=1.6, color="rgba(255,255,255,.9)")),
            text=group["candidate_id"],
            customdata=np.stack([
                group["ra"].to_numpy(),
                group["dec"].to_numpy(),
                group["validation_status"].astype(str).to_numpy(),
                group["displacement_significance_sigma"].to_numpy(),
            ], axis=-1),
            hovertemplate=(
                "<b>%{text}</b><br>RA %{customdata[0]:.3f}°  Dec %{customdata[1]:.3f}°"
                "<br>%{customdata[2]}<br>Motion %{customdata[3]:.2f}σ<extra></extra>"
            ),
        ))
    # right ascension in hours along the equator
    hours = [4, 8, 12, 16, 20]
    fig.add_trace(go.Scattergeo(
        lon=[180 - h * 15 for h in hours], lat=[0] * len(hours), mode="text",
        text=[f"{h}h" for h in hours], textposition="top center", hoverinfo="skip", showlegend=False,
        textfont=dict(family=FONT_MONO, size=10, color=MUTED),
    ))
    style_fig(fig, 470)
    fig.update_layout(margin=dict(l=4, r=4, t=4, b=4), legend=dict(
        orientation="h", y=-0.04, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=10, color="#B9C4EC"),
    ))
    fig.update_geos(
        projection_type="mollweide",
        bgcolor="rgba(0,0,0,0)",
        showland=False, showcoastlines=False, showcountries=False, showlakes=False,
        showocean=True, oceancolor="rgba(10,16,52,.75)",
        showframe=True, framecolor="rgba(61,224,255,.55)", framewidth=1.5,
        lonaxis=dict(showgrid=True, dtick=30, gridcolor="rgba(140,160,255,.2)"),
        lataxis=dict(showgrid=True, dtick=30, gridcolor="rgba(140,160,255,.2)"),
    )
    return fig


# -------------------- Fetch catalogue --------------------
try:
    items = load_candidates()
except requests.exceptions.RequestException:
    st.error("Cannot reach the SPHEREx backend. Start the FastAPI service on port 8000 and refresh this page.")
    st.stop()

if not items:
    st.warning("The backend returned an empty candidate catalogue.")
    st.stop()

full_df = pd.DataFrame(items).copy()
df = full_df.copy()

# Safe defaults for optional fields
for column, default in {
    "scientific_interpretation": "Unclassified",
    "validation_status": "Unreviewed",
    "has_quality_warnings": False,
    "quality_indicators": None,
    "bands_observed": None,
}.items():
    if column not in df:
        df[column] = default
    if column not in full_df:
        full_df[column] = default

# -------------------- Command deck --------------------
render_deck(full_df)

query = st.text_input(
    "Ask the catalogue",
    placeholder="Search by candidate ID, class or status, e.g. SPX-J0439, H2O or artifact",
    label_visibility="collapsed",
    key="cmd",
)

render_scale_strip()

# -------------------- Mission snapshot --------------------
section("Mission snapshot", "Counts for the full backend catalogue")
total = len(full_df)
ice_count = int(full_df["scientific_interpretation"].astype(str).str.contains("Ice", case=False).sum())
confirmed = int((full_df["validation_status"] == "Confirmed").sum())
warnings = int(full_df["has_quality_warnings"].fillna(False).astype(bool).sum())
plausible = int((full_df["validation_status"] == "Plausible Candidate").sum())
artifacts = int(full_df["scientific_interpretation"].astype(str).str.contains("Artifact", case=False).sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Detected candidates", total, help="Candidates currently returned by the backend.")
m2.metric("Ice-feature sources", ice_count, help="Candidates classified with a molecular ice feature.")
m3.metric("Confirmed", confirmed, help="Candidates currently marked Confirmed in the validation status.")
m4.metric("Quality warnings", warnings, help="Candidates carrying one or more quality warnings.")

# -------------------- Filters --------------------
st.sidebar.markdown("## Mission filters")
st.sidebar.caption("Narrow the candidate catalogue")
classification_options = ["All classifications"] + sorted(full_df["scientific_interpretation"].dropna().astype(str).unique().tolist())
classification = st.sidebar.selectbox("Scientific classification", classification_options)
status_options = ["All statuses"] + sorted(full_df["validation_status"].dropna().astype(str).unique().tolist())
status_choice = st.sidebar.selectbox("Validation status", status_options)
quality_only = st.sidebar.checkbox("Quality warnings only", value=False)

if classification != "All classifications":
    df = df[df["scientific_interpretation"] == classification]
if status_choice != "All statuses":
    df = df[df["validation_status"] == status_choice]
if query.strip():
    needle = query.strip()
    haystack = (
        df["candidate_id"].astype(str) + " " + df["scientific_interpretation"].astype(str) + " "
        + df["validation_status"].astype(str)
    )
    df = df[haystack.str.contains(needle, case=False, na=False, regex=False)]
if quality_only:
    df = df[df["has_quality_warnings"].fillna(False).astype(bool)]

st.sidebar.markdown("---")
st.sidebar.markdown("## Cone search")
use_cone = st.sidebar.checkbox("Search around a sky position")
if use_cone:
    cone_ra = st.sidebar.number_input("Right ascension (°)", 0.0, 360.0, 270.0, step=0.5, format="%.4f")
    cone_dec = st.sidebar.number_input("Declination (°)", -90.0, 90.0, -24.0, step=0.5, format="%.4f")
    cone_radius = st.sidebar.number_input("Radius (arcmin)", 0.1, 10800.0, 120.0, step=10.0)
    if not df.empty:
        df = df.copy()
        df["separation"] = angular_sep_arcmin(cone_ra, cone_dec, df["ra"], df["dec"])
        df = df[df["separation"] <= cone_radius]

st.caption(f"Showing **{len(df)} of {total}** candidates. The metrics above describe the complete backend catalogue.")

# -------------------- Gallery --------------------
section("Candidate gallery", "Open any source for its spectrum, epochs and blink comparison", anchor="gallery")
if df.empty:
    st.info("No candidates match the current filters. Clear the search box or a sidebar filter to see sources.")
else:
    render_gallery(df)

# -------------------- Visual analytics --------------------
section("Celestial field and classification", "Where the candidates sit and what they are", anchor="sky")

left, right = st.columns([1.65, 1], gap="large")

with left:
    panel_heading("Sky distribution", "Mollweide projection · RA in hours")
    if df.empty:
        st.info("No candidates match the current filters. Clear a filter in the sidebar to see sources.")
    else:
        st.plotly_chart(sky_map(df), use_container_width=True, theme=None, config=PLOT_CONFIG)

counts = full_df["scientific_interpretation"].fillna("Unclassified").value_counts().reset_index()
counts.columns = ["Source class", "Sources"]

with right:
    panel_heading("Source composition", "Whole catalogue")
    if not counts.empty:
        fig_donut = px.pie(
            counts, names="Source class", values="Sources", hole=.7,
            color="Source class", color_discrete_map=COLORS,
        )
        fig_donut.update_traces(
            textposition="outside", textinfo="percent", domain=dict(x=[0, .58]),
            marker=dict(line=dict(color="#05060F", width=3)),
            textfont=dict(family=FONT_MONO, size=10),
            hovertemplate="%{label}<br>%{value} sources (%{percent})<extra></extra>",
        )
        style_fig(fig_donut, 330)
        fig_donut.update_layout(
            margin=dict(l=8, r=8, t=24, b=12),
            legend=dict(orientation="v", x=.62, y=.5, yanchor="middle", font=dict(size=10, color="#B9C4EC"),
                        bgcolor="rgba(0,0,0,0)"),
            annotations=[dict(
                text=f"<b>{total}</b><br><span style='font-size:11px;color:{MUTED}'>sources</span>",
                x=.29, y=.5, xref="paper", yref="paper", showarrow=False,
                font=dict(family=FONT_MONO, size=26, color="#FFFFFF"),
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True, theme=None, config=PLOT_CONFIG)
    st.markdown(
        f"""<div class="mini-stat-grid"><div><b>{plausible}</b><span>Plausible candidates</span></div><div><b>{artifacts}</b><span>Artifact flags</span></div></div>""",
        unsafe_allow_html=True,
    )

# -------------------- Analysis charts --------------------
section("Signal diagnostics", "How strong the detections are", anchor="signals")
c_left, c_right = st.columns(2, gap="large")

with c_left:
    panel_heading("Classification counts", "All candidates")
    bar_counts = counts.sort_values("Sources", ascending=True)
    fig_bar = px.bar(
        bar_counts, x="Sources", y="Source class", orientation="h",
        color="Source class", color_discrete_map=COLORS, text="Sources",
    )
    fig_bar.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0,
                          textfont=dict(family=FONT_MONO, size=11, color="#FFFFFF"))
    style_fig(fig_bar, 360, legend=False)
    fig_bar.update_layout(bargap=.42)
    fig_bar.update_xaxes(dtick=1, title="Number of candidates")
    fig_bar.update_yaxes(title=None)
    st.plotly_chart(fig_bar, use_container_width=True, theme=None, config=PLOT_CONFIG)

with c_right:
    panel_heading("Significance space", "Dashed lines mark the detection thresholds")
    if not df.empty:
        fig_sig = px.scatter(
            df,
            x="displacement_significance_sigma",
            y="delta_brightness_significance_sigma",
            color="scientific_interpretation",
            hover_name="candidate_id",
            color_discrete_map=COLORS,
            labels={
                "displacement_significance_sigma": "Astrometric significance (σ)",
                "delta_brightness_significance_sigma": "Photometric significance (σ)",
                "scientific_interpretation": "Source class",
            },
        )
        fig_sig.update_traces(marker=dict(size=14, line=dict(width=1.4, color="rgba(255,255,255,.9)")))
        fig_sig.add_vline(x=3, line_dash="dash", line_color="rgba(255,138,61,.8)",
                          annotation_text="3σ motion", annotation_font=dict(color="#FF8A3D", size=10, family=FONT_MONO))
        fig_sig.add_hline(y=3.5, line_dash="dash", line_color="rgba(255,138,61,.8)",
                          annotation_text="3.5σ variability", annotation_font=dict(color="#FF8A3D", size=10, family=FONT_MONO))
        style_fig(fig_sig, 360, legend=False)
        fig_sig.update_xaxes(title="Displacement significance (σ)")
        fig_sig.update_yaxes(title="Brightness-change significance (σ)")
        st.plotly_chart(fig_sig, use_container_width=True, theme=None, config=PLOT_CONFIG)
    else:
        st.info("No candidates to plot with the selected filters.")

# -------------------- Validation overview --------------------
section("Validation and catalogue", "Review status and every record", anchor="catalogue")
v1, v2 = st.columns([.85, 1.4], gap="large")

with v1:
    panel_heading("Validation status", "Review pipeline")
    validation = full_df["validation_status"].fillna("Unreviewed").value_counts().reset_index()
    validation.columns = ["Status", "Count"]
    fig_validation = px.bar(
        validation, x="Status", y="Count", color="Status",
        color_discrete_map=STATUS_COLORS, text="Count",
    )
    fig_validation.update_traces(textposition="outside", cliponaxis=False, marker_line_width=0,
                                 textfont=dict(family=FONT_MONO, size=11, color="#FFFFFF"))
    style_fig(fig_validation, 320, legend=False)
    fig_validation.update_layout(bargap=.45)
    fig_validation.update_yaxes(title="Candidates", dtick=1)
    fig_validation.update_xaxes(title=None)
    st.plotly_chart(fig_validation, use_container_width=True, theme=None, config=PLOT_CONFIG)

with v2:
    panel_heading("Candidate catalogue", "Live backend records")
    display_columns = [
        "candidate_id", "scientific_interpretation", "validation_status",
        "displacement_significance_sigma", "delta_brightness_significance_sigma",
        "has_quality_warnings", "ra", "dec",
    ]
    if use_cone and "separation" in df.columns:
        display_columns.append("separation")
    display = df[[c for c in display_columns if c in df.columns]].copy()
    display = display.rename(columns={
        "candidate_id": "Candidate ID",
        "scientific_interpretation": "Scientific class",
        "validation_status": "Validation",
        "displacement_significance_sigma": "Motion σ",
        "delta_brightness_significance_sigma": "Brightness σ",
        "has_quality_warnings": "Quality warning",
        "ra": "RA (°)",
        "dec": "Dec (°)",
        "separation": "Separation (')",
    })
    if not display.empty:
        st.dataframe(
            display.style.format({
                "Motion σ": "{:.2f}",
                "Brightness σ": "{:.2f}",
                "RA (°)": "{:.4f}",
                "Dec (°)": "{:.4f}",
                "Separation (')": "{:.1f}",
            }),
            use_container_width=True,
            hide_index=True,
            height=310,
        )
        st.download_button(
            "Export filtered catalogue (CSV)",
            display.to_csv(index=False).encode("utf-8"),
            file_name="spherex_candidate_catalogue.csv",
            mime="text/csv",
        )
    else:
        st.info("No candidates match these filters.")

# -------------------- Scientific note --------------------
st.markdown(
    """<div class="science-note"><div class="science-note-mark">i</div><div><b>About this data</b><p>This project currently uses a seven-source synthetic seed catalogue modelled on SPHEREx mission design. The sky map shows these candidate coordinates only; it is not a full-sky SPHEREx survey map. Classification is deterministic, physics-based triage and should be treated as candidate interpretation rather than confirmation of source identity.</p></div></div>""",
    unsafe_allow_html=True,
)
