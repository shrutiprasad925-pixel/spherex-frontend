# SPHEREx Mission Explorer — Frontend

A Streamlit frontend for the SPHEREx Mission Explorer FastAPI backend.

## What is included
- Mission overview dashboard with candidate metrics, classification breakdown, sky-coordinate plot, significance diagnostics, validation chart, filters and CSV export.
- Candidate detail page with key measurements, spectrum, ice-feature table, observation epochs, side-by-side cutouts and automatic blink comparator.
- Dark mission-control styling with starfield background and responsive layout.
- Command-deck hero (generated Earth image, spotlight card, radar, insight image cards), a search bar, and a clickable candidate gallery that opens each source's detail page.

## Important scientific note
The current backend catalogue contains seven synthetic seed candidates modelled on SPHEREx mission design. The sky plot visualizes those candidate coordinates only; it is not a full-sky SPHEREx survey map. The classifier is deterministic and rule-based, not a trained ML model.

## Setup (Windows PowerShell)
1. Open this folder in a terminal.
2. Create a virtual environment (recommended):
   ```powershell
   py -m venv .venv
   .venv\Scripts\activate
   ```
3. Install frontend packages:
   ```powershell
   pip install -r requirements.txt
   ```
4. Start your FastAPI backend in its own terminal on `http://127.0.0.1:8000`.
5. Start Streamlit:
   ```powershell
   streamlit run app.py
   ```

The API base URL is configured in `common.py` as `http://127.0.0.1:8000`. Change `API_URL` there only if your backend runs elsewhere.

## Project structure
```text
spherex-frontend/
├── app.py
├── common.py
├── theme.py
├── requirements.txt
├── pages/
│   ├── overview.py
│   └── detail.py
└── .streamlit/
    └── config.toml
```


## Artwork
All images in `assets/` are generated, so nothing needs downloading:
```text
python tools/make_assets.py   # class thumbnails + a basic hero
python tools/make_hero.py     # richer dotted-Earth hero (overwrites hero_globe.jpg)
```
To use real NASA / SPHEREx images, drop files with the same names into `assets/`.
