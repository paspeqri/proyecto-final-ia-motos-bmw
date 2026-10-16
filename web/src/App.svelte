<script lang="ts">
  import { onMount, tick } from 'svelte'
  import Fuentes from './lib/Fuentes.svelte'
  import { api, euros, numero, texto, type Documento, type Mensaje, type Respuesta } from './lib/api'

  const primeraPregunta = 'Busco una BMW R 1250 GS para viajar, hasta 17.000 €. ¿Qué opciones hay? Quiero saber kilómetros, ficha técnica y estado.'
  const sugerencias = ['Compara las dos R 1250 GS', '¿Qué mantenimiento y equipamiento tienen?', '¿Cuál es la matrícula?', 'Busca en Wallapop', 'Busca en Motos.net', 'Busca en Milanuncios']
  let mensajes = $state<Mensaje[]>([])
  let pregunta = $state('')
  let enviando = $state(false)
  let errorChat = $state('')
  let ausente = $state<Respuesta | null>(null)
  let conectado = $state(false)
  let consultandoConexion = $state(true)
  let todos = $state<Documento[]>([])
  let documentos = $state<Documento[]>([])
  let cargando = $state(true)
  let errorDocumentos = $state('')
  let busqueda = $state('')
  let modelo = $state('')
  let precio = $state<number | undefined>(undefined)
  let vendedor = $state('')
  let portal = $state('')
  let seleccion = $state<Documento | null>(null)
  let errorDetalle = $state('')
  let cargandoDetalle = $state(false)
  let vista = $state('chat')
  let imagenesFallidas = $state<string[]>([])
  let finalChat: HTMLDivElement
  let controlador: AbortController | undefined
  let detalleControlador: AbortController | undefined
  const modelos = $derived([...new Set(todos.map(d => d.modelo))].sort())
  const portales = $derived([...new Set(todos.map(d => d.fuente))].sort())

  async function comprobarConexion() {
    consultandoConexion = true
    try { const r = await api<{status: string}>('/health', { signal: AbortSignal.timeout(5000) }); conectado = r.status === 'ok' }
    catch { conectado = false } finally { consultandoConexion = false }
  }

  async function cargarDocumentos(signal?: AbortSignal) {
    cargando = true; errorDocumentos = ''
    const params = new URLSearchParams()
    if (busqueda.trim()) params.set('q', busqueda.trim())
    if (modelo) params.set('modelo', modelo)
    if (precio !== undefined) params.set('precio_max', String(precio))
    if (vendedor) params.set('tipo_vendedor', vendedor)
    if (portal) params.set('fuente', portal)
    try {
      const resultado = await api<{total: number; documentos: Documento[]}>(`/documentos?${params}`, { signal })
      if (!signal?.aborted) {
        documentos = resultado.documentos
        if (!params.size) {
          todos = resultado.documentos
          if (!seleccion && !cargandoDetalle) seleccion = todos[0] ?? null
        }
      }
    } catch (error) { if (!signal?.aborted) errorDocumentos = error instanceof Error ? error.message : 'No se pudieron cargar los anuncios.' }
    finally { if (!signal?.aborted) cargando = false }
  }

  $effect(() => {
    void busqueda; void modelo; void precio; void vendedor; void portal
    controlador?.abort(); controlador = new AbortController()
    const actual = controlador
    const timer = setTimeout(() => { void cargarDocumentos(actual.signal) }, 250)
    return () => { clearTimeout(timer); actual.abort() }
  })

  onMount(() => {
    void comprobarConexion()
    const observador = new IntersectionObserver(entradas => {
      for (const entrada of entradas) if (entrada.isIntersecting) vista = entrada.target.id === 'no-consta' ? 'chat' : entrada.target.id
    }, {rootMargin:'-90px 0px -55% 0px', threshold:0})
    document.querySelectorAll('main > section').forEach(seccion => observador.observe(seccion))
    void api<Respuesta>('/preguntar', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({pregunta:'¿Cuál es la matrícula de MA-001 y MA-002?', historial:[]})
    }).then(r => { ausente = r }).catch(() => { /* El botón permite reintentar la consulta. */ })
    return () => { controlador?.abort(); detalleControlador?.abort(); observador.disconnect() }
  })

  async function enviar(contenido = pregunta) {
    const consulta = contenido.trim()
    if (!consulta || enviando) return
    enviando = true; errorChat = ''
    const historial = mensajes.slice(-18).map(({role, content}) => ({role, content}))
    mensajes.push({role: 'user', content: consulta}); pregunta = ''
    try {
      const r = await api<Respuesta>('/preguntar', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({pregunta:consulta, historial})})
      mensajes.push({role:'assistant', content:r.respuesta, fuentes:r.fuentes, no_consta:r.no_consta})
      if (r.no_consta && /matr[ií]cul|placa/i.test(consulta)) ausente = r
      conectado = true
    } catch (error) {
      mensajes.pop(); pregunta = consulta
      errorChat = error instanceof Error ? error.message : 'No se ha podido enviar la pregunta.'
    } finally {
      enviando = false; await tick()
      finalChat?.scrollIntoView({behavior:'smooth', block:'nearest'})
    }
  }

  async function abrirDocumento(id: string) {
    detalleControlador?.abort(); detalleControlador = new AbortController()
    const actual = detalleControlador
    errorDetalle = ''; cargandoDetalle = true; seleccion = null; vista = 'detalle'
    try { const d = await api<Documento>(`/documentos/${encodeURIComponent(id)}`, {signal:actual.signal}); if (!actual.signal.aborted) seleccion = d }
    catch (error) { if (!actual.signal.aborted) errorDetalle = error instanceof Error ? error.message : 'No se pudo abrir el registro.' }
    finally {
      if (!actual.signal.aborted) {
        cargandoDetalle = false; await tick()
        document.getElementById('detalle')?.scrollIntoView({behavior:'smooth', block:'start'})
      }
    }
  }

  function reiniciarFiltros() { busqueda = ''; modelo = ''; precio = undefined; vendedor = ''; portal = '' }
  function fotoDisponible(d: Documento) { return d.foto_url && !imagenesFallidas.includes(d.id) }
  function falloFoto(id: string) { imagenesFallidas = [...imagenesFallidas, id] }
