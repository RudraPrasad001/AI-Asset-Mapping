import React, { useState, useEffect } from "react";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Circle,
  Marker,
  Popup,
  useMap,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import axios from "axios";

// --- FlyTo helper ---
function FlyToController({ center, radius, trigger }) {
  const map = useMap();
  useEffect(() => {
    if (center && radius) {
      map.flyTo(center, zoomFromRadiusMeters(radius), { duration: 1 });
    }
  }, [center, radius, trigger, map]);
  return null;
}

// Heuristic zoom based on radius
function zoomFromRadiusMeters(r) {
  if (r >= 15000) return 10;
  if (r >= 8000) return 11;
  if (r >= 4000) return 12;
  if (r >= 2000) return 13;
  return 14;
}

// Get color based on layer class
function getLayerColor(layerClass) {
  switch (layerClass) {
    case 'water':
      return '#1e90ff';
    case 'agriculture':
      return '#8b4513';
    case 'forest':
      return '#228b22';
    case 'infrastructure':
      return '#808080';
    default:
      return '#000000';
  }
}
const AOIMapper = () => {
  let apiEndpoint = "http://localhost:8000";
  let backend = "http://localhost:5000";
  const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6MSwiZ21haWwiOiJSdWRyYUBnbWFpbC5jb20iLCJyb2xlIjoiYWRtaW4iLCJpYXQiOjE3NTcyMzgwNzIsImV4cCI6MTc1NzI0MTY3Mn0.SuJaEOvp07CiftXNj3fMD-nRXVcISyL-Ko7iqpL5E1Q"; // replace with real token

  const [aoiInputs, setAoiInputs] = useState([]);
  const [aoiResults, setAoiResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [selectedAoiIndex, setSelectedAoiIndex] = useState(0);
  const [mapKey, setMapKey] = useState(0);

  // fetch initial AOI list from your API
  useEffect(() => {
  const fetchAOIs = async () => {
    setLoading(true);
    setStatus("Fetching AOIs...");

    try {
      const res = await axios.get(`${backend}/api/patta/stats/districts-area`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      // normalize strings → numbers
      const normalized = res.data.map(item => ({
        ...item,
        latitude: Number(item.latitude),
        longitude: Number(item.longitude),
        area_sq_m: Number(item.area_sq_m),
      }));

      setAoiInputs(normalized);
      setStatus("AOIs loaded successfully");
    } catch (err) {
      console.error("Error fetching AOIs:", err);
      setStatus("Failed to fetch AOIs");
    } finally {
      setLoading(false);
    }
  };

  fetchAOIs();
}, [backend, token]);


  // analyze selected AOI
  useEffect(() => {
    if (aoiInputs.length === 0) return;

    const analyzeArea = async (input) => {
      setLoading(true);
      setStatus(`Analyzing ${input.name}...`);

      try {
        // First get the geographical analysis
        const analysisRes = await axios.post(
          `${apiEndpoint}/api/aoi/analyze`,
          input,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        // Prepare data for DSS API
        const dssInput = {
          total_area_sq_m: analysisRes.data.summary.total_area_sq_m,
          agriculture_area_sq_m: analysisRes.data.summary.agriculture_area_sq_m || 0,
          water_area_sq_m: analysisRes.data.summary.water_area_sq_m || 0,
          forest_area_sq_m: analysisRes.data.summary.forest_area_sq_m || 0,
          infrastructure_area_sq_m: analysisRes.data.summary.infrastructure_area_sq_m || 0
        };

        // Get scheme recommendations
        const dssRes = await axios.post(
          `${apiEndpoint}/dss`,
          dssInput,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        // Return combined data
        return {
          ...analysisRes.data,
          schemes: dssRes.data
        };
      } catch (err) {
        console.error(`Error analyzing ${input.name}:`, err);
        return null;
      }
    };

    const selectedInput = aoiInputs[selectedAoiIndex];
    if (!selectedInput) return;

    analyzeArea(selectedInput).then((result) => {
      if (result) {
        setAoiResults((prevResults) => {
          const newResults = [...prevResults];
          newResults[selectedAoiIndex] = result;
          return newResults;
        });
        setStatus(`Analysis complete for ${selectedInput.name}`);
      } else {
        setStatus("Analysis failed. Please try again.");
      }
      setLoading(false);
    });
  }, [selectedAoiIndex, aoiInputs, apiEndpoint, token]);

  const selectedAoi = aoiResults[selectedAoiIndex];
  const selectedInput = aoiInputs[selectedAoiIndex];

  const center = selectedInput
    ? [selectedInput.latitude, selectedInput.longitude]
    : [17.385, 78.4867];

  const radius = selectedInput
    ? Math.sqrt(selectedInput.area_sq_m / Math.PI)
    : null;

  return (
    <div style={{ display: "flex", height: "100%", width: "100%" }}>
      <div
        style={{
          width: "300px",
          padding: "20px",
          borderRight: "1px solid #ddd",
          overflowY: "auto",
          backgroundColor: "#f5f5f5",
        }}
      >
        <h2 style={{ marginBottom: "20px" }}>AOI Locations</h2>
        {loading && (
          <div style={{ color: "#666" }}>
            <p>{status}</p>
          </div>
        )}
        {!loading && aoiInputs.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {aoiInputs.map((aoi, index) => (
              <button
                key={index}
                onClick={() => setSelectedAoiIndex(index)}
                style={{
                  padding: "15px",
                  border: "1px solid #ddd",
                  borderRadius: "6px",
                  backgroundColor: selectedAoiIndex === index ? "#e0e0e0" : "white",
                  cursor: "pointer",
                  textAlign: "left",
                  display: "flex",
                  flexDirection: "column",
                  gap: "5px",
                  transition: "all 0.2s ease",
                  boxShadow: selectedAoiIndex === index ? "0 2px 4px rgba(0,0,0,0.1)" : "none"
                }}
              >
                <strong>{aoi.name}</strong>
                <small style={{ color: "#666" }}>
                  {aoi.latitude.toFixed(4)}, {aoi.longitude.toFixed(4)}
                </small>
                {selectedAoiIndex === index && selectedAoi && (
                  <div style={{ marginTop: "8px", fontSize: "0.9em", color: "#444" }}>
                    {selectedAoi.summary && Object.entries(selectedAoi.summary).map(([key, value]) => (
                      key !== "name" && (
                        <div key={key}>
                          <strong>{key}:</strong> {typeof value === 'number' ? value.toFixed(2) : value}
                        </div>
                      )
                    ))}
                    
                    {selectedAoi.schemes && selectedAoi.schemes.length > 0 && (
                      <div style={{ marginTop: "12px", borderTop: "1px solid #ddd", paddingTop: "8px" }}>
                        <strong>Recommended Schemes:</strong>
                        {selectedAoi.schemes.filter(scheme => scheme.eligible).map((scheme, i) => (
                          <div key={i} style={{ marginTop: "4px", padding: "4px", backgroundColor: "white", borderRadius: "4px" }}>
                            <div style={{ fontWeight: "bold", color: "#2c5282" }}>{scheme.scheme}</div>
                            <div style={{ fontSize: "0.8em" }}>Score: {scheme.score}%</div>
                            <div style={{ fontSize: "0.8em", color: "#666" }}>{scheme.reason}</div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ flex: 1 }}>
        <MapContainer
          key={mapKey}
          center={center}
          zoom={12}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <FlyToController
            center={center}
            radius={radius}
            trigger={selectedAoiIndex}
          />
          {selectedAoi && (
            <>
              <Circle
                center={center}
                radius={radius}
                pathOptions={{ color: "#000", fillOpacity: 0.02 }}
              />
              <Marker position={center}>
                <Popup>{selectedAoi.summary.name}</Popup>
              </Marker>
              {selectedAoi.layers && selectedAoi.layers.map((layer, index) => {
                const layerClass = (layer.properties?.class || "").toLowerCase();
                const style = {
                  color: getLayerColor(layerClass),
                  fillColor: getLayerColor(layerClass),
                  fillOpacity: 0.5,
                  weight: 2
                };
                return (
                  <GeoJSON
                    key={index}
                    data={layer}
                    style={style}
                  />
                );
              })}
            </>
          )}
        </MapContainer>
      </div>
    </div>
  );
};

export default AOIMapper;
