"""Corpus local reproducible a partir de las constantes de maquetas.html."""

import ast
import base64
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATOS = ROOT / "datos" / "documentos.json"


def reparar(texto: str) -> str:
    """Corrige únicamente secuencias UTF-8 mal decodificadas del HTML original."""
    def intento(match: re.Match) -> str:
        palabra = match.group()
        for codec in ("latin1", "cp1252"):
            try:
                corregida = palabra.encode(codec).decode("utf-8")
                if corregida.count("Ã") + corregida.count("Â") < palabra.count("Ã") + palabra.count("Â"):
                    return corregida
            except (UnicodeError, LookupError):
                pass
        return palabra
    return re.sub(r"\S+", intento, texto)


def preparar_datos() -> list[dict]:
    html = (ROOT / "maquetas.html").read_text(encoding="utf-8-sig")
    decoder = json.JSONDecoder()

    def constante(nombre: str):
        inicio = html.index("=", html.index(f"const {nombre}")) + 1
        return decoder.raw_decode(html[inicio:].lstrip())[0]

    resumen = ast.literal_eval(re.search(r"const summaries\s*=\s*(\{.*?\});", html, re.S).group(1))
    documentos = []
    for a in constante("importedRecords"):
        tecnica = {reparar(k): reparar(v) if isinstance(v, str) else v for k, v in a["technical"].items()}
        if a["dealerId"] == 476:
            tecnica["Distancia del suelo al asiento"] = "No consta; la fuente publica 850 cm, un valor incoherente"
        estado, mantenimiento, equipo = resumen[a["dealerId"]]
        documentos.append(dict(
            id=a["id"], referencia=tecnica.get("Referencia"), modelo=a["model"],
            titulo=f"BMW {a['model']} · {a['year']} · MotoLuxe",
            fuente="MotoLuxe", tipo_vendedor="Concesionario", vendedor="MotoLuxe", ubicacion="Madrid",
            precio_eur=a["price"], kilometros=a["km"], anio=a["year"], cilindrada_cm3=a["cc"],
            ficha_tecnica=tecnica, estado=estado, mantenimiento=mantenimiento, equipamiento=equipo,
            garantia="Incluida; la duración no está indicada, según el vendedor.",
            condiciones="Documentación a nombre del comprador y garantía incluidas, según el vendedor.",
            matricula=None, itv=None, propietarios=None, url=a["url"], foto_url=a["photoUrl"],
            fragmento_original=reparar(a["quote"]), fecha_consulta="2026-10-16",
            verificacion="Copia local de la ficha incorporada en las maquetas; disponibilidad y precio actual sin confirmar.",
            observaciones="Estado, mantenimiento y equipamiento declarados por el vendedor."
        ))
    for a in constante("portalResults"):
        documentos.append(dict(
            id=a["id"], referencia=a["sourceId"], modelo=a["model"],
            titulo=f"BMW {a['model']} · {a['portal']} · {a['sourceId']}",
            fuente=a["portal"], tipo_vendedor=None, vendedor=None, ubicacion=a["city"],
            precio_eur=a["price"], kilometros=a["km"], anio=a["year"], cilindrada_cm3=None, ficha_tecnica={},
            estado=None, mantenimiento=None, equipamiento=None, garantia=None, condiciones=None,
            matricula=None, itv=None, propietarios=None, url=a["url"], foto_url=None,
            fragmento_original=a["quote"], fecha_consulta="2026-10-16",
            verificacion=a["verification"], observaciones=a["note"] or None,
        ))
    for d in documentos:
        def dato(campo):
            return "No consta" if d[campo] is None else str(d[campo])
        lineas = [f"Registro: {d['id']}. {d['titulo']}.",
                  f"Fuente: {d['fuente']}. Referencia: {d['referencia']}.",
                  f"Precio publicado: {dato('precio_eur')} EUR. Kilómetros: {dato('kilometros')}. Año: {dato('anio')}. Cilindrada: {dato('cilindrada_cm3')} cm³.",
                  f"Ubicación: {dato('ubicacion')}. Vendedor: {dato('vendedor')}. Tipo: {dato('tipo_vendedor')}."]
        lineas += [f"Ficha técnica — {k}: {v}." for k, v in d["ficha_tecnica"].items()]
        lineas += [f"{c.capitalize()}: {dato(c)}." for c in ("estado", "mantenimiento", "equipamiento", "garantia", "condiciones", "matricula", "itv", "propietarios", "observaciones")]
        lineas += [f"Fragmento original: «{d['fragmento_original']}». Para los datos normalizados, véanse los campos anteriores.",
                   f"Consulta: {d['fecha_consulta']}. {d['verificacion']}"]
        d["texto"] = "\n".join(lineas)
    DATOS.parent.mkdir(parents=True, exist_ok=True)
    contenido = json.dumps(documentos, ensure_ascii=False, indent=2) + "\n"
    if not DATOS.exists() or DATOS.read_text(encoding="utf-8") != contenido:
        DATOS.write_text(contenido, encoding="utf-8")
    return documentos


def cargar_datos() -> list[dict]:
    if not DATOS.exists():
        return preparar_datos()
    return json.loads(DATOS.read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def foto_local(documento_id: str) -> tuple[bytes, str] | None:
    """Sirve la foto exacta ya incorporada al HTML, sin descargar recursos externos."""
    html = (ROOT / "maquetas.html").read_text(encoding="utf-8-sig")
    inicio = html.index("=", html.index("const importedRecords")) + 1
    registros = json.JSONDecoder().raw_decode(html[inicio:].lstrip())[0]
    for registro in registros:
        if registro["id"] == documento_id and registro.get("photo", "").startswith("data:image/"):
            cabecera, contenido = registro["photo"].split(",", 1)
            return base64.b64decode(contenido, validate=True), cabecera[5:].split(";", 1)[0]
    return None
