
import base64

import io

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageChops, ImageOps

from common import (
    CLEAR, FONT_MONO, GRID, PANEL, PLOT_CONFIG, RIBBON, STATUS_COLORS, TEXT,
    load_candidate_detail, load_candidates, style_fig,
)
from theme import render_candidate_banner, section


# ============================================================
#  LOAD CANDIDATES
# ============================================================

try:
    items = load_candidates()
except requests.exceptions.RequestException:
    st.error("Cannot reach the backend. Is it running on port 8000?")
    st.stop()

labels = {
    c["candidate_id"]: (
        f'{c["candidate_id"]}  ·  {c["scientific_interpretation"]}'
    )
    for c in items
}

st.sidebar.markdown("## Candidate")

_ids = list(labels.keys())
_requested = st.query_params.get("candidate")
_start = _ids.index(_requested) if _requested in _ids else 0

selected = st.sidebar.selectbox(
    "Choose a candidate",
    _ids,
    index=_start,
    format_func=lambda i: labels[i]
)

try:
    detail = load_candidate_detail(selected)
except requests.exceptions.RequestException:
    st.error("Could not load this candidate from the backend.")
    st.stop()


# ============================================================
#  BANNER
# ============================================================

status = detail["validation_status"]
status_color = STATUS_COLORS.get(status, "#FFFFFF")

render_candidate_banner(
    candidate_id=detail["candidate_id"],
    interpretation=detail["scientific_interpretation"],
    status=status,
    status_color=status_color,
    ra=detail["ra"],
    dec=detail["dec"],
    summary=detail["scientific_summary"],
)


# ============================================================
#  SECTION 01 - KEY MEASUREMENTS
# ============================================================

section("Key measurements", "How far it moved and how much it changed")

m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "Displacement (arcsec)",
    f'{detail["displacement_arcsec"]:.4f}'
)

m2.metric(
    "Movement significance (σ)",
    f'{detail["displacement_significance_sigma"]:.2f}'
)

m3.metric(
    "Brightness change (mag)",
    f'{detail["delta_brightness_mag"]:.3f}'
)

m4.metric(
    "Brightness significance (σ)",
    f'{detail["delta_brightness_significance_sigma"]:.2f}'
)

flags = ", ".join(detail.get("quality_indicators") or [])

st.caption(f"Quality indicators: {flags or 'none'}")


# ============================================================
#  SECTION 02 - SPECTRUM
# ============================================================

section("Spectrum", "Flux across the 0.75 to 5.0 µm survey range")

spec = (
    pd.DataFrame(detail.get("spectrum") or [])
    .sort_values("wavelength_um")
    .reset_index(drop=True)
)

fig = go.Figure()

