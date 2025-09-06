# Backend (FastAPI) for AOI Mapper

## Setup (one-time)

1. Create a Python virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Authenticate Google Earth Engine (one-time; follow prompt):
   ```bash
   python -c "import ee; ee.Authenticate(); ee.Initialize()"
   ```
   For server/service use consider a service account; see GEE docs.

## Run
Start the API:
```bash
uvicorn main:app --reload --port 8000
```

POST /analyze expects JSON:
{
  "name": "TestArea",
  "latitude": 17.385,
  "longitude": 78.4867,
  "area_sq_m": 5000000
}

It returns:
{
  "summary": { ... },
  "layers": {
    "water": <GeoJSON-like FeatureCollection dict>,
    "agriculture": ...,
    "forest": ...,
    "infrastructure": ...
  }
}
