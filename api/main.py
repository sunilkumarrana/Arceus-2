"""
Main FastAPI Application Entrypoint.
Assembles all API routers, initiates database lifecycle, and serves the Single-Page Web App.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from database.seed import seed_database
from api.routes_chat import router as chat_router
from api.routes_schemes import router as schemes_router
from api.routes_eligibility import router as eligibility_router
from api.routes_benchmark import router as benchmark_router
from api.routes_auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite database tables and seed data are ready
    try:
        seed_database()
    except Exception as e:
        print(f"Startup database warning: {e}")
    yield


app = FastAPI(
    title="सुविधा वाणी (SuvidhaVani) - AI Voice-First Scheme Agent",
    description="Multilingual AI Voice Assistant for Indian Welfare Schemes Discovery, Deterministic Eligibility, and Explainable Reasoning",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(chat_router)
app.include_router(schemes_router)
app.include_router(eligibility_router)
app.include_router(benchmark_router)
app.include_router(auth_router)


@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "SuvidhaVani AI Agent",
        "version": "2.0.0",
        "supported_languages": ["hi-IN", "en-IN", "te-IN"],
        "modules": [
            "Deterministic Rule Engine",
            "Multi-slot Vernacular NLU",
            "Contradiction Detector",
            "Vague Answer Disambiguator",
            "Entropy Question Minimizer",
            "SIH Judge Test Suite"
        ]
    }


# Mount static directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(base_dir, "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
