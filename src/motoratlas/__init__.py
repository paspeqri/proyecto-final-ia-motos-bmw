def main() -> None:
    """Arranca el servidor de desarrollo con `uv run motoratlas`."""
    import uvicorn

    uvicorn.run("motoratlas.api:app", host="127.0.0.1", port=8000, reload=True)
