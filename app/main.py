"""FastAPI application entry point for FinSight Agent."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.routes import query, health

# Initialize FastAPI app
app = FastAPI(
    title="FinSight Agent",
    description="An Explainable Agentic RAG System for Business Document Intelligence",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(query.router, tags=["RAG"])

# Mount static files (CSS, JS)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Serve index.html on root
from fastapi.responses import FileResponse

@app.get("/")
async def root():
    """Serve the main HTML page."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"message": "FinSight Agent API running. Visit /docs for API documentation."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
