import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const destino = join(raiz, 'capturas')
const origen = process.env.MOTORATLAS_URL || 'http://127.0.0.1:5173'
await mkdir(destino, { recursive: true })
const salud = await fetch(`${origen}/api/health`, { signal: AbortSignal.timeout(10000) })
assert(salud.ok, 'Arranca Python y Vite antes de ejecutar las capturas')
const listado = await fetch(`${origen}/api/documentos`).then(r => r.json())
const documentos = new Map(listado.documentos.map(d => [d.id, d]))
const casos = [
  ['01-busqueda.json', '01-chat-busqueda.png', 'Búsqueda de una BMW R 1250 GS'],
  ['02-comparacion.json', '02-chat-comparacion.png', 'Comparación de las dos GS'],
  ['03-mantenimiento.json', '03-chat-mantenimiento.png', 'Mantenimiento y equipamiento'],
  ['04-matricula.json', '04-chat-no-consta.png', 'La matrícula no consta'],
]
const resultado = { fecha: new Date().toISOString(), origen, navegador: 'Microsoft Edge',
  viewport: { width: 1366, height: 900 }, total_documentos: listado.total, casos: [] }
const navegador = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const contexto = await navegador.newContext({ viewport: resultado.viewport, locale: 'es-ES',
    colorScheme: 'dark', reducedMotion: 'reduce', deviceScaleFactor: 1 })
  const pagina = await contexto.newPage()
  const errores = []
  pagina.on('pageerror', error => errores.push(error.message))
  await pagina.goto(origen, { waitUntil: 'networkidle' })
  await pagina.locator('.listing-card').first().waitFor()
  await pagina.addStyleTag({ content: '.chat-thread { max-height:430px !important; }' })

  for (const [entrada, archivo, titulo] of casos) {
    const { pregunta } = JSON.parse(await readFile(join(raiz, 'pruebas', entrada), 'utf8'))
    const previos = await pagina.locator('.assistant-message').count()
    await pagina.locator('#pregunta').fill(pregunta)
    const [respuestaHttp] = await Promise.all([
      pagina.waitForResponse(r => r.url().endsWith('/api/preguntar') &&
        r.request().method() === 'POST' && r.request().postDataJSON()?.pregunta === pregunta, { timeout: 120000 }),
      pagina.locator('.composer button[type="submit"]').click(),
    ])
    assert(respuestaHttp.ok(), `Error HTTP ${respuestaHttp.status()} al preguntar`)
    const respuesta = await respuestaHttp.json()
    assert(respuesta.respuesta.length > 30, 'Respuesta vacía o incompleta')
    assert(respuesta.fuentes.length === 2, 'Se esperan las dos fuentes de las GS')
    assert.equal(respuesta.no_consta, archivo.includes('no-consta'))
    if (respuesta.no_consta) assert.equal(respuesta.modelo_utilizado, false)
    for (const fuente of respuesta.fuentes) {
      assert(documentos.has(fuente.documento_id), 'Identificador de fuente desconocido')
      assert(documentos.get(fuente.documento_id).texto.includes(fuente.fragmento), 'Fragmento ajeno al registro')
    }
    const articulo = pagina.locator('.assistant-message').nth(previos)
    await articulo.locator('.answer-text').waitFor()
    await articulo.getByText(respuesta.respuesta, { exact: true }).waitFor()
    await articulo.locator('.source').last().waitFor()
    await pagina.locator('.composer textarea').waitFor({ state: 'visible' })
    await pagina.waitForFunction(() => !document.querySelector('.composer textarea').disabled)
    await pagina.evaluate(() => {
      const hilo = document.querySelector('.chat-thread')
      hilo.scrollTop = hilo.scrollHeight
      const chat = document.querySelector('#chat')
      window.scrollTo({ top: chat.getBoundingClientRect().top + scrollY - 90, behavior: 'instant' })
    })
    await pagina.waitForTimeout(250)
    for (const fuente of await articulo.locator('.source summary').all()) {
      const caja = await fuente.boundingBox()
      assert(caja && caja.y >= 0 && caja.y + caja.height <= 900, 'Las fuentes deben verse en la captura')
    }
    const textoVisible = await articulo.locator('.answer-text').innerText()
    assert.equal(textoVisible, respuesta.respuesta)
    await pagina.screenshot({ path: join(destino, archivo), fullPage: false, animations: 'disabled' })
    resultado.casos.push({ titulo, pregunta, archivo, ...respuesta,
      comprobaciones: { respuesta_real_http: true, fuentes_coinciden_con_corpus: true,
        fuentes_visibles_en_png: true, pantalla_no_vacia: true } })
    console.log(`${archivo}: respuesta real, ${respuesta.fuentes.length} fuentes visibles; no_consta=${respuesta.no_consta}`)
  }

  await pagina.locator('.topbar nav a[href="#registros"]').click()
  await pagina.evaluate(() => window.scrollTo({ top: document.querySelector('#registros').getBoundingClientRect().top + scrollY - 90, behavior: 'instant' }))
  await pagina.locator('.listing-card img').first().evaluate(async imagen => { await imagen.decode() })
  await pagina.waitForTimeout(200)
  assert.equal(await pagina.locator('.listing-card').count(), listado.total)
  await pagina.screenshot({ path: join(destino, '05-documentos.png'), fullPage: false, animations: 'disabled' })
  resultado.listado = { archivo: '05-documentos.png', total: listado.total,
    fuentes: [...new Set(listado.documentos.map(d => d.fuente))], foto_original_visible: true }
  assert.deepEqual(errores, [], 'No debe haber errores JavaScript')
  resultado.errores_javascript = errores
  await writeFile(join(destino, 'comprobacion.json'), JSON.stringify(resultado, null, 2) + '\n')
  console.log('05-documentos.png: listado real y foto original cargada')
  console.log('Guardadas cinco capturas y capturas/comprobacion.json')
} finally { await navegador.close() }
