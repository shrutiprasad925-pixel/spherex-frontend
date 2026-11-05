"""SPHEREx Mission Explorer: visual system.

Design idea: SPHEREx reads the sky as a spectrum, so the whole interface is
built around one motif, the wavelength ribbon (violet at 0.75 µm through to
infrared red at 5 µm). It appears as the rotating hero border, the rail above
the header and footer, the section dividers, the tab underline and the
spectrum colouring on the detail chart. Everything else is a quiet glass HUD.
"""
import base64
import html as _esc
import html as _h
import math
import random
from urllib.parse import quote as _quote
from functools import lru_cache
from pathlib import Path

import streamlit as st

from common import API_URL, STATUS_COLORS

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _html(markup):
    """Strip indentation and blank lines.

    Markdown ends an HTML block at a blank line and treats 4-space indents as
    code, so any HTML sent through st.markdown has to be compacted first.
    """
    return "\n".join(line.strip() for line in markup.splitlines() if line.strip())


# ----------------------------------------------------------------------------
# Main stylesheet
# ----------------------------------------------------------------------------

MAIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600;800&family=Instrument+Sans:wght@400;500;600;700&family=Martian+Mono:wght@300;400;600&display=swap');

:root {
  --void: #04050B;
  --void-2: #090C20;
  --ink: #E9EDFF;
  --mute: #8590C0;
  --dim: #5A6491;
  --line: rgba(140,160,255,.16);
  --line-strong: rgba(140,160,255,.34);
  --glass: linear-gradient(160deg, rgba(18,24,58,.74), rgba(7,9,26,.8));
  --cyan: #3DE0FF;
  --violet: #B45CFF;
  --ir: #FF3D5A;
  --amber: #FFB547;
  --mint: #3DFFA0;
  /* The wavelength ribbon: short wavelength on the left, infrared on the right */
  --ribbon: linear-gradient(90deg, #B45CFF 0%, #6C7BFF 18%, #3DE0FF 36%, #3DFFA0 54%, #FFD166 72%, #FF8A3D 86%, #FF2D55 100%);
  --display: 'Unbounded', 'Instrument Sans', sans-serif;
  --body: 'Instrument Sans', Helvetica, Arial, sans-serif;
  --mono: 'Martian Mono', ui-monospace, Menlo, Consolas, monospace;
}

@property --ang { syntax: '<angle>'; inherits: false; initial-value: 0deg; }

html, body, [class*="css"], .stApp { font-family: var(--body); color: var(--ink); }
#MainMenu, footer, [data-testid="stDecoration"] { visibility: hidden; }
::selection { background: rgba(61,224,255,.35); color: #fff; }

/* ---------- Canvas: nebula + survey grid ---------- */
.stApp {
  background:
    radial-gradient(ellipse 60% 45% at 8% 6%,  rgba(60,70,255,.34), transparent 70%),
    radial-gradient(ellipse 50% 40% at 92% 20%, rgba(180,92,255,.24), transparent 70%),
    radial-gradient(ellipse 55% 45% at 80% 92%, rgba(255,61,90,.12), transparent 70%),
    radial-gradient(ellipse 50% 40% at 15% 85%, rgba(61,224,255,.12), transparent 70%),
    var(--void) !important;
  background-attachment: fixed !important;
}
.stApp::before {
  content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(130,150,255,.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(130,150,255,.05) 1px, transparent 1px);
  background-size: 56px 56px;
  -webkit-mask-image: radial-gradient(ellipse 80% 70% at 50% 25%, #000 20%, transparent 80%);
          mask-image: radial-gradient(ellipse 80% 70% at 50% 25%, #000 20%, transparent 80%);
}
[data-testid="stAppViewContainer"], [data-testid="stMain"],
header[data-testid="stHeader"] { background: transparent !important; }
.block-container { position: relative; z-index: 1; max-width: 1520px !important;
                   padding: 1.1rem 2.2rem 2rem !important; }

/* Thin scrollbars */
* { scrollbar-width: thin; scrollbar-color: #2B3470 transparent; }

/* Keyboard focus is always visible */
:focus-visible { outline: 2px solid var(--cyan) !important; outline-offset: 2px; }

/* ---------- Wavelength rail ---------- */
.rail {
  position: relative; height: 5px; overflow: hidden;
  background: repeating-linear-gradient(90deg, transparent 0 2px, var(--void) 2px 4px), var(--ribbon);
}
.rail::after {
  content: ""; position: absolute; top: 0; bottom: 0; width: 22%; left: -25%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.85), transparent);
  mix-blend-mode: overlay; animation: sweep 7s ease-in-out infinite;
}
@keyframes sweep { 0%, 15% { left: -25%; } 70%, 100% { left: 105%; } }

/* ---------- Top bar ---------- */
.topbar {
  display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  flex-wrap: wrap; margin-bottom: 1.1rem; overflow: hidden;
  background: rgba(6,8,22,.72); backdrop-filter: blur(14px);
  border: 1px solid var(--line); border-radius: 14px;
}
.topbar-inner { display: flex; justify-content: space-between; align-items: center;
                gap: 1rem; flex-wrap: wrap; width: 100%; padding: .85rem 1.3rem; }
.brand { display: flex; align-items: center; gap: .8rem; color: #fff;
         font-family: var(--display); font-weight: 800; font-size: 1.05rem; letter-spacing: .02em; }
.brand small { font-family: var(--body); font-weight: 500; font-size: .85rem;
               color: var(--mute); letter-spacing: 0; }
.mark { position: relative; width: 30px; height: 30px; border-radius: 50%; flex: none;
        background: conic-gradient(from var(--ang), #B45CFF, #3DE0FF, #3DFFA0, #FFD166, #FF2D55, #B45CFF);
        animation: ang 6s linear infinite; box-shadow: 0 0 18px rgba(61,224,255,.4); }
.mark::after { content: ""; position: absolute; inset: 6px; border-radius: 50%; background: var(--void); }
.right { display: flex; align-items: center; gap: 1.6rem; flex-wrap: wrap; }
.nav { display: flex; gap: .25rem; padding: .28rem; border: 1px solid var(--line-strong); border-radius: 999px;
       background: rgba(255,255,255,.03); box-shadow: 0 0 24px -8px rgba(61,224,255,.5); }
.nav a { color: var(--ink); text-decoration: none; font-size: .84rem; font-weight: 500;
         padding: .42rem 1.05rem; border-radius: 999px; transition: background .2s, color .2s, box-shadow .2s; }
.nav a:hover { background: rgba(61,224,255,.14); color: #fff; box-shadow: inset 0 0 0 1px rgba(61,224,255,.6); }
.status { display: inline-flex; align-items: center; gap: .55rem; padding: .35rem .8rem;
          font-family: var(--mono); font-size: .68rem; color: var(--mute);
          border: 1px solid var(--line); border-radius: 999px; background: rgba(255,255,255,.02); }
.dot { width: 8px; height: 8px; border-radius: 50%; animation: pulse 2s infinite; }
.dot.on  { background: var(--mint); box-shadow: 0 0 10px var(--mint); }
.dot.off { background: var(--ir);   box-shadow: 0 0 10px var(--ir); }
@keyframes pulse { 50% { opacity: .35; } }
@keyframes ang   { to { --ang: 360deg; } }
@keyframes spin  { to { transform: rotate(360deg); } }

/* ---------- Hero ---------- */
.hero {
  position: relative; overflow: hidden; border-radius: 22px; color: #fff;
  display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, .9fr);
  align-items: center; gap: 1.5rem; padding: 3.4rem 3.4rem 2.2rem;
  background:
    radial-gradient(ellipse 50% 70% at 80% 40%, rgba(46,60,220,.5), transparent 70%),
    radial-gradient(ellipse 40% 50% at 10% 100%, rgba(180,92,255,.2), transparent 70%),
    linear-gradient(130deg, rgba(4,5,14,.92), rgba(9,12,34,.9));
  box-shadow: 0 30px 80px rgba(0,0,0,.5);
}
/* spectral border that travels around the card */
.hero::after {
  content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1.5px; pointer-events: none;
  background: conic-gradient(from var(--ang), #B45CFF, #6C7BFF, #3DE0FF, #3DFFA0, #FFD166, #FF8A3D, #FF2D55, #B45CFF);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
  animation: ang 9s linear infinite;
}
.hero-copy { position: relative; z-index: 2; }
.hero .kicker { max-width: 520px; font-family: var(--mono); font-size: .66rem; line-height: 1.9;
                color: var(--cyan); font-weight: 400; }
.hero h1 { margin: .9rem 0 1.1rem; padding: 0; color: #fff !important;
           font-family: var(--display); font-weight: 800; letter-spacing: -.025em;
           font-size: clamp(2.1rem, 3.9vw, 3.7rem); line-height: 1.04; }
.hero p { max-width: 520px; margin: 0; color: #B6C0EA; font-size: 1.04rem; line-height: 1.65; }
.hero-tags { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.5rem; }
.hero-tags span { display: inline-flex; align-items: center; gap: .5rem; padding: .42rem .85rem;
                  font-family: var(--mono); font-size: .66rem; color: #D5DCFF;
                  border: 1px solid var(--line-strong); border-radius: 999px;
                  background: rgba(8,12,34,.6); }
.hero-tags span::before { content: ""; width: 14px; height: 3px; border-radius: 2px; background: var(--ribbon); }

/* Wavelength scale: where each ice absorbs, on the 0.75 to 5.0 µm axis */
.scale { grid-column: 1 / -1; position: relative; z-index: 2; margin-top: 1.2rem; padding-top: 2rem; }
.scale-bar { position: relative; height: 10px; border-radius: 6px; background: var(--ribbon);
             box-shadow: 0 0 24px rgba(108,123,255,.35); }
.scale-bar::after { content: ""; position: absolute; inset: 0; border-radius: inherit;
                    background: repeating-linear-gradient(90deg, transparent 0 3px, rgba(4,5,11,.62) 3px 4px); }
.ice { position: absolute; bottom: 10px; transform: translateX(-50%); text-align: center; z-index: 3;
       font-family: var(--mono); font-size: .64rem; color: #fff; white-space: nowrap; }
.ice::after { content: ""; display: block; width: 1px; height: 26px; margin: 4px auto 0;
              background: linear-gradient(#fff, transparent); }
.ice b { display: inline-block; padding: .2rem .5rem; border-radius: 4px; font-weight: 600;
         background: rgba(4,5,11,.85); border: 1px solid var(--line-strong); }
.ticks { display: flex; justify-content: space-between; margin-top: .5rem;
         font-family: var(--mono); font-size: .62rem; color: var(--dim); }

/* Survey globe: pure CSS, no images */
.globe-wrap { position: relative; z-index: 1; width: 420px; height: 420px; margin: 0 auto; }
.globe { position: absolute; inset: 11%; border-radius: 50%; overflow: hidden;
         background: radial-gradient(circle at 34% 28%, #26389A 0%, #0C1344 48%, #04050B 100%);
         box-shadow: 0 0 70px rgba(61,224,255,.28), inset 0 0 40px rgba(4,5,11,.9),
                     inset -22px -18px 50px rgba(180,92,255,.16); }
.tilt { position: absolute; inset: 0; transform: rotate(-20deg); }
.mer, .lat { position: absolute; border-radius: 50%; border: 1px solid rgba(150,175,255,.3); }
.mer { inset: 0; animation: meridian 14s cubic-bezier(.37,0,.63,1) infinite; }
.lat { left: 0; right: 0; margin: auto; }
.lat.eq { border-color: rgba(61,224,255,.75); box-shadow: 0 0 10px rgba(61,224,255,.35); }
@keyframes meridian { 0%, 100% { transform: scaleX(.02); } 50% { transform: scaleX(1); } }
.sweep { position: absolute; inset: 0; border-radius: 50%; mix-blend-mode: screen;
         background: conic-gradient(from 0deg, transparent 0 300deg, rgba(61,224,255,.5) 360deg);
         -webkit-mask: radial-gradient(circle, transparent 8%, #000 70%);
                 mask: radial-gradient(circle, transparent 8%, #000 70%);
         animation: spin 6s linear infinite; }
.ping { position: absolute; width: 10px; height: 10px; margin: -5px 0 0 -5px; border-radius: 50%;
        background: var(--c); box-shadow: 0 0 12px var(--c); }
.ping::after { content: ""; position: absolute; inset: -4px; border-radius: 50%;
               border: 1px solid var(--c); animation: ping 3s ease-out infinite; animation-delay: var(--d); }
@keyframes ping { 0% { transform: scale(.6); opacity: 1; } 100% { transform: scale(4); opacity: 0; } }
.orbit { position: absolute; left: 0; right: 0; top: 50%; height: 30%; margin-top: -15%;
         border: 1px dashed rgba(180,200,255,.28); border-radius: 50%; transform: rotate(-20deg); }
.sat { position: absolute; left: 50%; top: 50%; width: 0; height: 0; }
.sat-x { animation: satx 9s cubic-bezier(.37,0,.63,1) infinite alternate; }
.sat-y { animation: saty 9s cubic-bezier(.37,0,.63,1) infinite alternate; animation-delay: -4.5s; }
.sat i { position: absolute; width: 9px; height: 9px; margin: -4.5px 0 0 -4.5px; border-radius: 50%;
         background: #fff; box-shadow: 0 0 14px 3px rgba(255,255,255,.7), 0 0 30px 8px rgba(255,61,90,.5); }
@keyframes satx { from { transform: translateX(-210px); } to { transform: translateX(210px); } }
@keyframes saty { from { transform: translateY(-63px); }  to { transform: translateY(63px); } }

@media (max-width: 1100px) {
  .hero { grid-template-columns: 1fr; padding: 2.2rem 1.4rem 1.6rem; }
  .globe-wrap { display: none; }
  .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
  .ice { font-size: .55rem; }
  .ice:nth-child(2) { transform: translateX(-85%); }
  .ice:nth-child(3) { transform: translateX(-8%); }
}

/* ---------- Ticker ---------- */
.ticker { overflow: hidden; white-space: nowrap; margin: 1rem 0 0;
          border: 1px solid var(--line); border-radius: 12px; background: rgba(6,8,22,.7);
          -webkit-mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent);
                  mask-image: linear-gradient(90deg, transparent, #000 6%, #000 94%, transparent); }
.track { display: inline-block; padding: .7rem 0; animation: scroll 55s linear infinite; }
.ticker:hover .track { animation-play-state: paused; }
.tick { display: inline-flex; align-items: center; gap: .6rem; margin: 0 1.7rem;
        font-size: .8rem; color: #C2CAEE; }
.tick i { width: 7px; height: 7px; border-radius: 50%; background: var(--c, var(--cyan)); box-shadow: 0 0 9px var(--c, var(--cyan)); }
.tick b { font-family: var(--mono); font-weight: 600; font-size: .72rem; color: #fff; }
@keyframes scroll { to { transform: translateX(-50%); } }

/* ---------- Section headings ---------- */
.section { display: flex; align-items: center; gap: 1.2rem; margin: 3rem 0 1.1rem; }
.section h2 { margin: 0; padding: 0; color: #fff; white-space: nowrap;
              font-family: var(--display); font-weight: 600; font-size: 1.15rem; letter-spacing: -.01em; }
.section p { margin: 0; color: var(--mute); font-size: .85rem; white-space: nowrap; }
.section::after { content: ""; flex: 1; height: 4px; min-width: 40px;
  background: repeating-linear-gradient(90deg, transparent 0 2px, var(--void) 2px 4px), var(--ribbon);
  -webkit-mask-image: linear-gradient(90deg, #000, transparent); mask-image: linear-gradient(90deg, #000, transparent);
  opacity: .8; }
@media (max-width: 700px) { .section p { display: none; } }

/* ---------- Panels (HUD brackets on glass) ---------- */
.panel-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem;
                 margin: .2rem 0 .6rem; padding-bottom: .55rem; border-bottom: 1px solid var(--line); }
.panel-heading span { color: #fff; font-weight: 600; font-size: .98rem; }
.panel-heading small { color: var(--dim); font-family: var(--mono); font-size: .62rem; text-align: right; }

div[data-testid="stPlotlyChart"], div[data-testid="stMetric"], .mini-stat-grid > div,
.science-note, .summary, [data-testid="stDataFrame"], [data-testid="stImage"] {
  position: relative;
}
div[data-testid="stPlotlyChart"] {
  border: 1px solid var(--line); border-radius: 16px; padding: .5rem;
  background: var(--glass); box-shadow: 0 18px 44px rgba(0,0,0,.35), inset 0 1px 0 rgba(255,255,255,.04);
}
/* four corner ticks, drawn with gradients so no extra markup is needed */
div[data-testid="stPlotlyChart"]::before, [data-testid="stImage"]::before {
  content: ""; position: absolute; inset: 7px; z-index: 2; pointer-events: none;
  --k: var(--line-strong);
  background:
    linear-gradient(var(--k), var(--k)) top left / 14px 1px no-repeat,
    linear-gradient(var(--k), var(--k)) top left / 1px 14px no-repeat,
    linear-gradient(var(--k), var(--k)) top right / 14px 1px no-repeat,
    linear-gradient(var(--k), var(--k)) top right / 1px 14px no-repeat,
    linear-gradient(var(--k), var(--k)) bottom left / 14px 1px no-repeat,
    linear-gradient(var(--k), var(--k)) bottom left / 1px 14px no-repeat,
    linear-gradient(var(--k), var(--k)) bottom right / 14px 1px no-repeat,
    linear-gradient(var(--k), var(--k)) bottom right / 1px 14px no-repeat;
}

/* ---------- Metrics ---------- */
div[data-testid="stMetric"] {
  --accent: var(--cyan); overflow: hidden; min-height: 122px;
  padding: 1.15rem 1.3rem 1.2rem; border-radius: 16px;
  border: 1px solid var(--line); background: var(--glass); backdrop-filter: blur(10px);
  box-shadow: 0 14px 34px rgba(0,0,0,.28); transition: border-color .25s, box-shadow .25s;
}
div[data-testid="stMetric"]::before { content: ""; position: absolute; left: 0; top: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--accent), transparent 75%); }
div[data-testid="stMetric"]::after { content: ""; position: absolute; right: -36px; top: -36px;
  width: 130px; height: 130px; border-radius: 50%; opacity: .2; pointer-events: none;
  background: radial-gradient(circle, var(--accent), transparent 68%); }
div[data-testid="stMetric"]:hover { border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent), 0 0 30px -4px var(--accent); }
[data-testid="stHorizontalBlock"] > div:nth-child(1) div[data-testid="stMetric"] { --accent: #3DE0FF; }
[data-testid="stHorizontalBlock"] > div:nth-child(2) div[data-testid="stMetric"] { --accent: #B45CFF; }
[data-testid="stHorizontalBlock"] > div:nth-child(3) div[data-testid="stMetric"] { --accent: #3DFFA0; }
[data-testid="stHorizontalBlock"] > div:nth-child(4) div[data-testid="stMetric"] { --accent: #FF8A3D; }
div[data-testid="stMetricLabel"] { color: var(--mute) !important; font-size: .82rem !important; font-weight: 500; }
div[data-testid="stMetricLabel"] p { font-size: .82rem !important; }
div[data-testid="stMetricValue"] { font-family: var(--mono) !important; font-weight: 600 !important;
  font-size: 2.35rem !important; line-height: 1.25; color: #fff !important;
  background: linear-gradient(180deg, #fff 30%, color-mix(in srgb, var(--accent) 60%, #fff));
  -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }

.mini-stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; margin-top: .75rem; }
.mini-stat-grid > div { padding: .9rem 1rem; border: 1px solid var(--line); border-radius: 14px; background: var(--glass); }
.mini-stat-grid b { display: block; color: #fff; font-family: var(--mono); font-weight: 600; font-size: 1.7rem; }
.mini-stat-grid span { color: var(--mute); font-size: .78rem; }

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, rgba(8,11,30,.96), rgba(5,6,18,.98)) !important;
  border-right: 2px solid; border-image: linear-gradient(180deg, #B45CFF, #3DE0FF, #3DFFA0, #FFD166, #FF2D55) 1;
}
section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
  font-family: var(--display); font-weight: 600; font-size: .95rem; letter-spacing: -.01em; color: #fff; }
section[data-testid="stSidebar"] label, section[data-testid="stSidebar"] label p { color: #B9C4EC !important; font-size: .85rem; }
a[data-testid="stSidebarNavLink"] { border-radius: 10px; margin: 2px 0; transition: background .2s; }
a[data-testid="stSidebarNavLink"]:hover { background: rgba(61,224,255,.08); }
a[data-testid="stSidebarNavLink"][aria-current="page"] {
  background: linear-gradient(90deg, rgba(61,224,255,.18), transparent); box-shadow: inset 3px 0 0 var(--cyan); }

/* ---------- Inputs ---------- */
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, div[data-baseweb="base-input"],
[data-testid="stNumberInput"] input, [data-testid="stTextInput"] input {
  background: rgba(4,6,20,.9) !important; border-color: var(--line-strong) !important; border-radius: 10px !important; }
div[data-baseweb="select"] > div:focus-within, div[data-baseweb="input"]:focus-within > div {
  border-color: var(--cyan) !important; box-shadow: 0 0 0 3px rgba(61,224,255,.18) !important; }
[data-testid="stSidebar"] input::placeholder { color: var(--dim); }

/* ---------- Buttons ---------- */
.stButton > button, [data-testid="stDownloadButton"] > button {
  border: 1px solid transparent !important; border-radius: 10px !important; color: #fff !important;
  font-weight: 600; padding: .55rem 1.1rem;
  background: linear-gradient(#0B1030, #0B1030) padding-box, var(--ribbon) border-box !important;
  transition: box-shadow .25s, transform .15s;
}
.stButton > button:hover, [data-testid="stDownloadButton"] > button:hover {
  box-shadow: 0 0 26px -2px rgba(108,123,255,.7); }
.stButton > button:active, [data-testid="stDownloadButton"] > button:active { transform: scale(.97); }

/* ---------- Tabs ---------- */
[data-baseweb="tab-list"] { gap: .4rem; }
button[data-baseweb="tab"] { background: transparent; color: var(--mute); font-weight: 600; padding: .6rem 1rem; }
button[data-baseweb="tab"][aria-selected="true"] { color: #fff; }
[data-baseweb="tab-highlight"] { height: 3px !important; background: var(--ribbon) !important; }
[data-baseweb="tab-border"] { background: var(--line) !important; }

/* ---------- Content blocks ---------- */
h3 { font-family: var(--display) !important; font-weight: 600 !important; font-size: 1rem !important; color: #fff; letter-spacing: -.01em; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--mute) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
  box-shadow: 0 14px 34px rgba(0,0,0,.3); }
[data-testid="stImage"] img { border-radius: 10px; border: 1px solid var(--line-strong); image-rendering: pixelated; }
[data-testid="stImage"] { padding: .5rem; border: 1px solid var(--line); border-radius: 16px; background: var(--glass); }
[data-testid="stAlert"] { border-radius: 12px; border: 1px solid var(--line-strong); background: rgba(12,17,46,.7); }
hr { border-color: var(--line) !important; }

.summary { margin-top: 1rem; padding: 1.1rem 1.4rem; border-radius: 14px; color: #BFC9F0; line-height: 1.65;
           border: 1px solid var(--line); background: var(--glass); }
.summary::before { content: ""; position: absolute; left: 0; top: 14px; bottom: 14px; width: 3px;
                   border-radius: 3px; background: linear-gradient(#B45CFF, #3DE0FF); }

.pill { display: inline-flex; align-items: center; gap: .5rem; padding: .35rem .8rem; border-radius: 999px;
        font-size: .8rem; font-weight: 600; color: var(--c); border: 1px solid var(--c);
        background: rgba(4,5,11,.55); box-shadow: 0 0 18px -6px var(--c); }
.pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--c); box-shadow: 0 0 8px var(--c); }
.coords { font-family: var(--mono); font-size: .76rem; color: var(--mute); }

.hero.compact { grid-template-columns: 1fr; padding: 2.4rem 2.8rem; }
.hero.compact h1 { font-family: var(--mono); font-weight: 600; letter-spacing: -.03em;
                   font-size: clamp(1.8rem, 3.2vw, 2.9rem); margin: .6rem 0 1rem; }
.hero.compact .row { display: flex; flex-wrap: wrap; align-items: center; gap: .9rem 1.2rem; }

.science-note { display: flex; gap: 1rem; margin-top: 2.4rem; padding: 1.15rem 1.4rem; border-radius: 14px;
                border: 1px solid var(--line); background: var(--glass); color: #AAB5DD; }
.science-note-mark { flex: 0 0 28px; height: 28px; border-radius: 50%; display: grid; place-items: center;
                     font-family: var(--mono); font-weight: 600; color: var(--cyan);
                     border: 1px solid var(--cyan); box-shadow: 0 0 14px -2px var(--cyan); }
.science-note b { color: #fff; font-size: .9rem; }
.science-note p { margin: .35rem 0 0; font-size: .84rem; line-height: 1.65; color: #95A2CE; }

/* ---------- Footer ---------- */
.sitefooter { position: relative; margin-top: 4rem; overflow: hidden; border-radius: 22px 22px 0 0;
  border: 1px solid var(--line); border-bottom: 0; background: rgba(5,6,18,.85); }
.sitefooter-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 2.2rem; padding: 2.4rem 2.2rem 1.4rem; position: relative; z-index: 1; }
.sitefooter h4 { margin: 0 0 .7rem; font-family: var(--display); font-weight: 600; font-size: .9rem; color: #fff; letter-spacing: -.01em; }
.sitefooter p, .sitefooter li { color: #8F9BC8; font-size: .86rem; line-height: 1.75; margin: 0; }
.sitefooter ul { list-style: none; padding: 0; margin: 0; }
.sitefooter a { color: #9FB6FF; text-decoration: none; }
.sitefooter a:hover { color: var(--cyan); text-decoration: underline; }
.wordmark { position: absolute; right: -1rem; bottom: -2.2rem; z-index: 0; pointer-events: none; user-select: none;
  font-family: var(--display); font-weight: 800; font-size: clamp(4rem, 12vw, 10rem); letter-spacing: -.04em;
  color: transparent; -webkit-text-stroke: 1px rgba(140,160,255,.09); }
.legal { position: relative; z-index: 1; padding: .9rem 2.2rem 1.4rem; color: var(--dim); font-size: .75rem; border-top: 1px solid var(--line); }
@media (max-width: 900px) { .sitefooter-grid { grid-template-columns: 1fr; } }

.banner-img { position: absolute; inset: 0; z-index: 0; background-size: cover; background-position: center; opacity: .6;
              -webkit-mask-image: linear-gradient(90deg, transparent 5%, #000 80%); mask-image: linear-gradient(90deg, transparent 5%, #000 80%); }
.hero.compact .hero-copy { z-index: 2; }
.scale-card { margin-top: 1rem; padding: 1.2rem 1.6rem 1rem; border: 1px solid var(--line); border-radius: 18px; background: var(--glass); }
.scale-card .scale { margin-top: 0; padding-top: 2.2rem; }
.scale-card h4 { margin: 0; color: #fff; font-size: .95rem; font-weight: 600; }
.scale-card p { margin: .2rem 0 0; color: var(--mute); font-size: .82rem; }

/* ---------- Motion preferences ---------- */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
"""


# ----------------------------------------------------------------------------
# Starfield (kept from the original, retuned for the new palette)
# ----------------------------------------------------------------------------


def star_shadows(count, seed):
    """Random star positions written as a CSS box-shadow list."""
    rnd = random.Random(seed)
    palette = ["#FFFFFF", "#CFE3FF", "#FFE9C4", "#E3CFFF"]
    return ", ".join(
        f"{rnd.randint(0, 2400)}px {rnd.randint(0, 2000)}px {rnd.choice(palette)}"
        for _ in range(count)
    )


STARS_CSS = """
<style>
.stars { position: fixed; top: 0; left: 0; z-index: -1; pointer-events: none; border-radius: 50%; }
.stars::after { content: ""; position: absolute; top: 2000px; left: 0;
                width: inherit; height: inherit; border-radius: 50%; }
.s1 { width: 1px; height: 1px; --sh: __S1__; box-shadow: var(--sh);
      animation: drift 240s linear infinite; }
.s2 { width: 2px; height: 2px; --sh: __S2__; box-shadow: var(--sh);
      animation: drift 150s linear infinite, twinkle 5s ease-in-out infinite alternate; }
.s3 { width: 3px; height: 3px; --sh: __S3__; box-shadow: var(--sh);
      animation: drift 90s linear infinite, twinkle 3s ease-in-out infinite alternate; }
.s1::after, .s2::after, .s3::after { box-shadow: var(--sh); }
@keyframes drift   { to { transform: translateY(-2000px); } }
@keyframes twinkle { from { opacity: .35; } to { opacity: 1; } }

.shoot { position: fixed; z-index: -1; width: 150px; height: 2px; border-radius: 2px;
         opacity: 0; pointer-events: none;
         background: linear-gradient(90deg, rgba(61,224,255,0), #fff);
         transform: rotate(30deg); animation: shoot 12s linear infinite; }
@keyframes shoot {
    0%   { opacity: 0; transform: translate(0, 0) rotate(30deg); }
    1%   { opacity: 1; }
    6%   { opacity: 0; transform: translate(520px, 300px) rotate(30deg); }
    100% { opacity: 0; transform: translate(520px, 300px) rotate(30deg); }
}
</style>
""".replace("__S1__", star_shadows(380, 1)).replace(
    "__S2__", star_shadows(130, 2)
).replace("__S3__", star_shadows(45, 3))

STARS_HTML = (
    '<div class="stars s1"></div><div class="stars s2"></div><div class="stars s3"></div>'
    '<div class="shoot" style="top:6vh; left:48vw; animation-delay:2s"></div>'
    '<div class="shoot" style="top:22vh; left:12vw; animation-delay:6s; animation-duration:15s"></div>'
    '<div class="shoot" style="top:3vh; left:78vw; animation-delay:10s; animation-duration:18s"></div>'
)


def apply_theme():
    """Inject the full visual system and the animated starfield."""
    st.markdown(MAIN_CSS, unsafe_allow_html=True)
    st.markdown(DECK_CSS, unsafe_allow_html=True)
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)
    st.markdown(_image_css(), unsafe_allow_html=True)
    st.markdown(STARS_CSS + STARS_HTML, unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Components
# ----------------------------------------------------------------------------


def render_header(online):
    st.markdown(
        _html(
            f"""
            <div class="topbar">
              <div class="rail"></div>
              <div class="topbar-inner">
                <div class="brand"><span class="mark"></span>SPHEREx <small>Mission Explorer</small></div>
                <div class="right">
                  <div class="nav">
                    <a href="{API_URL}/docs" target="_blank" rel="noopener">API docs</a>
                    <a href="https://spherex.caltech.edu" target="_blank" rel="noopener">Mission site</a>
                    <a href="https://github.com/Arnyz17/spherex-backend" target="_blank" rel="noopener">Source</a>
                  </div>
                  <div class="status"><span class="dot {'on' if online else 'off'}"></span>{'backend online' if online else 'backend offline'}</div>
                </div>
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_candidate_banner(candidate_id, interpretation, status, status_color, ra, dec, summary):
    key = class_key(interpretation)
    st.markdown(
        _html(
            f"""
            <div class="hero compact has-art im-{key}">
              <div class="hero-copy">
                <div class="kicker">Candidate detail</div>
                <h1>{_h.escape(str(candidate_id))}</h1>
                <div class="row">
                  <b>{_h.escape(str(interpretation))}</b>
                  <span class="pill" style="--c:{status_color}">{_h.escape(str(status))}</span>
                  <span class="coords">RA {ra:.4f}°  Dec {dec:.4f}°</span>
                </div>
              </div>
            </div>
            <div class="summary">{summary}</div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_footer():
    st.markdown(
        _html(
            f"""
            <div class="sitefooter">
              <div class="rail"></div>
              <div class="wordmark">SPHEREx</div>
              <div class="sitefooter-grid">
                <div>
                  <h4>SPHEREx Mission Explorer</h4>
                  <p>A candidate triage dashboard for multi-epoch astrometry, photometry and
                  molecular ice absorption, built for the NASA Space Apps Challenge.
                  Classification is rule-based triage, not proof of a source's true identity.</p>
                </div>
                <div>
                  <h4>Resources</h4>
                  <ul>
                    <li><a href="https://spherex.caltech.edu" target="_blank" rel="noopener">SPHEREx mission</a></li>
                    <li><a href="https://www.spaceappschallenge.org" target="_blank" rel="noopener">NASA Space Apps Challenge</a></li>
                    <li><a href="{API_URL}/docs" target="_blank" rel="noopener">API documentation</a></li>
                    <li><a href="https://github.com/Arnyz17/spherex-backend" target="_blank" rel="noopener">Backend repository</a></li>
                  </ul>
                </div>
                <div>
                  <h4>Built with</h4>
                  <ul>
                    <li>FastAPI, Pydantic, Astropy</li>
                    <li>NumPy, SciPy</li>
                    <li>Streamlit, Pandas, Plotly</li>
                  </ul>
                </div>
              </div>
              <div class="legal">
                Independent project created for the NASA Space Apps Challenge. This is not an official NASA website,
                and NASA does not endorse it. Catalogue: simulated, modelled on the SPHEREx mission design.
              </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def section(title, note=None, anchor=None):
    note_html = f"<p>{note}</p>" if note else ""
    id_html = f" id='{anchor}'" if anchor else ""
    st.markdown(
        _html(f"<div class='section'{id_html}><h2>{title}</h2>{note_html}</div>"),
        unsafe_allow_html=True,
    )


def panel_heading(title, meta=""):
    st.markdown(
        _html(f"<div class='panel-heading'><span>{title}</span><small>{meta}</small></div>"),
        unsafe_allow_html=True,
    )


# ----------------------------------------------------------------------------
# Artwork (assets/*.jpg, produced by tools/make_assets.py; swap in real photos)
# ----------------------------------------------------------------------------

ASSET_DIR = Path(__file__).resolve().parent / "assets"
_CLASS_COLORS = {
    "star_motion": "#6C8BFF", "ice_h2o": "#3DE0FF", "ice_co2": "#B45CFF", "ice_co": "#3DFFA0",
    "variable": "#FFB547", "artifact": "#FF3D5A", "galaxy": "#9AA6D6", "generic": "#6C7BFF",
}


@lru_cache(maxsize=None)
def _data_uri(stem):
    for ext, mime in (("jpg", "jpeg"), ("jpeg", "jpeg"), ("png", "png"), ("webp", "webp")):
        path = ASSET_DIR / f"{stem}.{ext}"
        if path.exists():
            return f"data:image/{mime};base64," + base64.b64encode(path.read_bytes()).decode()
    return ""


def class_key(name):
    n = str(name).lower()
    if "proper motion" in n:
        return "star_motion"
    if "h2o" in n:
        return "ice_h2o"
    if "co2" in n:
        return "ice_co2"
    if "ice" in n:
        return "ice_co"
    if "transient" in n or "variable" in n:
        return "variable"
    if "artifact" in n or "spike" in n:
        return "artifact"
    if "galaxy" in n:
        return "galaxy"
    return "generic"


@lru_cache(maxsize=None)
def _image_css():
    rules = []
    hero = _data_uri("hero_globe")
    if hero:
        rules.append(f".deck-bg {{ background-image: url({hero}); }}")
    for key in _CLASS_COLORS:
        uri = _data_uri(f"class_{key}")
        if uri:
            rules.append(f".im-{key} {{ background-image: url({uri}); }}")
    return "<style>" + "\n".join(rules) + "</style>"


# ----------------------------------------------------------------------------
# Command deck: globe, glass cards and image cards over one full-bleed scene
# ----------------------------------------------------------------------------

DECK_CSS = """
<style>
.deck-wrap { container-type: inline-size; }
.deck { position: relative; container-type: inline-size; aspect-ratio: 1.55; overflow: hidden;
        border-radius: 28px; background: #04050B; border: 1px solid var(--line-strong);
        box-shadow: 0 40px 90px rgba(0,0,0,.6), 0 0 60px -20px rgba(61,224,255,.35); }
.deck-bg { position: absolute; inset: 0; background-size: cover; background-position: center;
           background-color: #04050B; animation: drift-bg 40s ease-in-out infinite alternate; }
@keyframes drift-bg { from { transform: scale(1.0); } to { transform: scale(1.045); } }
.deck-scrim { position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(90deg, rgba(4,5,11,.88) 0%, rgba(4,5,11,.4) 30%, transparent 55%),
              linear-gradient(0deg, rgba(4,5,11,.8) 0%, transparent 38%); }
.deck::after { content: ""; position: absolute; inset: 0; border-radius: inherit; padding: 1.5px; pointer-events: none; z-index: 6;
  background: conic-gradient(from var(--ang), #B45CFF, #6C7BFF, #3DE0FF, #3DFFA0, #FFD166, #FF8A3D, #FF2D55, #B45CFF);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude; animation: ang 10s linear infinite; }

.d-item { position: absolute; z-index: 3; font-size: clamp(10px, .95cqw, 15px); color: var(--ink); }
.glass { background: linear-gradient(160deg, rgba(48,70,130,.36), rgba(8,12,32,.66));
         backdrop-filter: blur(18px) saturate(1.35); -webkit-backdrop-filter: blur(18px) saturate(1.35);
         border: 1px solid rgba(160,190,255,.22); border-radius: 1.6em;
         box-shadow: 0 22px 50px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.14); }

/* headline */
.d-head { left: 3%; top: 7%; width: 38%; }
.d-head .kicker { font-family: var(--mono); font-size: .76em; line-height: 1.9; color: var(--cyan); max-width: 32em; }
.d-head h1 { margin: .8em 0 .55em; padding: 0; color: #fff !important; font-family: var(--display); font-weight: 800;
             font-size: clamp(1.7rem, 3.6cqw, 3.7rem); letter-spacing: -.03em; line-height: 1.03; text-shadow: 0 6px 40px rgba(0,0,0,.7); }
.d-head p { margin: 0; max-width: 29em; font-size: 1.12em; line-height: 1.6; color: #C3CCF0; text-shadow: 0 2px 16px rgba(0,0,0,.8); }
.d-head .hero-tags { margin-top: 1.4em; }
.d-head .hero-tags span { font-size: .78em; }

/* candidate markers on the globe */
.globe-box { position: absolute; z-index: 2; height: 106.6%; aspect-ratio: 1; left: 55.2%; top: 66%; transform: translate(-50%, -50%); }
.dping { position: absolute; width: 0; height: 0; }
.dping i { position: absolute; width: .8em; height: .8em; margin: -.4em 0 0 -.4em; border-radius: 50%;
           background: var(--c); box-shadow: 0 0 1.2em var(--c); }
.dping::before, .dping::after { content: ""; position: absolute; border-radius: 50%; border: 1px solid var(--c);
                                width: 2.6em; height: 2.6em; margin: -1.3em 0 0 -1.3em; }
.dping::after { width: 4.6em; height: 4.6em; margin: -2.3em 0 0 -2.3em; opacity: .5; animation: dping 3.2s ease-out infinite; animation-delay: var(--d, 0s); }
.dping span { position: absolute; left: 1.8em; top: -.9em; padding: .25em .6em; border-radius: .5em; white-space: nowrap; opacity: 0;
              font-family: var(--mono); font-size: .8em; color: #fff; background: rgba(4,5,11,.85); border: 1px solid var(--c);
              transition: opacity .2s; pointer-events: none; }
.dping:hover span { opacity: 1; }
.dping { pointer-events: auto; }
.dping::before { pointer-events: auto; }
@keyframes dping { 0% { transform: scale(.55); opacity: .9; } 100% { transform: scale(1.5); opacity: 0; } }

/* featured detection */
.d-feat { left: 56.5%; top: 11%; width: 21%; padding: 1.25em 1.35em 1.3em; }
.f-top { display: flex; justify-content: space-between; align-items: center; color: var(--mute); font-size: .92em; }
.f-top em { font-style: normal; font-family: var(--mono); font-size: .8em; padding: .25em .7em; border-radius: 999px;
            border: 1px solid var(--line-strong); }
.d-feat h3 { margin: .35em 0 .45em !important; font-family: var(--display) !important; font-weight: 600 !important;
             font-size: 1.85em !important; letter-spacing: -.02em; color: #fff; line-height: 1.1; }
.f-class { display: inline-flex; align-items: center; gap: .5em; font-size: .92em; color: var(--c); }
.f-class::before { content: ""; width: .6em; height: .6em; border-radius: 50%; background: var(--c); box-shadow: 0 0 .9em var(--c); }
.f-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1em 1.2em; margin-top: 1.2em; padding-top: 1em; border-top: 1px solid rgba(160,190,255,.18); }
.f-grid span { display: block; color: var(--mute); font-size: .84em; }
.f-grid b { display: block; margin-top: .15em; font-family: var(--mono); font-weight: 600; font-size: 1.3em; color: #fff; }
.f-foot { margin-top: 1.1em; color: var(--mute); font-size: .88em; }
.f-foot b { display: block; margin-top: .15em; color: #fff; font-size: 1.15em; font-weight: 600; }

/* radar */
.d-radar { left: 56.5%; top: 55%; width: 21%; aspect-ratio: 1.35; overflow: hidden; padding: 0; }
.radar-grid { position: absolute; inset: 0;
  background:
    linear-gradient(rgba(61,224,255,.16) 1px, transparent 1px) 0 0 / 14.28% 20%,
    linear-gradient(90deg, rgba(61,224,255,.16) 1px, transparent 1px) 0 0 / 14.28% 20%,
    linear-gradient(135deg, rgba(61,224,255,.28), rgba(61,224,255,.05)); }
.radar-ring { position: absolute; left: 50%; top: 50%; border-radius: 50%; border: 1px solid rgba(190,240,255,.6); transform: translate(-50%, -50%); }
.radar-ring.a { width: 78%; aspect-ratio: 1; } .radar-ring.b { width: 52%; aspect-ratio: 1; opacity: .8; } .radar-ring.c { width: 26%; aspect-ratio: 1; opacity: .7; }
.radar-sweep { position: absolute; left: 50%; top: 50%; width: 78%; aspect-ratio: 1; margin: calc(-39% * 1) 0 0 -39%; border-radius: 50%;
               background: conic-gradient(from 0deg, transparent 0 290deg, rgba(190,250,255,.55) 360deg); animation: spin 5s linear infinite;
               transform-origin: 50% 50%; }
.radar-dot { position: absolute; width: .7em; height: .7em; margin: -.35em; border-radius: 50%; background: var(--c); box-shadow: 0 0 1em var(--c); }
.radar-cap { position: absolute; left: 1em; bottom: .8em; font-size: .85em; color: #D9E6FF; text-shadow: 0 1px 8px rgba(0,0,0,.8); }

/* insights column */
.d-ins { left: 79.4%; top: 4.2%; width: 18.6%; height: 91.6%; padding: 1em; display: flex; flex-direction: column; gap: .5em; }
.ins-title { display: flex; align-items: center; justify-content: center; gap: .5em; font-weight: 600; font-size: 1.05em; color: #fff; padding: .2em 0 .1em; }
.ins-title::before { content: "✦"; color: var(--cyan); }
.ins-h { text-align: center; color: #E3EAFF; font-size: .98em; font-weight: 500; margin-top: .2em; }
.ic { position: relative; flex: 1; min-height: 0; border-radius: 1.2em; overflow: hidden; background-size: cover; background-position: center;
      border: 1px solid rgba(160,190,255,.25); box-shadow: 0 10px 30px rgba(0,0,0,.4); }
.ic::before { content: ""; position: absolute; inset: 0; background: linear-gradient(0deg, rgba(4,5,14,.9) 0%, rgba(4,5,14,.2) 55%, rgba(4,5,14,.35) 100%); }
.ic > * { position: relative; }
.ic-cls { position: absolute; left: .8em; top: .7em; font-size: .78em; color: #DDE6FF; display: flex; flex-direction: column; text-shadow: 0 1px 8px #000; }
.ic-cls small { color: var(--c); font-size: .95em; font-weight: 600; }
.ic-sig { position: absolute; right: .7em; top: .6em; font-family: var(--mono); font-size: .8em; padding: .35em .7em; border-radius: 999px;
          background: rgba(4,5,14,.6); border: 1px solid rgba(190,210,255,.4); color: #fff; backdrop-filter: blur(6px); }
.ic-body { position: absolute; left: .85em; right: .85em; bottom: .7em; }
.ic-body b { display: block; color: #fff; font-weight: 600; font-size: 1.05em; margin-bottom: .35em; }
.chip { display: inline-flex; align-items: center; gap: .45em; padding: .3em .7em; font-size: .85em; color: #fff;
        border-radius: .7em; background: rgba(150,170,230,.22); border: 1px solid rgba(190,210,255,.3); backdrop-filter: blur(6px); }
.chip.warn::before { content: "!"; display: inline-grid; place-items: center; width: 1.3em; height: 1.3em; border-radius: 50%;
                     background: #FFB547; color: #1a1200; font-weight: 700; font-size: .85em; }
.chip.ok::before { content: ""; width: .6em; height: .6em; border-radius: 50%; background: var(--mint); box-shadow: 0 0 .8em var(--mint); }

/* bottom stat cards */
.d-stat { bottom: 4.2%; height: 26%; padding: 1.1em 1.3em; overflow: hidden; }
.sA { left: 2.5%; width: 24.4%; } .sB { left: 28.2%; width: 24.4%; } .sC { left: 53.9%; width: 24.4%; }
.s-title { font-weight: 600; color: #fff; font-size: 1.02em; }
.s-big { font-family: var(--mono); font-weight: 600; font-size: 2.1em; line-height: 1.15; color: #fff; margin-top: .1em; }
.s-big small { margin-left: .5em; font-family: var(--body); font-weight: 400; font-size: .42em; color: var(--mute); }
.cols { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: .6em; margin-top: .6em; height: 46%; }
.col { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: .25em; min-width: 0; }
.col .track { position: relative; width: 70%; flex: 1; border-radius: .3em; background:
  repeating-linear-gradient(0deg, transparent 0 .35em, rgba(150,175,255,.14) .35em .4em),
  repeating-linear-gradient(90deg, transparent 0 .35em, rgba(150,175,255,.14) .35em .4em); }
.col .fill { position: absolute; left: 0; right: 0; bottom: 0; border-radius: .3em; background: linear-gradient(0deg, color-mix(in srgb, var(--c) 35%, transparent), color-mix(in srgb, var(--c) 80%, transparent));
             box-shadow: 0 0 1em -.2em var(--c); }
.col .fill::after { content: ""; position: absolute; left: 50%; top: -.3em; width: .6em; height: .6em; margin-left: -.3em; border-radius: 50%; background: #fff; box-shadow: 0 0 .8em var(--c); }
.col label { font-size: .7em; color: var(--mute); white-space: nowrap; }
.tiles { display: flex; gap: .7em; margin-top: .8em; }
.tile { flex: 1; min-width: 0; padding: .7em .8em; border-radius: .9em; background: rgba(150,170,230,.1); border: 1px solid rgba(160,190,255,.2); }
.tile em { display: inline-block; font-style: normal; font-family: var(--mono); font-size: .72em; padding: .2em .55em; border-radius: .5em; background: rgba(150,170,230,.2); color: #DCE6FF; }
.tile b { display: block; margin: .5em 0 .15em; font-size: .88em; color: #fff; font-family: var(--mono); font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile span { display: block; font-size: .76em; color: var(--mute); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tile .chip { margin-top: .6em; font-size: .7em; }
.rows { margin-top: .7em; display: flex; flex-direction: column; gap: .55em; }
.row { display: grid; grid-template-columns: 9.5em 1fr 2em; align-items: center; gap: .8em; font-size: .85em; color: #D3DBF5; }
.row span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.row .bar { height: .3em; border-radius: 1em; background: rgba(150,175,255,.18); overflow: hidden; }
.row .bar i { display: block; height: 100%; border-radius: inherit; background: var(--c); box-shadow: 0 0 .8em var(--c); }
.row b { font-family: var(--mono); font-weight: 600; text-align: right; color: #fff; }

/* narrow screens: stack everything */
@container (max-width: 900px) {
  .deck { aspect-ratio: auto; display: flex; flex-direction: column; gap: 14px; padding: 18px; }
  .deck-bg { background-position: 40% 30%; }
  .d-item { position: relative; left: auto; top: auto; bottom: auto; width: auto; height: auto; font-size: 13px; }
  .d-head h1 { font-size: 2rem; }
  .globe-box, .d-radar { display: none; }
  .d-ins { height: auto; } .ic { min-height: 150px; flex: none; }
  .d-stat { height: auto; min-height: 150px; } .cols { height: 90px; }
}
@media (prefers-reduced-motion: reduce) { .deck-bg { animation: none; } }
</style>
"""


EXTRA_CSS = """
<style>
/* wavelength scale (used by the strip under the deck) */
.scale { position: relative; margin-top: 1.2rem; padding-top: 2rem; }
.scale-bar { position: relative; height: 10px; border-radius: 6px; background: var(--ribbon); box-shadow: 0 0 24px rgba(108,123,255,.35); }
.scale-bar::after { content: ""; position: absolute; inset: 0; border-radius: inherit;
                    background: repeating-linear-gradient(90deg, transparent 0 3px, rgba(4,5,11,.62) 3px 4px); }
.ice { position: absolute; bottom: 10px; transform: translateX(-50%); text-align: center; z-index: 3;
       font-family: var(--mono); font-size: .64rem; color: #fff; white-space: nowrap; }
.ice::after { content: ""; display: block; width: 1px; height: 26px; margin: 4px auto 0; background: linear-gradient(#fff, transparent); }
.ice b { display: inline-block; padding: .2rem .5rem; border-radius: 4px; font-weight: 600; background: rgba(4,5,11,.85); border: 1px solid var(--line-strong); }
.ticks { display: flex; justify-content: space-between; margin-top: .5rem; font-family: var(--mono); font-size: .62rem; color: var(--dim); }
.scale-card { margin-top: 1rem; padding: 1.3rem 1.6rem 1.2rem; border-radius: 20px; border: 1px solid var(--line); background: var(--glass); }
.scale-card h4 { margin: 0 0 .3rem; font-family: var(--display); font-weight: 600; font-size: .95rem; color: #fff; }
.scale-card p { margin: 0; color: var(--mute); font-size: .88rem; max-width: 60ch; }
@media (max-width: 700px) {
  .ice { font-size: .55rem; }
  .ice:nth-child(2) { transform: translateX(-85%); }
  .ice:nth-child(3) { transform: translateX(-8%); }
}

/* candidate banner with class artwork */
.hero.compact.has-art { background-size: cover; background-position: center; }
.hero.compact.has-art::before { content: ""; position: absolute; inset: 0; z-index: 1; pointer-events: none;
  background: linear-gradient(90deg, rgba(4,5,14,.96) 28%, rgba(4,5,14,.55) 60%, rgba(4,5,14,.15)); }

/* command bar: the first search box under the deck */
div[class*="st-key-cmd"] { position: relative; z-index: 5; max-width: 760px; margin: -2.2rem auto 0; }
div[class*="st-key-cmd"] div[data-baseweb="input"] { border-radius: 999px !important; background: rgba(8,12,34,.82) !important;
  border: 1px solid rgba(160,190,255,.35) !important; backdrop-filter: blur(16px);
  box-shadow: 0 18px 46px rgba(0,0,0,.5), 0 0 40px -12px rgba(61,224,255,.5); }
div[class*="st-key-cmd"] div[data-baseweb="input"] > div { border: 0 !important; background: transparent !important; }
div[class*="st-key-cmd"] input { height: 3.1rem; padding-left: 3.1rem !important; font-size: 1rem; color: #fff; }
div[class*="st-key-cmd"] div[data-baseweb="input"]::before { content: "✦"; position: absolute; left: 1.2rem; top: 50%;
  transform: translateY(-50%); color: var(--cyan); font-size: 1.1rem; z-index: 2; }
div[class*="st-key-cmd"] div[data-baseweb="input"]:focus-within { border-color: var(--cyan) !important;
  box-shadow: 0 18px 46px rgba(0,0,0,.5), 0 0 0 3px rgba(61,224,255,.2), 0 0 44px -8px rgba(61,224,255,.7); }

/* candidate gallery */
.gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(255px, 1fr)); gap: 1.1rem; }
.gcard { display: block; overflow: hidden; border-radius: 20px; text-decoration: none !important; color: inherit !important;
         border: 1px solid var(--line); background: var(--glass); box-shadow: 0 16px 40px rgba(0,0,0,.35);
         transition: border-color .25s, box-shadow .25s; }
.gcard:hover { border-color: var(--c); box-shadow: 0 0 0 1px var(--c), 0 0 34px -6px var(--c); }
.gimg { position: relative; height: 150px; background-size: cover; background-position: center; transition: transform .6s; }
.gcard:hover .gimg { transform: scale(1.06); }
.gcard { position: relative; }
.gimg::after { content: ""; position: absolute; inset: 0; background: linear-gradient(0deg, rgba(4,5,14,.75), transparent 60%); }
.gpill { position: absolute; left: .8rem; top: .8rem; z-index: 2; display: inline-flex; align-items: center; gap: .45rem; padding: .28rem .7rem;
         font-size: .72rem; font-weight: 600; color: #fff; border-radius: 999px; background: rgba(4,5,14,.62);
         border: 1px solid var(--c); backdrop-filter: blur(6px); }
.gpill::before { content: ""; width: 6px; height: 6px; border-radius: 50%; background: var(--c); box-shadow: 0 0 8px var(--c); }
.gwarn { position: absolute; right: .8rem; top: .8rem; z-index: 2; display: grid; place-items: center; width: 1.5rem; height: 1.5rem;
         border-radius: 50%; background: #FFB547; color: #1a1200; font-weight: 700; font-size: .8rem; }
.gbody { padding: .95rem 1.1rem 1.1rem; position: relative; background: rgba(6,8,22,.55); }
.gbody b { display: block; color: #fff; font-family: var(--mono); font-weight: 600; font-size: .98rem; }
.gbody > span { display: block; margin-top: .2rem; color: var(--c); font-size: .84rem; }
.gmeta { display: flex; gap: .5rem; margin-top: .8rem; }
.gmeta em { flex: 1; font-style: normal; font-size: .68rem; color: var(--mute); padding: .45rem .55rem; border-radius: .7rem;
            background: rgba(150,170,230,.08); border: 1px solid var(--line); }
.gmeta strong { display: block; margin-top: .1rem; font-family: var(--mono); font-size: .88rem; color: #fff; }
</style>
"""


def _short_class(name):
    return str(name).replace(" Feature", "").replace("Photometric Transient / Variable Star", "Transient / variable")


def _fmt(v, digits=2, fallback="n/a"):
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return fallback


def _ping_xy(ra, dec):
    """Schematic placement on the globe: RA spread across the visible face."""
    lon = math.radians((float(ra) - 180.0) / 180.0 * 66.0)
    lat = math.radians(max(-70.0, min(70.0, float(dec) * 0.85)))
    x, y = math.cos(lat) * math.sin(lon), math.sin(lat)
    return 50 + 50 * x, 50 - 50 * y


def _score(frame):
    a = frame["displacement_significance_sigma"].astype(float).fillna(0) if "displacement_significance_sigma" in frame else 0
    b = frame["delta_brightness_significance_sigma"].astype(float).fillna(0) if "delta_brightness_significance_sigma" in frame else 0
    return a.where(a > b, b) if hasattr(a, "where") else a


def render_deck(df):
    """The overview command deck, built from the live catalogue."""
    e = _esc.escape
    frame = df.copy().reset_index(drop=True)
    for col, default in (("scientific_interpretation", "Unclassified"), ("validation_status", "Unreviewed"),
                         ("has_quality_warnings", False), ("displacement_significance_sigma", 0.0),
                         ("delta_brightness_significance_sigma", 0.0), ("ra", 0.0), ("dec", 0.0)):
        if col not in frame:
            frame[col] = default
    frame["score_"] = _score(frame)
    frame["key_"] = frame["scientific_interpretation"].map(class_key)
    frame["warn_"] = frame["has_quality_warnings"].fillna(False).astype(bool) | frame["scientific_interpretation"].astype(str).str.contains("Artifact", case=False)
    ranked = frame.sort_values("score_", ascending=False)
    clean = ranked[~ranked["warn_"]]  # a flagged artifact should not headline the deck
    top = (clean if not clean.empty else ranked).iloc[0]

    def col_of(key):
        return _CLASS_COLORS.get(key, "#6C7BFF")

    # --- markers on the globe
    pings = "".join(
        f'<div class="dping" style="left:{x:.1f}%;top:{y:.1f}%;--c:{col_of(r.key_)};--d:-{i * .7:.1f}s">'
        f'<i></i><span>{e(str(r.candidate_id))}</span></div>'
        for i, r in enumerate(frame.head(14).itertuples())
        for x, y in [_ping_xy(r.ra, r.dec)]
    )

    # --- insight cards: strongest, needs review, best vetted candidate
    used = {top.name}

    def pick(mask, order):
        pool = order[mask.reindex(order.index, fill_value=False)]
        pool = pool[~pool.index.isin(used)]
        if pool.empty:
            pool = order[~order.index.isin(used)]
        if pool.empty:
            pool = order
        row = pool.iloc[0]
        used.add(row.name)
        return row

    status = frame["validation_status"].astype(str)
    cards = [
        ("Strongest signal", top),
        ("Needs review", pick(frame["warn_"], ranked)),
        ("Best vetted candidate", pick(status.isin(["Confirmed", "Plausible Candidate"]), ranked)),
    ]

    def ins_card(label, r):
        c = col_of(r.key_)
        chip = '<span class="chip warn">Quality warning</span>' if r.warn_ else f'<span class="chip ok">{e(str(r.validation_status))}</span>'
        return (
            f'<div class="ins-h">{label}</div>'
            f'<div class="ic im-{r.key_}" style="--c:{c}">'
            f'<div class="ic-cls"><small>{e(_short_class(r.scientific_interpretation))}</small></div>'
            f'<div class="ic-sig">{_fmt(r.score_, 1)}σ</div>'
            f'<div class="ic-body"><b>{e(str(r.candidate_id))}</b>{chip}</div></div>'
        )

    insights = "".join(ins_card(lbl, r) for lbl, r in cards)

    # --- featured detection + radar
    c = col_of(top.key_)
    rx = 50 + 30 * math.cos(math.radians(float(top.ra) * 3.7))
    ry = 50 + 24 * math.sin(math.radians(float(top.dec) * 5.3 + 40))
    feat = (
        f'<div class="d-item d-feat glass" style="--c:{c}">'
        f'<div class="f-top"><span>Top detection</span><em>{_fmt(top.score_, 1)}σ</em></div>'
        f'<h3>{e(str(top.candidate_id))}</h3>'
        f'<div class="f-class">{e(_short_class(top.scientific_interpretation))}</div>'
        f'<div class="f-grid">'
        f'<div><span>Motion</span><b>{_fmt(top.displacement_significance_sigma)}σ</b></div>'
        f'<div><span>Brightness</span><b>{_fmt(top.delta_brightness_significance_sigma)}σ</b></div>'
        f'<div><span>RA</span><b>{_fmt(top.ra, 2)}°</b></div>'
        f'<div><span>Dec</span><b>{_fmt(top.dec, 2)}°</b></div></div>'
        f'<div class="f-foot">Validation<b>{e(str(top.validation_status))}</b></div></div>'
        f'<div class="d-item d-radar glass" style="--c:{c}"><div class="radar-grid"></div>'
        f'<div class="radar-ring a"></div><div class="radar-ring b"></div><div class="radar-ring c"></div>'
        f'<div class="radar-sweep"></div><div class="radar-dot" style="left:{rx:.0f}%;top:{ry:.0f}%"></div>'
        f'<div class="radar-cap">Field around {e(str(top.candidate_id))}</div></div>'
    )

    # --- bottom row
    total = len(frame)
    order = [("Confirmed", "Confirmed", "#3DFFA0"), ("Plausible Candidate", "Plausible", "#6C8BFF"),
             ("Likely Artifact", "Artifact", "#FF3D5A"), ("Unreviewed", "Unreviewed", "#9AA6D6")]
    counts = [(lbl, int((status == key).sum()), colr) for key, lbl, colr in order]
    top_n = max([n for _, n, _ in counts] + [1])
    cols = "".join(
        f'<div class="col" style="--c:{colr}"><div class="track"><div class="fill" style="height:{max(6, n / top_n * 100):.0f}%"></div></div><label>{lbl} {n}</label></div>'
        for lbl, n, colr in counts
    )
    sA = (f'<div class="d-item d-stat sA glass"><div class="s-title">Candidates by status</div>'
          f'<div class="s-big">{total}<small>sources</small></div><div class="cols">{cols}</div></div>')

    tiles = "".join(
        f'<div class="tile"><em>RA {_fmt(r.ra, 1)}°</em><b>{e(str(r.candidate_id))}</b>'
        f'<span>{e(_short_class(r.scientific_interpretation))}</span>'
        + ('<div class="chip warn">Warning</div>' if r.warn_ else f'<div class="chip ok">{e(str(r.validation_status).split()[0])}</div>')
        + '</div>'
        for r in frame.head(3).itertuples()
    )
    sB = f'<div class="d-item d-stat sB glass"><div class="s-title">Latest detections</div><div class="tiles">{tiles}</div></div>'

    by_class = frame["scientific_interpretation"].astype(str).value_counts().head(5)
    keymax = max(int(by_class.max()), 1)
    rows = "".join(
        f'<div class="row" style="--c:{col_of(class_key(n))}"><span>{e(_short_class(n))}</span>'
        f'<div class="bar"><i style="width:{v / keymax * 100:.0f}%"></i></div><b>{int(v)}</b></div>'
        for n, v in by_class.items()
    )
    sC = f'<div class="d-item d-stat sC glass"><div class="s-title">Sources by class</div><div class="rows">{rows}</div></div>'

    head = (
        '<div class="d-item d-head"><div class="kicker">Spectro-Photometer for the History of the Universe, '
        'Epoch of Reionization and Ices Explorer</div><h1>Read the sky<br>in infrared</h1>'
        '<p>Scientific triage of multi-epoch astrometry, photometric variability and infrared ice-absorption signatures.</p>'
        '<div class="hero-tags"><span>0.75–5.0 µm</span><span>6 spectral bands</span><span>Multi-epoch analysis</span></div></div>'
    )
    ins = f'<div class="d-item d-ins glass"><div class="ins-title">Detection insights</div>{insights}</div>'

    st.markdown(
        _html(
            '<div class="deck-wrap"><div class="deck"><div class="deck-bg"></div><div class="deck-scrim"></div>'
            f'<div class="globe-box">{pings}</div>{head}{feat}{ins}{sA}{sB}{sC}</div></div>'
        ),
        unsafe_allow_html=True,
    )


# Ice absorption bands on the survey's 0.75 to 5.0 µm axis
_ICES = [("H₂O", 3.05), ("CO₂", 4.27), ("CO", 4.67)]


def _scale_html():
    lo, hi = 0.75, 5.0
    marks = "".join(
        f'<span class="ice" style="left:{(wl - lo) / (hi - lo) * 100:.1f}%"><b>{name} {wl:.2f} µm</b></span>'
        for name, wl in _ICES
    )
    return (
        '<div class="scale">'
        f'<div class="scale-bar">{marks}</div>'
        '<div class="ticks"><span>0.75 µm</span><span>1</span><span>2</span><span>3</span><span>4</span><span>5.0 µm</span></div>'
        "</div>"
    )


def render_gallery(df, limit=12):
    """Image cards for each candidate. Each card opens that candidate's detail page."""
    e = _esc.escape
    frame = df.head(limit)
    cards = []
    for r in frame.itertuples():
        cls = getattr(r, "scientific_interpretation", "Unclassified")
        key = class_key(cls)
        colour = _CLASS_COLORS.get(key, "#6C7BFF")
        status = str(getattr(r, "validation_status", "Unreviewed"))
        scolor = STATUS_COLORS.get(status, "#9AA6D6")
        warn = bool(getattr(r, "has_quality_warnings", False))
        warn_html = '<span class="gwarn" title="Quality warning">!</span>' if warn else ""
        cid = str(r.candidate_id)
        cards.append(
            f'<a class="gcard" href="detail?candidate={_quote(cid)}" style="--c:{colour}">'
            f'<div class="gimg im-{key}"><span class="gpill" style="--c:{scolor}">{e(status)}</span>{warn_html}</div>'
            f'<div class="gbody"><b>{e(cid)}</b><span>{e(_short_class(cls))}</span>'
            f'<div class="gmeta"><em>Motion<strong>{_fmt(getattr(r, "displacement_significance_sigma", None), 1)}σ</strong></em>'
            f'<em>Brightness<strong>{_fmt(getattr(r, "delta_brightness_significance_sigma", None), 1)}σ</strong></em>'
            f'<em>Dec<strong>{_fmt(getattr(r, "dec", None), 1)}°</strong></em></div></div></a>'
        )
    st.markdown(_html('<div class="gallery">' + "".join(cards) + "</div>"), unsafe_allow_html=True)


def render_scale_strip():
    st.markdown(
        _html(
            '<div class="scale-card"><h4>Where each ice absorbs</h4>'
            '<p>The survey covers 0.75 to 5.0 µm. Water, carbon dioxide and carbon monoxide ices leave dips at these wavelengths.</p>'
            f'{_scale_html()}</div>'
        ),
        unsafe_allow_html=True,
    )
