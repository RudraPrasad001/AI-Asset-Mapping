from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils.earth_engine import initialize_earth_engine
from routers import aoi

# Initialize Earth Engine with project ID
GEE_PROJECT = "carbon-segment-466615-n9"
initialize_earth_engine(GEE_PROJECT)

# Create FastAPI app
app = FastAPI(
    title="AOI Mapper API",
    description="API for analyzing Areas of Interest using Earth Engine"
)

# Configure CORS
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(aoi.router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "AOI Mapper API is running"}

