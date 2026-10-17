import { ICON_OPEN, ICON_COPY, ICON_LINK } from '../icons.js'

const COPY_BASE_CLASSES = 'bg-gray-100 hover:bg-gray-200 text-gray-700'

function escapeAttr(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

export function renderError(result, message) {
  result.innerHTML = `
    <div class="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
      ❌ Error: ${escapeAttr(message)}
    </div>
  `
}

export function renderEmpty(result) {
  result.innerHTML = `
    <div class="p-4 bg-yellow-50 text-yellow-700 rounded-lg border border-yellow-200">
      ⚠️ No se encontraron calidades disponibles.
    </div>
  `
}

function renderShortenButton(stream, label) {
  const shorten = stream.shorten || {}
  return `
    <button
      type="button"
      data-action="shorten"
      data-url="${escapeAttr(stream.url)}"
      data-quality="${label}"
      data-slug="${escapeAttr(shorten.slug || '')}"
      data-title="${escapeAttr(shorten.title || '')}"
      data-ts="${escapeAttr(shorten.ts ?? '')}"
      data-sig="${escapeAttr(shorten.sig || '')}"
      title="Acortar y copiar"
      aria-label="Acortar la URL de ${label} y copiarla"
      class="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 text-xl transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-twitch focus-visible:ring-offset-2"
    >${ICON_LINK}</button>
  `
}

function renderStream(stream, shortenerEnabled) {
  const url = escapeAttr(stream.url)
  const quality = escapeAttr(stream.quality)
  const shortenButton = shortenerEnabled
    ? renderShortenButton(stream, quality)
    : ''

  return `
    <tr class="hover:bg-gray-50">
      <td class="px-4 py-3 text-sm font-mono text-gray-800 text-center">${quality}</td>
      <td class="px-4 py-3">
        <div class="flex items-center justify-center gap-2">
          <a
            href="${url}"
            target="_blank"
            rel="noopener noreferrer"
            title="Abrir en reproductor"
            aria-label="Abrir ${quality} en una pestaña nueva"
            class="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-twitch text-white text-xl transition-colors duration-150 hover:bg-twitch-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-twitch focus-visible:ring-offset-2"
          >${ICON_OPEN}</a>
          <button
            type="button"
            data-action="copy"
            data-url="${url}"
            data-quality="${quality}"
            title="Copiar URL de ${quality}"
            aria-label="Copiar la URL de ${quality}"
            class="inline-flex h-9 w-9 items-center justify-center rounded-lg text-xl transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-twitch focus-visible:ring-offset-2 ${COPY_BASE_CLASSES}"
          >${ICON_COPY}</button>${shortenButton}
        </div>
      </td>
    </tr>
  `
}

export function renderStreams(result, streams) {
  const shortenerEnabled = result.dataset.shortener === '1'
  const rows = streams
    .map((stream) => renderStream(stream, shortenerEnabled))
    .join('')

  result.innerHTML = `
    <h3 class="text-xl font-semibold text-gray-800 mb-3">Calidades disponibles</h3>
    <div class="overflow-x-auto rounded-lg border border-gray-200">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Calidad</th>
            <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Acciones</th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">${rows}</tbody>
      </table>
    </div>
  `
}
