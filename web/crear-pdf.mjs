import assert from 'node:assert/strict'
import { access } from 'node:fs/promises'
import { constants } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { chromium } from 'playwright-core'

const raiz = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const html = join(raiz, 'entregable.html')
const salida = join(raiz, 'entregable.pdf')

await access(html, constants.R_OK)
const navegador = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const pagina = await navegador.newPage({ viewport: { width: 1366, height: 900 } })
  await pagina.goto(pathToFileURL(html).href, { waitUntil: 'load' })
  await pagina.evaluate(() => document.fonts.ready)
  const imagenes = await pagina.locator('.capture').evaluateAll(async elementos => {
    await Promise.all(elementos.map(imagen => imagen.decode()))
    return elementos.map(imagen => ({ src: imagen.getAttribute('src'), width: imagen.naturalWidth }))
  })
  assert.equal(imagenes.length, 5, 'El informe debe incluir las cinco capturas')
  assert(imagenes.every(imagen => imagen.width > 0), 'Todas las capturas deben cargar')
  await pagina.pdf({
    path: salida,
    format: 'A4',
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: false,
  })
  console.log(`PDF creado: ${salida}`)
  console.log(`Capturas incluidas: ${imagenes.length}`)
} finally {
  await navegador.close()
}
