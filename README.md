# MotorAtlas

Agregador de demostración de anuncios de motos BMW usadas, con buscador y un
chat RAG que responde con fuentes y dice «no consta» cuando falta evidencia.
El servidor usa Python/FastAPI; la interfaz, Svelte, TypeScript y Vite. El
modelo de chat predeterminado es `gpt-4.1-mini` y los embeddings usan
`text-embedding-3-small`.

## Datos

El corpus local contiene 68 registros estáticos construidos para la maqueta:
ocho fichas de concesionario MotoLuxe y 60 resultados atribuidos a Wallapop,
Milanuncios y Motos.net. No se consultan anuncios en vivo; las fichas,
referencias y enlaces son datos de demostración. Estado, mantenimiento y
equipamiento se atribuyen al anunciante y la disponibilidad debe confirmarse.

## Arranque local

Requisitos: Python 3.13, `uv`, Node.js 24 y npm. Configura un `.env` local
copiando `.env.example` y añade tu clave de OpenAI; `.env` está excluido de Git.

Desde la raíz del proyecto, instala dependencias y arranca la API:

```powershell
uv sync --locked
uv run servidor.py
```

En otra terminal:

```powershell
cd web
npm ci
npm run dev
```

Abre http://127.0.0.1:5173. Para rehacer las capturas con Edge, arranca ambos
servidores y ejecuta desde `web/` `node capturas.mjs`. Para regenerar el PDF:
`node crear-pdf.mjs`.

## Preguntas comprobadas

1. «Busco una BMW R 1250 GS para viajar, hasta 17.000 €. ¿Qué opciones hay?
   Quiero saber kilómetros, ficha técnica y estado.»
2. «Compara las dos R 1250 GS».
3. «¿Qué mantenimiento y equipamiento tienen?».
4. «¿Me puedes dar la matrícula de esas dos BMW?» — respondió que no consta.

Las respuestas y citas se contrastaron con los registros locales MA-001 y
MA-002 de `datos/documentos.json`; las preguntas reproducibles están en
`pruebas/`. El informe explica qué campos y fragmentos revisar:
[entregable.pdf](entregable.pdf).
