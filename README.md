# Video Analyzer — Django + Streamlit

Same pipeline as before (captions → Whisper fallback → chunked summarization
→ keyword extraction), rebuilt with a Django REST API backend and a
Streamlit frontend with a professional theme (deep teal accent, off-white
background, restrained borders — no dark/red landing-page styling).

## Structure
```
backend_django/          Django + DRF API
  analyzer_project/      settings, urls, wsgi
  analyzer/
    views.py             /api/analyze/, /api/health/
    serializers.py
    services/            transcript_service.py, summarizer.py, keywords.py
                          (unchanged logic from the FastAPI version)
streamlit_frontend/
  app.py                 UI
  .streamlit/config.toml theme colors
```

## Run the backend
```bash
cd backend_django
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
sudo apt install ffmpeg      # needed for the Whisper fallback path

python manage.py runserver 0.0.0.0:8000
```

For GPU acceleration on your RTX 4050:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

## Run the frontend
```bash
cd streamlit_frontend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

streamlit run app.py
```

Opens at `http://localhost:8501` and talks to the Django API at
`http://localhost:8000/api/analyze/`.

## API
Same contract as before:
```
POST /api/analyze/
{ "mode": "url", "content": "https://www.youtube.com/watch?v=..." }
```
or `"mode": "transcript"` with raw transcript text in `content`.

## Notes
- No database is configured — the API is stateless (analyze → return, nothing
  persisted). If you later want history/saved analyses, add a model + SQLite
  and a `POST /api/history/` endpoint.
- CORS is wide open between :8501 and :8000 for local dev — tighten
  `CORS_ALLOW_ALL_ORIGINS` in `settings.py` if you deploy this.
- Theme colors live in `streamlit_frontend/.streamlit/config.toml` — change
  `primaryColor`/`backgroundColor` there to retheme without touching `app.py`.
