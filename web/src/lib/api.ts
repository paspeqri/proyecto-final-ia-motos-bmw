export interface Documento {
  id: string; titulo: string; modelo: string; referencia: string; fuente: string
  vendedor: string | null; tipo_vendedor: string | null; ubicacion: string | null
  precio_eur: number | null; kilometros: number | null; anio: number | null; cilindrada_cm3: number | null
  ficha_tecnica: Record<string, string>; estado: string | null; mantenimiento: string | null
  equipamiento: string | null; garantia: string | null; condiciones: string | null
  matricula: string | null; itv: string | null; propietarios: string | null
  url: string; foto_url: string | null; fragmento_original: string; fecha_consulta: string
  verificacion: string; observaciones: string | null; texto: string
}
export interface Fuente {
  documento_id: string; titulo: string; url: string; fragmento: string
  fecha_consulta: string; verificacion: string
}
export interface Respuesta { respuesta: string; fuentes: Fuente[]; no_consta: boolean; modelo_utilizado: boolean }
export interface Mensaje { role: 'user' | 'assistant'; content: string; fuentes?: Fuente[]; no_consta?: boolean }
export const numero = (valor: number | null, unidad = '') => valor === null ? 'No consta' : `${new Intl.NumberFormat('es-ES').format(valor)}${unidad}`
export const euros = (valor: number | null) => numero(valor, ' €')
export const texto = (valor: string | null) => valor || 'No consta'

export async function api<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const respuesta = await fetch(`/api${ruta}`, { ...opciones, signal: opciones?.signal ?? AbortSignal.timeout(120000) })
  if (!respuesta.ok) {
    let detalle = 'No se pudo completar la solicitud.'
    try { const error = await respuesta.json(); if (typeof error.detail === 'string') detalle = error.detail } catch { /* Proxy sin respuesta de Python. */ }
    throw new Error(`Error ${respuesta.status}. ${detalle}`)
  }
  return respuesta.json() as Promise<T>
}