</script>

<svelte:head><title>MotorAtlas · Encuentra tu próxima BMW</title><meta name="description" content="Compara anuncios de BMW de segunda mano con un asistente que muestra sus fuentes." /></svelte:head>
<a class="skip-link" href="#contenido">Saltar al contenido</a>
<header class="topbar">
  <a class="brand" href="#chat" onclick={() => vista = 'chat'}><span class="brand-symbol" aria-hidden="true">↗</span> motor<span>atlas</span><span class="brand-tag">BMW OCCASION</span></a>
  <nav aria-label="Navegación principal"><a class:active={vista === 'chat'} href="#chat" onclick={() => vista = 'chat'}>Asistente</a><a class:active={vista === 'registros'} href="#registros" onclick={() => vista = 'registros'}>Anuncios <span class="count">{todos.length || '—'}</span></a><a class:active={vista === 'detalle'} href="#detalle" onclick={() => vista = 'detalle'}>Ficha de moto</a></nav>
  <button class="connection" class:online={conectado} onclick={comprobarConexion} disabled={consultandoConexion} title="Comprobar conexión con el servidor"><span class="status-dot"></span>{consultandoConexion ? 'Conectando…' : conectado ? 'Servidor conectado' : 'Sin conexión · reintentar'}</button>
</header>

