async function postJson(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  return response.json()
}

export function extractStreams(url) {
  return postJson('/extract', { url })
}

export function shortenStream(button) {
  return postJson('/shorten', {
    url: button.dataset.url,
    slug: button.dataset.slug,
    title: button.dataset.title,
    ts: button.dataset.ts,
    sig: button.dataset.sig,
  })
}
