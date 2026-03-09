from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from src.database import init_database, get_schema_info
from src.conversation_store import ConversationStore
from src.cache import QueryCache
from src.logger import EventLogger
from src.rag import ValueIndex
from src.routes.chat import router as chat_router
from src.routes.chat_stream import router as chat_stream_router
from src.routes.query import router as query_router
from src.routes.export import router as export_router
from src.routes.conversations import router as conversations_router
from src.routes.suggestions import router as suggestions_router
from src.routes.dashboard import router as dashboard_router
from src.config import BASE_DIR


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: load CSVs into SQLite
    app.state.db = init_database()
    app.state.conversations = ConversationStore()
    app.state.cache = QueryCache()
    app.state.logger = EventLogger()
    app.state.value_index = ValueIndex(app.state.db)
    schema = get_schema_info(app.state.db)
    anomaly_count = schema.get("generic_anomaly", {}).get("row_count", 0)
    print(f"Database loaded: {anomaly_count} anomalies, 264 configurations")
    yield
    # Shutdown
    app.state.logger.close()
    app.state.conversations.close()
    app.state.db.close()


app = FastAPI(title="Prisme — Anomaly Insights", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(chat_router)
app.include_router(chat_stream_router)
app.include_router(query_router)
app.include_router(export_router)
app.include_router(conversations_router)
app.include_router(suggestions_router)
app.include_router(dashboard_router)


# Schema endpoint
@app.get("/api/schema")
async def schema_info():
    return get_schema_info(app.state.db)


# Logs endpoint
@app.get("/api/logs")
async def get_logs():
    return app.state.logger.get_recent()


# Serve frontend static files
interface_dir = BASE_DIR / "interface"
app.mount("/css", StaticFiles(directory=str(interface_dir / "css")), name="css")
app.mount("/js", StaticFiles(directory=str(interface_dir / "js")), name="js")


@app.get("/")
async def serve_frontend():
    return FileResponse(str(interface_dir / "index.html"))