<main id="contenido">
  <section id="chat" class="page-section" aria-labelledby="chat-title">
    <div class="section-label"><span>01</span> ASISTENTE DE BÚSQUEDA <span class="label-line"></span><span class="muted">Tu próxima ruta empieza aquí</span></div>
    <div class="app-shell">
      <aside class="sidebar"><div><p class="eyebrow">TU ESPACIO</p><a class="side-link selected" href="#chat">✦ Asistente ↗</a><a class="side-link" href="#registros" onclick={() => vista = 'registros'}>▦ Anuncios <span class="count">{todos.length || '—'}</span></a><a class="side-link" href="#detalle" onclick={() => vista = 'detalle'}>◈ Ficha de moto</a></div><div class="sidebar-note"><span class="trust-icon">✓</span><strong>Respuestas con respaldo</strong><p>Cada respuesta muestra los registros que la justifican. Si un dato falta, te lo decimos.</p><span class="tiny muted">Wallapop, Motos.net, Milanuncios y concesionarios.</span></div></aside>
      <div class="chat-panel">
        <div class="chat-heading"><div><p class="eyebrow">MENOS BÚSQUEDA. MÁS CARRETERA.</p><h1 id="chat-title">Encuentra tu próxima <span>BMW.</span></h1><p class="muted">Compara anuncios, pregunta por los detalles y comprueba las fuentes.</p></div><span class="assistant-emblem" aria-hidden="true">✦</span></div>
        <div class="chat-thread" role="log" aria-label="Conversación con el asistente" aria-live="polite" aria-busy={enviando}>
          {#if !mensajes.length}<div class="chat-welcome"><span class="assistant-mark" aria-hidden="true">✦</span><div><h2>¿Qué moto tienes en mente?</h2><p class="muted">Empieza con la búsqueda de las maquetas o escribe tu propia pregunta.</p><button class="example-question" disabled={enviando} onclick={() => enviar(primeraPregunta)}>{primeraPregunta}<span aria-hidden="true">↗</span></button></div></div>{/if}
          {#each mensajes as mensaje, indice (indice)}
            {#if mensaje.role === 'user'}<div class="user-message"><div class="user-bubble">{mensaje.content}</div><span class="avatar">TÚ</span></div>
            {:else}<article class="assistant-message"><span class="assistant-mark" aria-hidden="true">✦</span><div class="answer"><p class="answer-name">MOTORATLAS <span>Asistente</span></p>{#if mensaje.no_consta}<p class="missing-badge">✓ Información no disponible</p>{/if}<div class="answer-text">{mensaje.content}</div><Fuentes fuentes={mensaje.fuentes ?? []} abrir={abrirDocumento} /></div></article>{/if}
          {/each}
          {#if enviando}<div class="thinking" role="status"><span class="assistant-mark">✦</span> Consultando los registros y sus fuentes<span class="loading-dot">…</span></div>{/if}<div bind:this={finalChat}></div>
        </div>
        <div class="composer-area"><div class="suggestions" aria-label="Preguntas sugeridas">{#each sugerencias as sugerencia}<button class="chip" disabled={enviando} onclick={() => enviar(sugerencia)}>{sugerencia} ↗</button>{/each}</div>
          {#if errorChat}<p class="error-box" role="alert">{errorChat} Comprueba el servidor Python y vuelve a enviar la pregunta.</p>{/if}
          <form class="composer" onsubmit={(e) => { e.preventDefault(); void enviar() }}><label class="sr-only" for="pregunta">Pregunta al asistente</label><textarea id="pregunta" rows="2" maxlength="2000" bind:value={pregunta} placeholder="Pregunta por un modelo, presupuesto o equipamiento…" disabled={enviando} required></textarea><button class="send" type="submit" disabled={enviando || !pregunta.trim()} aria-label="Enviar pregunta">↑</button></form>
          <p class="disclaimer">Copia local consultada el 16/10/2026. Precio y disponibilidad sin confirmar.</p>
        </div>
      </div>
    </div>
  </section>

  <section id="no-consta" class="page-section" aria-labelledby="missing-title">
    <div class="section-label"><span>02</span> CONTINUACIÓN · INFORMACIÓN QUE NO CONSTA<span class="label-line"></span></div>
    <div class="continuation"><div class="continuation-title"><span class="assistant-mark">✦</span><span>Una GS para viajar <span class="muted">/ Continuación</span></span></div><div class="user-message"><div class="user-bubble">¿Me puedes dar la matrícula de esas dos BMW?</div><span class="avatar">TÚ</span></div>
      <div class="missing-notice"><span class="trust-icon">✓</span><div><h2 id="missing-title">La matrícula no consta en los datos disponibles.</h2><p>Los registros incorporados no contienen ese dato. No se deduce del modelo, del año ni de las fotografías.</p></div></div>
      {#if ausente}<div class="answer-text missing-response">{ausente.respuesta}</div><Fuentes fuentes={ausente.fuentes} abrir={abrirDocumento} />{:else}<p class="muted small">Consulta el servidor para ver los registros que respaldan este aviso en tu conversación.</p>{/if}
      <button class="secondary" disabled={enviando} onclick={() => enviar('¿Me puedes dar la matrícula de esas dos BMW?')}>{enviando ? 'Consultando…' : 'Consultar matrícula en la conversación'} ↗</button>
    </div>
  </section>

  <section id="registros" class="page-section" aria-labelledby="records-title">
    <div class="section-label"><span>03</span> BIBLIOTECA DE ANUNCIOS<span class="label-line"></span></div>
    <div class="section-heading"><div><p class="eyebrow">TUS FUENTES, EN UN SOLO SITIO</p><h2 id="records-title">Cada anuncio. Todos los detalles.</h2><p class="muted">Explora los registros incorporados al asistente y comprueba su procedencia.</p></div><span class="snapshot-badge">◷ Copia local · 16 oct 2026</span></div>
    <form class="filters" onsubmit={(e) => { e.preventDefault(); void cargarDocumentos() }}>
      <div class="search-field"><label for="buscar">Buscar en los registros</label><input id="buscar" type="search" maxlength="200" bind:value={busqueda} placeholder="Modelo, ubicación, equipamiento o referencia…" /></div>
      <div><label for="modelo">Modelo</label><select id="modelo" bind:value={modelo}><option value="">Todos los modelos</option>{#each modelos as nombre}<option value={nombre}>{nombre}</option>{/each}</select></div>
      <div><label for="precio">Precio máximo (€)</label><input id="precio" type="number" min="0" step="100" bind:value={precio} placeholder="Sin límite" /></div>
      <div><label for="vendedor">Tipo de vendedor</label><select id="vendedor" bind:value={vendedor}><option value="">Todos</option><option>Concesionario</option><option>Particular</option><option>No consta</option></select></div>
      <div><label for="portal">Procedencia</label><select id="portal" bind:value={portal}><option value="">Todas las fuentes</option>{#each portales as nombre}<option>{nombre}</option>{/each}</select></div><button class="reset" type="button" onclick={reiniciarFiltros}>Restablecer ↻</button>
    </form>
    <div class="results-heading"><p role="status">{cargando ? 'Buscando anuncios…' : `${documentos.length} anuncios encontrados`} <span class="muted">/ {todos.length || '—'} registros</span></p><span class="muted small">El estado y el mantenimiento los declara el anunciante.</span></div>
    {#if errorDocumentos}<div class="empty-state" role="alert"><h3>No se pudieron cargar los anuncios</h3><p>{errorDocumentos}</p><button class="secondary" onclick={() => cargarDocumentos()}>Volver a intentar</button></div>{:else if cargando}<div class="empty-state" aria-live="polite">Consultando el catálogo…</div>{:else if !documentos.length}<div class="empty-state"><span aria-hidden="true">⌕</span><h3>No hay anuncios con estos filtros</h3><p class="muted">Prueba otro modelo, amplía el presupuesto o restablece la búsqueda.</p><button class="secondary" onclick={reiniciarFiltros}>Mostrar todos los anuncios</button></div>{:else}<div class="records-grid">{#each documentos as d (d.id)}
      <article class="listing-card"><button class="card-photo" onclick={() => abrirDocumento(d.id)} aria-label={`Ver ficha de ${d.titulo}`}>
        {#if fotoDisponible(d)}<img src={`/api/documentos/${d.id}/foto`} alt={`BMW ${d.modelo} del anuncio ${d.referencia}`} loading="lazy" onerror={() => falloFoto(d.id)} />{:else}<div class="photo-placeholder"><svg viewBox="0 0 240 110" fill="none" aria-hidden="true"><circle cx="53" cy="76" r="25"/><circle cx="186" cy="76" r="25"/><path d="M53 76 88 37 137 48 160 18 177 18M137 48 186 76M53 76 116 76 137 48M88 37 77 29 59 29M100 34 127 27 152 31"/></svg><span>Sin foto incorporada</span></div>{/if}<span class="photo-source">{d.fuente}</span>
      </button><div class="card-body"><div class="card-top"><span class="record-id">{d.id}</span><span class="muted tiny">{texto(d.tipo_vendedor)}</span></div><h3>BMW {d.modelo}</h3><p class="card-price">{euros(d.precio_eur)}</p><div class="card-specs"><span>{numero(d.anio)}</span><span>{numero(d.kilometros, ' km')}</span><span>{texto(d.ubicacion)}</span></div><p class="card-condition">{d.estado ?? 'Ficha parcial: estado y mantenimiento no constan.'}</p><div class="card-footer"><span class="muted small">{texto(d.vendedor)}</span><button class="text-button" onclick={() => abrirDocumento(d.id)}>Ver ficha ↗</button></div></div></article>
    {/each}</div>{/if}<p class="disclaimer">Los resultados de portales pueden ser parciales. «No consta» significa que el dato no aparece en el registro incorporado.</p>
  </section>

  <section id="detalle" class="page-section" aria-labelledby="detail-title">
    <div class="section-label"><span>04</span> DETALLE DEL ANUNCIO<span class="label-line"></span></div>
    {#if errorDetalle}<div class="empty-state" role="alert">{errorDetalle}</div>{:else if cargandoDetalle}<div class="empty-state" role="status">Abriendo ficha…</div>{:else if seleccion}{@const d = seleccion}
      <div class="detail-heading"><div><div class="detail-meta"><span class="record-id">{d.id}</span><span class="muted">{d.fuente} · {d.referencia}</span></div><h2 id="detail-title">BMW {d.modelo}</h2><p class="muted">{texto(d.ubicacion)} · {texto(d.vendedor)} · {texto(d.tipo_vendedor)}</p></div><div class="detail-price">{euros(d.precio_eur)}<span>Precio publicado · sin confirmar</span></div></div>
      <div class="detail-grid"><div class="detail-main"><div class="detail-photo">{#if fotoDisponible(d)}<img src={`/api/documentos/${d.id}/foto`} alt={`Foto original del anuncio de BMW ${d.modelo}`} onerror={() => falloFoto(d.id)} /><span class="photo-source">Foto del anuncio original · {d.fuente}</span>{:else}<div class="photo-placeholder"><svg viewBox="0 0 240 110" fill="none" aria-hidden="true"><circle cx="53" cy="76" r="25"/><circle cx="186" cy="76" r="25"/><path d="M53 76 88 37 137 48 160 18 177 18M137 48 186 76M53 76 116 76 137 48M88 37 77 29 59 29M100 34 127 27 152 31"/></svg><span>No hay foto incorporada para este registro</span></div>{/if}</div>
        <div class="detail-facts"><div><span>Año</span><strong>{numero(d.anio)}</strong></div><div><span>Kilometraje</span><strong>{numero(d.kilometros, ' km')}</strong></div><div><span>Cilindrada publicada</span><strong>{numero(d.cilindrada_cm3, ' cm³')}</strong></div><div><span>Matrícula</span><strong>{texto(d.matricula)}</strong></div></div>
        <div class="detail-block"><h3>Ficha técnica publicada</h3>{#if Object.keys(d.ficha_tecnica).length}<dl class="technical-list">{#each Object.entries(d.ficha_tecnica) as [clave, valor]}<div><dt>{clave}</dt><dd>{valor}</dd></div>{/each}</dl>{:else}<p class="muted">No consta una ficha técnica en el registro disponible.</p>{/if}</div>
        <div class="detail-block"><h3>Descripción y procedencia</h3><p class="eyebrow">FRAGMENTO ORIGINAL INCORPORADO</p><blockquote>{d.fragmento_original}</blockquote><p class="muted small">Se conserva el fragmento disponible, no el texto íntegro del anuncio.</p>{#if d.observaciones}<p>{d.observaciones}</p>{/if}<p class="muted">Consultado el {d.fecha_consulta.split('-').reverse().join('/')}. {d.verificacion}</p><a class="external-link" href={d.url} target="_blank" rel="noopener noreferrer">Abrir anuncio original en {d.fuente} ↗</a></div>
      </div><aside class="detail-side"><div class="detail-block"><h3>Lo que declara el vendedor</h3><dl class="conditions">{#each [['Estado', d.estado], ['Mantenimiento', d.mantenimiento], ['Equipamiento', d.equipamiento], ['Garantía', d.garantia], ['Condiciones de venta', d.condiciones], ['ITV', d.itv], ['Propietarios anteriores', d.propietarios]] as [etiqueta, valor]}<div><dt>{etiqueta}</dt><dd>{texto(valor)}</dd></div>{/each}</dl></div><div class="trust-note"><span class="trust-icon">✓</span><h3>Comprueba antes de decidir</h3><p>Estos datos son una copia local del anuncio. Confirma precio, disponibilidad y condiciones con el vendedor.</p></div><button class="secondary full-width" disabled={enviando} onclick={() => { void enviar(`¿Qué información consta del anuncio ${d.id}?`); document.getElementById('chat')?.scrollIntoView({behavior:'smooth'}) }}>Preguntar por esta moto ↗</button></aside></div>
    {:else}<div class="empty-state"><h2 id="detail-title">Elige un anuncio para ver su ficha</h2><p class="muted">Puedes abrirlo desde el buscador o desde las fuentes del chat.</p><a href="#registros">Explorar anuncios ↗</a></div>{/if}
  </section>
  <footer><a class="brand" href="#chat">motor<span>atlas</span></a><p>BMW de segunda mano · Proyecto final · Datos locales con procedencia</p><a href="#chat">Volver arriba ↑</a></footer>
</main>
