# Frontend (React) for AOI Mapper

## Setup
1. In the frontend folder:
   ```bash
   npm install
   npm start
   ```
2. The app expects the backend at `http://localhost:8000/analyze`. Edit the URL in `src/App.jsx` if needed.

## Notes
- The UI has a textarea to paste the input JSON and an Analyze button.
- The returned layers are rendered as GeoJSON overlays with configured colors:
  - Water: blue
  - Agriculture: brown
  - Forest: green
  - Infrastructure: grey
