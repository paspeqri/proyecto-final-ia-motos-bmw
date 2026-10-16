"""Extrae de nuevo los registros de las maquetas, sin acceder a los portales."""

from motoratlas.datos import preparar_datos


if __name__ == "__main__":
    documentos = preparar_datos()
    print(f"Guardados {len(documentos)} registros en datos/documentos.json")
