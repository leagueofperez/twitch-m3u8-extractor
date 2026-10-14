# Twitch Stream Extractor

Extrae las URLs `.m3u8` de streams de **Twitch** en vivo y de VODs, separadas por
calidad, listas para abrir en cualquier reproductor compatible con HLS.

Pega el nombre del canal, su URL o la de un VOD, y obtienes una tabla con una URL
por calidad (`1080p60`, `720p60`, …, `audio_only`) con botones para abrirla en una
pestaña nueva o copiarla al portapapeles.

> Las URLs que devuelve son **tokens efímeros**: cambian en cada llamada y caducan
> a los pocos minutos. Es el comportamiento de Twitch, no un fallo. Lo normal es
> volver a extraer cuando deixen de reproducir.

---

## Índice

- [Cómo funciona](#cómo-funciona)
- [Arranque rápido](#arranque-rápido)
- [Configuración](#configuración)
- [Despliegue](#despliegue)
- [Generación de assets](#generación-de-assets)
- [API](#api)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Solución de problemas](#solución-de-problemas)

---

## Cómo funciona

El extractor reproduce el mismo proceso que usa la API pública de referencia
`pwn.sh/tools/streamapi.py`:

1. **Token de reproducción** — `POST` a `https://gql.twitch.tv/gql` con una
   *persisted query* (`PlaybackAccessToken`).
2. **Manifiesto maestro** — `GET` a `https://usher.ttvnw.net/api/v2/channel/hls/<canal>.m3u8`.
3. **URLs por calidad** — devuelve las URLs hijas que cuelgan del manifiesto.

Todo en **una sola petición** a GraphQL: el estado del canal y el token se piden
batched. La detección de canal offline no bloquea la extracción; solo sirve para
dar un mensaje más claro si el manifiesto falla, porque un falso "offline"
descartaría canales que sí están emitiendo.

---

## Arranque rápido

### Opción A — Docker (recomendada)

```bash
make run          # build + docker run en el puerto 5000
# o bien:
make build
docker run -d --name twitch-app -p 5000:5000 twitch-extractor
```

Abre <http://localhost:5000>.

### Opción B — Desarrollo con recarga

```bash
make dev          # docker-compose up --build
```

### Opción C — Local, sin Docker

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py     # http://localhost:5000
```

En producción se usa Gunicorn en vez del servidor de desarrollo:

```bash
gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
```

### Comandos disponibles

| Comando | Qué hace |
|---|---|
| `make ps` | Estado de los contenedores y si la app responde |
| `make logs` | Sigue los logs del contenedor |
| `make stop` | Para **los dos** contenedores posibles |
| `make clean` | Elimina contenedores e imagen |
| `make icons` | Regenera los iconos desde `assets/*.svg` |
| `make help` | Lista los comandos |

`make ps` distingue los dos nombres de contenedor que genera el proyecto —`twitch-app`
(`make run`) y `twitch-extractor` (`make dev`)— e indica cuál de los dos lo arrancó:

```console
$ make ps
twitch-app  [make run]
    estado  : running
    puertos : 5000/tcp -> 0.0.0.0:5000 5000/tcp -> [::]:5000
    http    : OK (200) en http://localhost:5000/
```

> Ojo: `twitch-extractor` es también el nombre de la **imagen** que crea
> `make build`. `make ps` solo mira contenedores, así que no los confunde.

`make stop` trata los dos nombres a propósito. Un `docker compose down` a secas
solo pararía el contenedor de `make dev` y dejaría en marcha el de `make run`,
que es fácil de no notar: `make ps` sigue diciendo `running` y parece que no pasó
nada.

```console
$ make stop
  parado: twitch-app

$ make stop          # idempotente
  twitch-app ya estaba parado
```

---

## Configuración

Todo se controla por variables de entorno. Ninguna es obligatoria.

| Variable | Por defecto | Para qué sirve |
|---|---|---|
| `PUBLIC_URL` | se deduce de la petición | Raíz absoluta del sitio para `canonical`, `og:url`, `manifest` y JSON-LD |
| `PORT` | `5000` | Puerto de escucha (lo usa `entrypoint.sh`) |

### `PUBLIC_URL`

Si no se define, la app usa `request.url_root`, que **funciona sin configurar
nada** en local y en red local. Pero detrás de un reverse proxy puede devolver el
esquema o el host interno en vez del público, y entonces los meta tags quedarían
con una URL incorrecta. **Fíjalo siempre en producción:**

```bash
docker run -d -p 5000:5000 \
  -e PUBLIC_URL="https://extractor.midominio.com" \
  twitch-extractor
```

Acepta barra final o no; se normaliza. Ejemplos válidos:

```
PUBLIC_URL=https://extractor.midominio.com
PUBLIC_URL=https://extractor.midominio.com/
```

---

## Despliegue

### Con `docker compose`

```yaml
services:
  twitch-extractor:
    container_name: twitch-extractor
    build: .
    ports:
      - "5000:5000"
    environment:
      PUBLIC_URL: "https://extractor.midominio.com"
      PORT: "5000"
```

⚠️ **Ojo con el `docker-compose.yml` del repositorio**: está pensado para
desarrollo, no para producción.

- `command: python app.py` **sobrescribe el entrypoint**, así que arranca el
  servidor de desarrollo de Flask en vez de Gunicorn. Quítalo para usar Gunicorn.
- `volumes: - .:/app` monta el directorio de trabajo, así que los cambios en el
  host se reflejan de inmediato. Bien para desarrollo; en producción convendría
  quitarlo para no depender del sistema de ficheros del host.
- Declara una red externa `npm_network` que debe existir antes:

  ```bash
  docker network create npm_network
  ```

### Detrás de un reverse proxy

Sirve la app por HTTP y deja el TLS en el proxy (Caddy, nginx, Traefik…).

1. Exporta `PUBLIC_URL` con el dominio público y esquema `https`.
2. Si el proxy no reenvía cabeceras de protocolo, **fíjalo también** en la app con
   `ProxyFix`:

   ```python
   from werkzeug.middleware.proxy_fix import ProxyFix
   app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
   ```

3. `POST /extract` no necesita CSRF ni cookies: es un endpoint público de solo
   lectura. Aun así, si lo expones a internet, pon un límite de peticiones
   (nginx `limit_req` o similar): cada extracción consume cuota con Twitch.

---

## Generación de assets

`assets/icon.svg` es la **única fuente de verdad visual**. Todos los PNG, el `.ico`
y la imagen social se rasterizan desde ahí.

### El flujo

```
assets/icon.svg  ──┬─► favicon.svg            (vectorial, el que usan los navegadores modernos)
                   ├─► favicon-16x16.png  favicon-32x32.png  favicon-48x48.png
                   ├─► favicon.ico              (empaqueta los tres anteriores)
                   ├─► apple-touch-icon.png           180x180
                   └─► android-chrome-192x192.png  /  android-chrome-512x512.png

assets/og.svg  ─────► og-image.png           1200x630 (imagen para redes sociales)
                         ↑
                         └── el generador inyecta aquí el contenido de icon.svg
```

### Cómo cambiar la marca

```bash
$EDITOR assets/icon.svg     # cambia color, formas, proportions…
make icons                  # regenera TODO
git add assets static
```

No hay que recrear ninguna imagen a mano.

### Requisitos del generador

Se ejecuta **en tu máquina, no dentro del contenedor**: la imagen
`python:3.11-slim` no incluye rasterizadores ni fuentes.

```bash
# Debian / Ubuntu
sudo apt install librsvg2-bin imagemagick fontconfig fonts-dejavu-core
```

| Herramienta | Para qué |
|---|---|
| `rsvg-convert` | rasteriza los SVG (librsvg) |
| `convert` | solo para empaquetar el `.ico` |
| `fontconfig` + una fuente | para el `<text>` de la imagen social |
| `python3` | para inyectar la marca en la plantilla del OG |

Sin fuentes instaladas la imagen social se genera **sin texto** (el resto sale
bien).

### `assets/og.svg`

Es una plantilla, no la fuente de la marca. El generador sustituye el marcador
`{{ICON_BODY}}` por el contenido de `icon.svg`, así que puedes retocar la
composición, los colores y los textos sin que se desincronice del icono.

Para cambiar el diseño de la imagen social (no la marca), edita `assets/og.svg` y
ejecuta `make icons`.

### Archivos generados

Se **commitean** en `static/` (unos 132 KB en total) para que el despliegue no
necesite las herramientas de rasterizado.

---

## API

### `POST /extract`

```bash
curl -sX POST http://localhost:5000/extract \
  -H 'Content-Type: application/json' \
  -d '{"url": "admiralbulldog"}'
```

Acepta cualquiera de estas formas en `url`:

| Entrada | Se interpreta como |
|---|---|
| `admiralbulldog` | canal en vivo |
| `twitch.tv/admiralbulldog` | canal en vivo |
| `https://twitch.tv/admiralbulldog/` | canal en vivo |
| `2899093597` | VOD (solo dígitos) |
| `https://twitch.tv/videos/2899093597` | VOD |

**Respuesta correcta** (`200`):

```json
{
  "streams": [
    { "quality": "1080p60",    "url": "https://eus22.playlist.ttvnw.net/v1/playlist/…" },
    { "quality": "audio_only", "url": "https://eus22.playlist.ttvnw.net/v1/playlist/…" }
  ]
}
```

Viene ordenada de mayor a menor calidad, con `audio_only` al final.

Dos matices sobre las URLs y la lista:

- En streams en vivo cuelgan de `*.playlist.ttvnw.net/v1/playlist/…`; en VODs
  suelen ir a un host de CloudFront. Ambos son válidos.
- Las emisiones **en vertical** añaden variantes `*-portrait`
  (`720p60-portrait`, `480p30-portrait`, …). Se listan después de las normales,
  porque no son comparables en altura.

**Errores** (`400` con `{"error": "…"}`):

| Mensaje | Causa |
|---|---|
| `El canal 'x' está offline.` | no está emitiendo |
| `El canal 'x' no existe.` | el canal no existe |
| `No se pudo reproducir ese VOD…` | eliminado, privado o con restricción de edad/suscripción |
| `Entrada no reconocida…` | formato no válido |
| `Solo se soportan URLs de Twitch.` | host distinto de `twitch.tv` |

Los errores nunca incluyen el token de reproducción de Twitch.

---

## Estructura del proyecto

```
├── app.py                     Rutas Flask, saneado de errores, URL del sitio
├── twitch_extractor.py        Token, manifiesto y parseo de calidades
├── templates/index.html       Interfaz y meta tags (OG, JSON-LD, favicons)
├── static/
│   ├── script.js              Lógica de la interfaz (módulo ES)
│   ├── icons.js               Los 2 SVG de react-icons usados
│   ├── styles.css
│   ├── site.webmanifest       ← generado
│   ├── robots.txt             ← generado
│   └── iconos y og-image      ← generados
├── assets/
│   ├── icon.svg               ★ Fuente de verdad de la marca
│   └── og.svg                 Plantilla de la imagen social
├── tools/generate-assets.sh   Generador (make icons)
├── Dockerfile
├── docker-compose.yml         Desarrollo
├── entrypoint.sh              Gunicorn
└── Makefile
```

---

## Solución de problemas

**`make icons` falla con `falta rsvg-convert`**
Instala las dependencias del sistema (ver [Requisitos](#requisitos-del-generador)).

**La imagen social sale sin texto**
No hay fuentes instaladas. `fc-list` no debería devolver nada.

**La imagen social sale con el fondo pero sin la marca**
Falta `rsvg-convert`: revisa que el `make icons` no haya fallado a medias.

**`docker compose up` falla con la red `npm_network`**
Es una red externa: créala antes con `docker network create npm_network`.

**Los meta tags muestran una URL interna**
Falta `PUBLIC_URL` o el proxy no reenvía cabeceras. Ver
[Detrás de un reverse proxy](#detrás-de-un-reverse-proxy).

**Una URL extraída deja de reproducir**
Es lo esperado: los tokens caducan en minutos. Vuelve a extraer.

**El canal aparece offline pero sí emite**
A veces `StreamMetadata` va desfasado. Si es persistente, revisa que la extracción
no esté bloqueándose por el estado: el diseño actual pide el manifiesto aunque el
canal figure como offline, y solo usa ese dato para mejorar el mensaje de error.

---

## Licencia

Dominio público ([Unlicense](LICENSE)).