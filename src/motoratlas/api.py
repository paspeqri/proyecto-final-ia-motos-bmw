"""Servidor local de MotorAtlas."""

from pathlib import Path
from contextlib import asynccontextmanager
import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from openai import OpenAIError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

from .rag import MotorRAG, Pregunta, Respuesta, normalizar
from .datos import foto_local

motor = MotorRAG()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No bloquear el listado de documentos si OpenAI está temporalmente caído.
    try:
        import asyncio
        await asyncio.to_thread(motor.indice.preparar)
    except (OpenAIError, RuntimeError, OSError, ValueError) as error:
        log.warning("Índice no disponible al arrancar (%s); se reintentará al preguntar", type(error).__name__)
    yield


app = FastAPI(title="MotorAtlas API", version="0.2.0", lifespan=lifespan)


@app.post("/api/preguntar", response_model=Respuesta)
def preguntar(peticion: Pregunta) -> Respuesta:
    try:
        return motor.preguntar(peticion)
    except (OpenAIError, RuntimeError, OSError) as error:
        log.warning("Servicio RAG no disponible: %s", type(error).__name__)
        raise HTTPException(503, "No se pudo consultar el servicio de IA. Revisa la clave y la conexión del servidor.") from None
    except ValueError:
        raise HTTPException(502, "El servicio de IA no devolvió datos válidos; vuelve a intentarlo.") from None


@app.get("/api/documentos")
def documentos(q: str = Query(default="", max_length=200), modelo: str | None = None,
               precio_max: float | None = Query(default=None, ge=0), tipo_vendedor: str | None = None,
               fuente: str | None = None):
    resultados = motor.documentos
    if q.strip():
        resultados = [d for d in resultados if normalizar(q.strip()) in normalizar(d["texto"])]
    if modelo:
        resultados = [d for d in resultados if normalizar(d["modelo"]) == normalizar(modelo)]
    if precio_max is not None:
        resultados = [d for d in resultados if d["precio_eur"] is not None and d["precio_eur"] <= precio_max]
    if tipo_vendedor:
        resultados = [d for d in resultados if normalizar(d["tipo_vendedor"] or "No consta") == normalizar(tipo_vendedor)]
    if fuente:
        resultados = [d for d in resultados if normalizar(d["fuente"]) == normalizar(fuente)]
    return {"total": len(resultados), "documentos": resultados}


@app.get("/api/documentos/{documento_id}")
def documento(documento_id: str):
    for registro in motor.documentos:
        if registro["id"] == documento_id:
            return registro
    raise HTTPException(404, "Registro no encontrado")


@app.get("/api/documentos/{documento_id}/foto", response_class=Response)
def foto(documento_id: str):
    if not any(d["id"] == documento_id and d["foto_url"] for d in motor.documentos):
        raise HTTPException(404, "El registro no tiene una foto incorporada")
    resultado = foto_local(documento_id)
    if resultado is None:
        raise HTTPException(404, "Foto no disponible")
    contenido, tipo = resultado
    return Response(contenido, media_type=tipo, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/health")
def health() -> dict[str, str]:
    """Permite comprobar la conexión entre Svelte, Vite y FastAPI."""
    return {"status": "ok", "service": "motoratlas-api"}


@app.get("/api/maquetas", include_in_schema=False)
def maquetas() -> FileResponse:
    """Muestra el prototipo HTML que ya existe en el proyecto."""
    return FileResponse(PROJECT_ROOT / "maquetas.html", media_type="text/html")