if not spec.empty:

    fig.add_trace(
        go.Scatter(
            x=spec["wavelength_um"],
            y=spec["flux_density_mjy"],
            mode="lines+markers",
            name="Spectrum",
            fill="tozeroy",
            fillcolor="rgba(61,224,255,.07)",
            line=dict(color="rgba(233,237,255,.55)", width=1.6),
            marker=dict(
                size=13,
                color=spec["wavelength_um"],
                colorscale=RIBBON,
                cmin=0.75,
                cmax=5.0,
                line=dict(width=1.5, color="white")
            ),
            error_y=dict(
                type="data",
                array=spec["flux_error_mjy"],
                color="rgba(233,237,255,.4)",
                thickness=1.3,
                width=5
            ),
            customdata=spec["band"],
            hovertemplate=(
                "%{x} µm<br>%{y} mJy<br>"
                "%{customdata}<extra></extra>"
            ),
        )
    )

    baseline_in_legend = False

    for feature in detail.get("ice_features") or []:

        center = feature["central_wavelength_um"]

        label = f'{feature["molecule"]} {center} µm'

        if feature["is_detected"]:

            fig.add_vrect(
                x0=center - 0.12,
                x1=center + 0.12,
                fillcolor="rgba(61,224,255,.14)",
                line_width=0
            )

            fig.add_vline(
                x=center,
                line_dash="dot",
                line_color="#3DE0FF",
                annotation_text=label,
                annotation_position="top",
                annotation_font_color="#3DE0FF"
            )

            below = spec[
                spec["wavelength_um"] < center - 0.05
            ].tail(1)

            above = spec[
                spec["wavelength_um"] > center + 0.05
            ].head(1)

            if not below.empty and not above.empty:

                fig.add_trace(
                    go.Scatter(
                        x=[
                            below["wavelength_um"].iloc[0],
                            above["wavelength_um"].iloc[0]
                        ],
                        y=[
                            below["flux_density_mjy"].iloc[0],
                            above["flux_density_mjy"].iloc[0]
                        ],
                        mode="lines",
                        line=dict(
                            color="#FFB547",
                            dash="dash",
                            width=1.5
                        ),
                        name="Neighbour baseline (illustrative)",
                        showlegend=not baseline_in_legend,
                        hoverinfo="skip",
                    )
                )

                baseline_in_legend = True

        else:

            fig.add_vline(
                x=center,
                line_dash="dot",
                line_color="rgba(255,255,255,.28)",
                annotation_text=label,
                annotation_position="top",
                annotation_font_color="rgba(255,255,255,.5)"
            )

    style_fig(fig, 520)
    fig.update_layout(
        xaxis_title="Wavelength (µm)",
        yaxis_title="Flux density (mJy)",
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.update_xaxes(range=[0.6, 5.2])
    fig.update_yaxes(rangemode="tozero")

    st.plotly_chart(fig, use_container_width=True, theme=None, config=PLOT_CONFIG)

else:
    st.info("No spectrum data is available.")

st.caption(
    "Shaded bands mark ice features detected by the backend. "
    "The dashed orange line is only a visual aid joining neighbouring "
    "points; it is not the backend's continuum fit."
)


# ============================================================
#  SECTION 03 - ICE ABSORPTION FEATURES
# ============================================================

section("Ice absorption features", "Detected and not detected")

ice = pd.DataFrame(detail.get("ice_features") or [])

if not ice.empty:

    ice["Result"] = ice["is_detected"].map({
        True: "Detected",
        False: "Not detected"
    })

    ice_table = ice[
        [
            "molecule",
            "central_wavelength_um",
            "band",
            "equivalent_width_um",
            "equivalent_width_uncertainty_um",
            "detection_significance_sigma",
            "Result"
        ]
    ].rename(
        columns={
            "molecule": "Molecule",
            "central_wavelength_um": "Centre (µm)",
            "band": "Band",
            "equivalent_width_um": "Equivalent width (µm)",
            "equivalent_width_uncertainty_um": "Uncertainty (µm)",
            "detection_significance_sigma": "Significance (σ)",
        }
    )

    def color_result(value):

        if value == "Detected":
            return (
                "background-color: rgba(61,255,160,.16); "
                "color: #3DFFA0; font-weight: 600"
            )

        return "color: #8590C0"

    st.dataframe(
        ice_table.style.map(
            color_result,
            subset=["Result"]
        ).format({
            "Equivalent width (µm)": "{:.4f}",
            "Uncertainty (µm)": "{:.4f}",
            "Significance (σ)": "{:.2f}"
        }),
        hide_index=True
    )

else:
    st.info("No ice absorption features are available.")

st.caption(
    "A feature counts as detected when its significance is at least "
    "3σ and its equivalent width is above 0.02 µm."
)


# ============================================================
#  SECTION 04 - OBSERVATION EPOCHS
# ============================================================

section("Observation epochs", "Every measurement of this source")

epoch_rows = detail.get("epochs") or []

if not epoch_rows:

    st.info("No per-epoch records are available for this candidate.")

else:

    epochs = pd.DataFrame(epoch_rows)

    if "quality_flags" in epochs.columns:

        epochs["quality_flags"] = epochs["quality_flags"].apply(
            lambda f: (
                ", ".join(f)
                if isinstance(f, list)
                else str(f)
            )
        )

    names = {
        "epoch_index": "Epoch",
        "observation_id": "Observation ID",
        "timestamp_utc": "Time (UTC)",
        "band": "Band",
        "flux_density_mjy": "Flux (mJy)",
        "flux_density_err_mjy": "Flux error (mJy)",
        "magnitude": "AB mag",
        "magnitude_err": "Mag error",
        "quality_flags": "Quality flags",
    }

    shown = [
        column for column in names
        if column in epochs.columns
    ]

    st.dataframe(
        epochs[shown].rename(columns=names),
        hide_index=True
    )


# ============================================================
#  SECTION 05 - ASTRONOMICAL BLINK COMPARATOR
# ============================================================

section("Blink comparator", "Spot changes between two epochs")

st.markdown(
    "Compare two observations of the same astronomical candidate "
    "to visually inspect changes across observation epochs."
)

cutouts = detail.get("cutout_thumbnails") or {}


def decode_cutout(value):

    if not isinstance(value, str) or not value:
        return None

    try:

        if value.startswith("data:") and "," in value:
            value = value.split(",", 1)[1]

        image_bytes = base64.b64decode(value, validate=True)

        return image_bytes

    except (ValueError, TypeError):
        return None


if not isinstance(cutouts, dict) or not cutouts:

    st.info(
        "No astronomical image cutouts are available "
        "for this candidate."
    )

else:

    first_image = decode_cutout(cutouts.get("epoch_1"))
    second_image = decode_cutout(cutouts.get("epoch_2"))

    if first_image and second_image:

        dates = detail.get("observation_dates") or []
        date1 = dates[0][:10] if len(dates) > 0 else "Date unavailable"
        date2 = dates[1][:10] if len(dates) > 1 else "Date unavailable"

        st.caption(
            "These are the actual cutouts returned by the SPHEREx backend. "
            "Pick a view below."
        )

        tab_blink, tab_side, tab_manual, tab_diff = st.tabs(
            ["Auto blink", "Side by side", "Manual switch", "Difference"]
        )

        # ---------------------------------------------
        # AUTOMATIC BLINK ANIMATION
        # ---------------------------------------------

        with tab_blink:

            st.caption(
                "The two epochs alternate automatically. "
                "Use Pause to hold a frame, and the slider to change speed."
            )

            image1_b64 = base64.b64encode(first_image).decode("utf-8")
            image2_b64 = base64.b64encode(second_image).decode("utf-8")

            blink_html = """
            <!DOCTYPE html>
            <html>
            <head>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600&family=Martian+Mono:wght@400;600&display=swap" rel="stylesheet">
            <style>
            :root { --ribbon: linear-gradient(90deg,#B45CFF,#6C7BFF,#3DE0FF,#3DFFA0,#FFD166,#FF8A3D,#FF2D55); }
            @property --ang { syntax: '<angle>'; inherits: false; initial-value: 0deg; }
            * { box-sizing: border-box; }
            body {
                margin: 0; padding: 6px;
                background: transparent; color: #E9EDFF;
                font-family: 'Instrument Sans', Arial, sans-serif;
                text-align: center;
            }
            .blink-container {
                position: relative; padding: 22px 20px 20px; border-radius: 18px;
                background: linear-gradient(160deg, rgba(18,24,58,.85), rgba(6,8,24,.9));
            }
            .blink-container::after {
                content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1.5px; pointer-events: none;
                background: conic-gradient(from var(--ang), #B45CFF, #3DE0FF, #3DFFA0, #FFD166, #FF2D55, #B45CFF);
                -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
                -webkit-mask-composite: xor; mask-composite: exclude;
                animation: ang 8s linear infinite;
            }
            @keyframes ang { to { --ang: 360deg; } }
            .epoch-label {
                display: inline-block; margin-bottom: 14px; padding: 5px 14px; border-radius: 999px;
                font-family: 'Martian Mono', monospace; font-size: 12px; font-weight: 600;
                color: #3DE0FF; border: 1px solid rgba(61,224,255,.6);
                box-shadow: 0 0 16px -4px #3DE0FF;
            }
            .frame { position: relative; display: inline-block; }
            .frame::before, .frame::after {
                content: ""; position: absolute; width: 22px; height: 22px; pointer-events: none;
                border: 2px solid #3DE0FF;
            }
            .frame::before { top: -7px; left: -7px; border-right: 0; border-bottom: 0; }
            .frame::after  { bottom: -7px; right: -7px; border-left: 0; border-top: 0; }
            .blink-image {
                display: block; width: 256px; height: 256px; max-width: 100%;
                object-fit: contain; image-rendering: pixelated;
                background: #04050B;
                box-shadow: 0 0 40px rgba(61,224,255,.2);
            }
            .date-label {
                margin-top: 14px; color: #B6C0EA;
                font-family: 'Martian Mono', monospace; font-size: 12px;
            }
            .controls { margin-top: 18px; display: flex; justify-content: center; align-items: center; gap: 18px; flex-wrap: wrap; }
            button {
                color: #fff; border: 1px solid transparent; padding: 9px 26px; border-radius: 10px;
                font: 600 14px 'Instrument Sans', Arial, sans-serif; cursor: pointer;
                background: linear-gradient(#0B1030, #0B1030) padding-box, var(--ribbon) border-box;
                transition: box-shadow .25s;
            }
            button:hover { box-shadow: 0 0 22px -2px rgba(108,123,255,.8); }
            button:focus-visible, input:focus-visible { outline: 2px solid #3DE0FF; outline-offset: 3px; }
            .speed-control { font-size: 13px; color: #B6C0EA; display: flex; align-items: center; gap: 10px; }
            .speed-control span { font-family: 'Martian Mono', monospace; font-size: 11px; min-width: 52px; text-align: left; }
            input[type=range] { width: 160px; accent-color: #3DE0FF; }
            .status { margin-top: 14px; font-size: 12px; color: #8590C0; }
            @media (prefers-reduced-motion: reduce) { * { animation: none !important; } }
            </style>
            </head>

            <body>

            <div class="blink-container">

                <div class="epoch-label" id="epochLabel">EPOCH 1</div>

                <div>
                    <div class="frame">
                        <img id="blinkImage" class="blink-image"
                             src="data:image/png;base64,__IMAGE1__"
                             alt="Astronomical observation">
                    </div>
                </div>

                <div class="date-label" id="dateLabel">__DATE1__</div>

                <div class="controls">
                    <button id="playButton" onclick="toggleBlink()">Pause</button>
                    <div class="speed-control">
                        <label for="speed">Blink interval</label>
                        <input type="range" id="speed" min="300" max="2000" step="100" value="800"
                               oninput="changeSpeed(this.value)">
                        <span id="speedValue">800 ms</span>
                    </div>
                </div>

                <div class="status" id="status" aria-live="polite">Animation playing</div>

            </div>

            <script>

            const images = [
                "data:image/png;base64,__IMAGE1__",
                "data:image/png;base64,__IMAGE2__"
            ];

            const dates = ["__DATE1__", "__DATE2__"];

            let currentEpoch = 0;
            let playing = true;
            let interval = null;
            let speed = 800;

            const imageElement = document.getElementById("blinkImage");
            const epochLabel = document.getElementById("epochLabel");
            const dateLabel = document.getElementById("dateLabel");
            const playButton = document.getElementById("playButton");
            const status = document.getElementById("status");

            function showEpoch() {
                imageElement.src = images[currentEpoch];
                epochLabel.textContent = "EPOCH " + (currentEpoch + 1);
                dateLabel.textContent = dates[currentEpoch];
            }

            function blink() {
                currentEpoch = 1 - currentEpoch;
                showEpoch();
            }

            function startBlink() {
                clearInterval(interval);
                interval = setInterval(blink, speed);
                playing = true;
                playButton.textContent = "Pause";
                status.textContent = "Animation playing";
            }

            function pauseBlink() {
                clearInterval(interval);
                playing = false;
                playButton.textContent = "Play";
                status.textContent = "Animation paused";
            }

            function toggleBlink() {
                if (playing) { pauseBlink(); } else { startBlink(); }
            }

            function changeSpeed(value) {
                speed = Number(value);
                document.getElementById("speedValue").textContent = speed + " ms";
                if (playing) { startBlink(); }
            }

            showEpoch();
            startBlink();

            </script>

            </body>
            </html>
            """

            blink_html = (
                blink_html
                .replace("__IMAGE1__", image1_b64)
                .replace("__IMAGE2__", image2_b64)
                .replace("__DATE1__", date1)
                .replace("__DATE2__", date2)
            )

            components.html(blink_html, height=500, scrolling=False)

        # ---------------------------------------------
        # SIDE-BY-SIDE COMPARISON
        # ---------------------------------------------

        with tab_side:

            col1, col2 = st.columns(2)

            with col1:
                st.image(first_image, caption=f"Epoch 1 · {date1}", use_container_width=True)

            with col2:
                st.image(second_image, caption=f"Epoch 2 · {date2}", use_container_width=True)

        # ---------------------------------------------
        # MANUAL IMAGE SWITCHING
        # ---------------------------------------------

        with tab_manual:

            selected_epoch = st.radio(
                "Select observation",
                ["Epoch 1", "Epoch 2"],
                horizontal=True,
                key=f"blink_{selected}"
            )

            if selected_epoch == "Epoch 1":
                st.image(first_image, caption=f"Epoch 1 · {date1}")
            else:
                st.image(second_image, caption=f"Epoch 2 · {date2}")

        # ---------------------------------------------
        # DIFFERENCE IMAGE (epoch 2 minus epoch 1)
        # ---------------------------------------------

        with tab_diff:

            st.caption(
                "Brighter pixels changed more between the two epochs. "
                "A moving or variable source shows up as a bright spot; "
                "a static source cancels out."
            )

            try:
                img1 = Image.open(io.BytesIO(first_image)).convert("L")
                img2 = Image.open(io.BytesIO(second_image)).convert("L")

                if img2.size != img1.size:
                    img2 = img2.resize(img1.size)

                diff = ImageOps.autocontrast(ImageChops.difference(img1, img2))
                diff = ImageOps.colorize(
                    diff, black="#04050B", mid="#B45CFF", white="#FFD166", midpoint=110
                )

                buffer = io.BytesIO()
                diff.save(buffer, format="PNG")

                d1, d2, d3 = st.columns([1, 1, 1])

                with d1:
                    st.image(first_image, caption=f"Epoch 1 · {date1}", use_container_width=True)

                with d2:
                    st.image(second_image, caption=f"Epoch 2 · {date2}", use_container_width=True)

                with d3:
                    st.image(buffer.getvalue(), caption="Difference", use_container_width=True)

            except Exception:
                st.info("A difference image could not be computed for these cutouts.")

    else:

        st.warning(
            "Two valid observation images were not found. "
            "Check the cutout_thumbnails data returned by the backend."
        )
