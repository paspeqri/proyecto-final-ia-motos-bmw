<script lang="ts">
  import type { Fuente } from './api'
  export let fuentes: Fuente[]
  export let abrir: (id: string) => void
</script>

<div class="sources">
  <p class="sources-label">FUENTES · {fuentes.length} {fuentes.length === 1 ? 'registro consultado' : 'registros consultados'}</p>
  {#each fuentes as fuente (fuente.documento_id)}
    <details class="source">
      <summary><span class="record-id">{fuente.documento_id}</span><span class="source-summary-text"><span>{fuente.titulo}</span><span class="source-excerpt">{fuente.fragmento.split('\n').slice(2, 4).join(' ')}</span></span><span class="source-toggle" aria-hidden="true">+</span></summary>
      <div class="source-body">
        <p class="muted">Consultado el {fuente.fecha_consulta.split('-').reverse().join('/')} · {fuente.verificacion}</p>
        <blockquote>{fuente.fragmento}</blockquote>
        <button class="text-button" onclick={() => abrir(fuente.documento_id)}>Ver ficha y procedencia ↗</button>
      </div>
    </details>
  {:else}<p class="muted small">No hay registros que justifiquen una respuesta para esta consulta.</p>{/each}
</div>
