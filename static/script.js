// static/script.js

async function extract() {
  const urlInput = document.getElementById('twitchUrl')
  const resultDiv = document.getElementById('result')
  const url = urlInput.value.trim()

  if (!url) {
    alert('Por favor ingresa una URL.')
    return
  }

  resultDiv.innerHTML = '<p class="text-gray-500">Obteniendo calidades...</p>'

  try {
    const res = await fetch('/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
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
              <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Acción</th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
    `

    for (const stream of data.streams) {
      const safeUrl = stream.url.replace(/"/g, '&quot;')
      html += `
        <tr class="hover:bg-gray-50">
          <td class="px-4 py-3 text-sm font-mono text-gray-800 text-center">${stream.quality}</td>
          <td class="px-4 py-3 text-center">
            <a
              href="${safeUrl}"
              target="_blank"
              rel="noopener noreferrer"
              class="inline-block px-3 py-1.5 bg-twitch hover:bg-twitch-dark text-white text-sm font-medium rounded transition-colors duration-150"
            >
              Abrir en reproductor
            </a>
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

// Permitir Enter
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('twitchUrl')
  if (input) {
    input.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') extract()
    })
  }
})
