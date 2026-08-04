"""
Web Server Dashboard API for CNPJ Pipeline.
Built with FastAPI and WebSockets.
"""

import asyncio
import os
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import config
from downloader import Downloader
from scheduler import init_scheduler, pipeline_manager

app = FastAPI(title="CNPJ Pipeline Dashboard API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve web frontend static files
web_dir = os.path.join(os.path.dirname(__file__), "web")
if not os.path.exists(web_dir):
    os.makedirs(web_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=web_dir), name="static")


@app.on_event("startup")
def startup_event():
    """Initialize background scheduler on server startup."""
    init_scheduler()


from typing import List, Optional

class TriggerRequest(BaseModel):
    month: Optional[str] = None
    force: bool = False
    stages: Optional[List[str]] = None
    oracle_tables: Optional[List[str]] = None


TABLE_LABELS = {
    "cnaes": "CNAEs",
    "motivos": "Motivos",
    "municipios": "Municípios",
    "naturezas_juridicas": "Naturezas Jurídicas",
    "paises": "Países",
    "qualificacoes_socios": "Qualificações de Sócios",
    "empresas": "Empresas",
    "estabelecimentos": "Estabelecimentos",
    "socios": "Sócios",
    "dados_simples": "Dados do Simples",
}


@app.get("/")
def read_root():
    """Serve Dashboard main page."""
    index_file = os.path.join(web_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "CNPJ Pipeline API Running. Frontend index.html not found."}


@app.get("/api/status")
def get_status():
    """Get current pipeline execution status."""
    return pipeline_manager.status


@app.get("/api/months")
def get_months():
    """List available months from Receita Federal WebDAV."""
    try:
        downloader = Downloader(config)
        available = downloader.get_available_directories()
        return {"available_months": available, "latest": available[0] if available else None}
    except Exception as e:
        return {"error": str(e), "available_months": []}


@app.get("/api/tables")
def get_tables():
    """List available tables for Oracle migration."""
    tables_list = [{"name": name, "label": label} for name, label in TABLE_LABELS.items()]
    return {"tables": tables_list}


@app.post("/api/trigger")
def trigger_pipeline(req: TriggerRequest):
    """Trigger manual pipeline run for a specific month or latest with stage/table options."""
    if pipeline_manager.status["state"] in ["DOWNLOADING", "PROCESSING_PG", "MIGRATING_ORACLE", "CHECKING"]:
        return {"status": "error", "message": "Pipeline já está em execução!"}

    pipeline_manager.run_pipeline(
        target_month=req.month,
        force=req.force,
        stages=req.stages,
        oracle_tables=req.oracle_tables,
    )
    return {"status": "ok", "message": f"Pipeline iniciado para o mês: {req.month or 'Mais recente'}"}


@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """WebSocket endpoint for real-time progress and live logs."""
    await websocket.accept()
    queue = asyncio.Queue()
    pipeline_manager.log_listeners.append(queue)

    # Send initial status snapshot
    await websocket.send_json({"type": "status", "data": pipeline_manager.status})

    try:
        while True:
            # Send queued updates
            msg = await queue.get()
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        if queue in pipeline_manager.log_listeners:
            pipeline_manager.log_listeners.remove(queue)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.web_host, port=config.web_port)
