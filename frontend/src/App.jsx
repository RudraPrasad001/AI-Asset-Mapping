import React, { useState } from "react";
import { MapContainer, TileLayer, GeoJSON, Circle, Marker, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";

function App() {
  const [inputJson, setInputJson] = useState(JSON.stringify({
    name: "TestArea",
    latitude: 17.385,
    longitude: 78.4867,
    area_sq_m: 5000000
  }, null, 2));
  const [summary, setSummary] = useState(null);
  const [layers, setLayers] = useState(null);
  const [aoiRadius, setAoiRadius] = useState(null);
  const [aoiCenter, setAoiCenter] = useState(null);
  const [error, setError] = useState(null);

  async function analyze() {
    try {
      const payload = JSON.parse(inputJson);
      const res = await axios.post("http://127.0.0.1:8000/analyze", payload);
      setSummary(res.data.summary);
      setLayers(res.data.layers);
      const r = Math.sqrt(payload.area_sq_m / Math.PI);
      setAoiRadius(r);
      setAoiCenter([payload.latitude, payload.longitude]);
    } catch (err) {
      alert("Error: " + (err.response?.data?.detail || err.message));
      console.error(err);
    }
  }

  function styleByClass(feature) {
    const cls = (feature?.properties?.class || "").toLowerCase();
    if (cls === "water") return { color: "#1e90ff", fillColor: "#1e90ff", fillOpacity: 0.5 };
    if (cls === "agriculture") return { color: "#8b4513", fillColor: "#8b4513", fillOpacity: 0.45 };
    if (cls === "forest") return { color: "#228b22", fillColor: "#228b22", fillOpacity: 0.45 };
    if (cls === "infrastructure") return { color: "#808080", fillColor: "#808080", fillOpacity: 0.35 };
    return { color: "#000", fillColor: "#000", fillOpacity: 0.2 };
  }

  // Add effect to automatically analyze when JSON changes
  React.useEffect(() => {
    const timeoutId = setTimeout(() => {
      try {
        JSON.parse(inputJson); // Validate JSON
        analyze();
      } catch (err) {
        setError("Invalid JSON format");
      }
    }, 1000); // Wait 1 second after last change before analyzing

    return () => clearTimeout(timeoutId);
  }, [inputJson]);

  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <div style={{ width: "380px", padding: 12, borderRight: "1px solid #ddd", overflow: "auto" }}>
        <h2>AOI Mapper</h2>
        <p>Provide input JSON below to automatically analyze the area.</p>
        <textarea 
          style={{ 
            width: "100%", 
            height: 220,
            borderColor: error ? 'red' : '#ddd'
          }} 
          value={inputJson} 
          onChange={e => {
            setInputJson(e.target.value);
            setError(null);
          }} 
        />
        {error && <p style={{ color: 'red', marginTop: 4 }}>{error}</p>}

        {summary && (
          <div style={{ marginTop: 12 }}>
            <h3>Summary</h3>
            <pre style={{ background: "#f7f7f7", padding: 10 }}>{JSON.stringify(summary, null, 2)}</pre>
            <a href={"data:application/json;charset=utf-8," + encodeURIComponent(JSON.stringify(summary, null, 2))} download={`${summary.name}_summary.json`}>Download Summary JSON</a>
          </div>
        )}
      </div>

      <div style={{ flex: 1 }}>
        <MapContainer center={[17.385, 78.4867]} zoom={12} style={{ height: "100%", width: "100%" }}>
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {aoiCenter && aoiRadius && <Circle center={aoiCenter} radius={aoiRadius} pathOptions={{color: "#000", fillOpacity:0.02}} />}
          {aoiCenter && <Marker position={aoiCenter}><Popup>{summary?summary.name:"AOI"}</Popup></Marker>}
          {layers && layers.water && (
            <GeoJSON data={layers.water} style={styleByClass} />
          )}
          {layers && layers.agriculture && (
            <GeoJSON data={layers.agriculture} style={styleByClass} />
          )}
          {layers && layers.forest && (
            <GeoJSON data={layers.forest} style={styleByClass} />
          )}
          {layers && layers.infrastructure && (
            <GeoJSON data={layers.infrastructure} style={styleByClass} />
          )}
        </MapContainer>
      </div>
    </div>
  );
}

export default App;
