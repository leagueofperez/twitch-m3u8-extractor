// static/script.js
import { ICON_OPEN, ICON_COPY } from './icons.js'
const COPY_FEEDBACK_MS = 1500

const COPY_BASE_CLASSES = 'bg-gray-100 hover:bg-gray-200 text-gray-700'
const COPY_OK_CLASSES = 'bg-green-600 text-white'

function escapeAttr(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function announce(message) {
  const status = document.getElementById('copyStatus')
  if (!status) return
  status.textContent = ''
  window.setTimeout(() => {
    status.textContent = message
  }, 50)
}

async function copyText(text) {
  if (window.isSecureContext && navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch (err) {
      // Sin permiso o sin soporte: se intenta el camino legacy.
    }
  }

  const helper = document.createElement('textarea')
  helper.value = text
  helper.setAttribute('readonly', '')
  helper.style.position = 'fixed'
  helper.style.top = '0'
  helper.style.left = '-9999px'
  helper.style.opacity = '0'
  document.body.appendChild(helper)

  let copied = false
  try {
    helper.select()
    helper.setSelectionRange(0, text.length)
    copied = document.execCommand('copy')
  } catch (err) {
    copied = false
  } finally {
    document.body.removeChild(helper)
  }

  return copied
}

function flashCopied(button) {
  if (button.dataset.flashing === '1') return
  button.dataset.flashing = '1'
  button.classList.remove(...COPY_BASE_CLASSES.split(' '))
  button.classList.add(...COPY_OK_CLASSES.split(' '))
  button.title = 'Copiado'

  window.setTimeout(() => {
    button.dataset.flashing = '0'
    button.classList.remove(...COPY_OK_CLASSES.split(' '))
    button.classList.add(...COPY_BASE_CLASSES.split(' '))
    button.title = `Copiar URL de ${button.dataset.quality}`
  }, COPY_FEEDBACK_MS)
}

async function extract() {
  const urlInput = document.getElementById('twitchUrl')
  const resultDiv = document.getElementById('result')
  const url = urlInput.value.trim()

  if (!url) {
    announce('Introduce un canal, un ID de VOD o una URL de Twitch.')
    return
  }

  resultDiv.innerHTML = '<p class="text-gray-500">Obteniendo calidades...</p>'

  try {
    const res = await fetch('/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url }),
    })

    const data = await res.json()

    if (data.error) {
      resultDiv.innerHTML = `
        <div class="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
          ❌ Error: ${data.error}
        </div>
      `
      return
    }

    if (!data.streams || data.streams.length === 0) {
      resultDiv.innerHTML = `
        <div class="p-4 bg-yellow-50 text-yellow-700 rounded-lg border border-yellow-200">
          ⚠️ No se encontraron calidades disponibles.
        </div>
      `
      return
    }

    let html = `
      <h3 class="text-xl font-semibold text-gray-800 mb-3">Calidades disponibles</h3>
      <div class="overflow-x-auto rounded-lg border border-gray-200">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Calidad</th>
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Acciones</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
    `

    for (const stream of data.streams) {
      const safeUrl = escapeAttr(stream.url)
      const label = escapeAttr(stream.quality)

      html += `
        <tr class="hover:bg-gray-50">
          <td class="px-4 py-3 text-sm font-mono text-gray-800 text-center">${label}</td>
          <td class="px-4 py-3">
            <div class="flex items-center justify-center gap-2">
              <a
                href="${safeUrl}"
                target="_blank"
                rel="noopener noreferrer"
                title="Abrir en reproductor"
                aria-label="Abrir ${label} en una pestaña nueva"
                class="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-twitch text-white text-xl transition-colors duration-150 hover:bg-twitch-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-twitch focus-visible:ring-offset-2"
              >${ICON_OPEN}</a>
              <button
                type="button"
                data-url="${safeUrl}"
                data-quality="${label}"
                title="Copiar URL de ${label}"
                aria-label="Copiar la URL de ${label}"
                class="inline-flex h-9 w-9 items-center justify-center rounded-lg text-xl transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-twitch focus-visible:ring-offset-2 ${COPY_BASE_CLASSES}"
              >${ICON_COPY}</button>
            </div>
          </td>
        </tr>
      `
    }

    html += `
          </tbody>
        </table>
      </div>
    `

    resultDiv.innerHTML = html
  } catch (err) {
    console.error(err)
    resultDiv.innerHTML = `
      <div class="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">
        ⚠️ Error de red: ${err.message || 'No se pudo conectar al servidor.'}
      </div>
    `
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('twitchUrl')
  if (input) {
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') extract()
    })
  }

  // El botón no usa onclick inline: en un módulo las declaraciones no viven
  // en window, así que un onclick="extract()" fallaría con ReferenceError.
  const extractBtn = document.getElementById('extractBtn')
  if (extractBtn) {
    extractBtn.addEventListener('click', () => extract())
  }

  // Delegación: la tabla se re-renderiza con innerHTML en cada extracción.
  const resultDiv = document.getElementById('result')
  if (resultDiv) {
    resultDiv.addEventListener('click', async (e) => {
      const button = e.target.closest('button[data-url]')
      if (!button) return

      const url = button.dataset.url
      const quality = button.dataset.quality

      const copied = await copyText(url)
      if (copied) {
        flashCopied(button)
        announce(`URL de ${quality} copiada al portapapeles.`)
      } else {
        announce(
          `No se pudo copiar la URL de ${quality}. Abre el stream y cópiala manualmente.`,
        )
      }
    })
  }
})
