// Prueba E2E con Chrome local, sin dependencias adicionales.
// Arrancar Chrome con --headless=new --remote-debugging-port=9223 y perfil temporal.
// Desde la raíz: node tests/test_web.mjs
import assert from 'node:assert/strict'
import { writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

// El primer arranque puede estar cargando el índice: esperar antes de navegar.
let servidorListo = false
for (let intento = 0; intento < 40; intento++) {
  try {
    const respuesta = await fetch('http://127.0.0.1:5173/api/health', {signal:AbortSignal.timeout(2000)})
    if (respuesta.ok) { servidorListo = true; break }
  } catch { /* Reintentar durante el arranque. */ }
  await new Promise(resolve => setTimeout(resolve, 250))
}
assert(servidorListo, 'Python y Vite deben estar disponibles antes de navegar')

const tabs = await fetch('http://127.0.0.1:9223/json/list').then(r => r.json())
const tab = tabs.find(t => t.type === 'page')
assert(tab, 'Chrome debe tener una pestaña')
const socket = new WebSocket(tab.webSocketDebuggerUrl)
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject })
let secuencia = 0
const pendientes = new Map()
const errores = []
const peticiones = []
socket.onmessage = ({data}) => {
  const mensaje = JSON.parse(data)
  if (mensaje.id) {
    const pendiente = pendientes.get(mensaje.id)
    pendientes.delete(mensaje.id)
    if (mensaje.error) pendiente.reject(new Error(mensaje.error.message))
    else pendiente.resolve(mensaje.result)
  }
  if (mensaje.method === 'Runtime.exceptionThrown') errores.push(mensaje.params.exceptionDetails.text)
  if (mensaje.method === 'Network.requestWillBeSent') peticiones.push(mensaje.params.request)
}
function cdp(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++secuencia
    pendientes.set(id, {resolve, reject})
    socket.send(JSON.stringify({id, method, params}))
  })
}
async function evaluar(expression) {
  const r = await cdp('Runtime.evaluate', {expression, returnByValue:true, awaitPromise:true})
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
  return r.result.value
}
async function esperar(expression, timeout = 60000) {
  const fin = Date.now() + timeout
  while (Date.now() < fin) {
    if (await evaluar(expression)) return
    await new Promise(r => setTimeout(r, 200))
  }
  throw new Error(`Tiempo agotado: ${expression}`)
}
async function valor(selector, value) {
  await evaluar(`(()=>{const e=document.querySelector(${JSON.stringify(selector)}); e.value=${JSON.stringify(value)}; e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`)
}
async function click(selector) { await evaluar(`document.querySelector(${JSON.stringify(selector)}).click()`) }

try {
  await cdp('Runtime.enable'); await cdp('Network.enable'); await cdp('Page.enable')
  await cdp('Emulation.setDeviceMetricsOverride', {width:1366,height:768,deviceScaleFactor:1,mobile:false})
  await cdp('Page.navigate', {url:'http://127.0.0.1:5173/'})
  await esperar("document.querySelectorAll('.listing-card').length === 68")
  await esperar("document.querySelector('.card-photo img')?.naturalWidth > 0")
  assert.equal(await evaluar('document.documentElement.scrollWidth <= innerWidth'), true, 'Sin desbordamiento en portátil')
  assert.equal(await evaluar("document.querySelectorAll('main > section').length"), 4, 'Cuatro pantallas apiladas')
  console.log('OK: 68 anuncios, fotos originales y cuatro pantallas en portátil')

  await valor('#modelo','R 1250 GS'); await valor('#precio','15600'); await valor('#vendedor','Concesionario')
  await esperar("document.querySelectorAll('.listing-card').length === 1 && document.querySelector('.listing-card').textContent.includes('MA-001')")
  await valor('#buscar','sin-coincidencias-xyz')
  await esperar("document.querySelector('#registros .empty-state')?.textContent.includes('No hay anuncios')")
  await click('.reset')
  await esperar("document.querySelectorAll('.listing-card').length === 68")
  await valor('#portal','Wallapop')
  await esperar("document.querySelectorAll('.listing-card').length === 16")
  await click('.reset')
  await esperar("document.querySelectorAll('.listing-card').length === 68")
  console.log('OK: filtros combinados, cero resultados, restablecer y filtro de portal')

  await click('.example-question')
  await esperar("document.querySelectorAll('.assistant-message').length === 1", 120000)
  assert.equal(await evaluar("document.querySelector('.assistant-message').textContent.includes('MA-001')"), true)
  await click('.assistant-message .source summary')
  await click('.assistant-message .source-body .text-button')
  await esperar("document.querySelector('.detail-meta .record-id')?.textContent === 'MA-001'")
  await click('.suggestions button:nth-child(3)')
  await esperar("document.querySelectorAll('.assistant-message').length === 2")
  assert.equal(await evaluar("document.querySelectorAll('.assistant-message')[1].textContent.includes('La matrícula no consta')"), true)
  assert.equal(await evaluar("document.querySelectorAll('.assistant-message')[1].querySelectorAll('.source').length"), 2, 'La matrícula conserva las dos fuentes de la conversación')
  const historial = peticiones.filter(p => p.url.endsWith('/api/preguntar')).map(p => JSON.parse(p.postData)).find(p => p.historial.length > 0)
  assert(historial, 'Se envía el historial real de la conversación')
  console.log('OK: chat real, historial, fuentes navegables y aviso de matrícula')

  await cdp('Emulation.setDeviceMetricsOverride', {width:390,height:844,deviceScaleFactor:1,mobile:true})
  assert.equal(await evaluar('document.documentElement.scrollWidth <= innerWidth'), true, 'Sin desbordamiento en móvil')
  assert.equal(peticiones.some(p => /^https?:/.test(p.url) && !p.url.startsWith('http://127.0.0.1:5173/')), false, 'Ninguna petición remota desde el navegador')
  assert.equal(errores.length, 0, `Errores JS: ${errores.join(', ')}`)
  await cdp('Emulation.setDeviceMetricsOverride', {width:1366,height:768,deviceScaleFactor:1,mobile:false})
  await evaluar('scrollTo(0,0)')
  const captura = await cdp('Page.captureScreenshot', {format:'png', captureBeyondViewport:false})
  const archivo = join(tmpdir(), 'motoratlas-interfaz.png')
  await writeFile(archivo, Buffer.from(captura.data,'base64'))
  console.log(`OK: móvil sin desbordamiento, sin errores JS ni peticiones remotas. Captura: ${archivo}`)
} finally { socket.close() }
