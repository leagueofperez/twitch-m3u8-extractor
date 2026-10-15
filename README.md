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
   _persisted query_ (`PlaybackAccessToken`).
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

| Comando      | Qué hace                                        |
| ------------ | ----------------------------------------------- |
| `make ps`    | Estado de los contenedores y si la app responde |
| `make logs`  | Sigue los logs del contenedor                   |
| `make stop`  | Para **los dos** contenedores posibles          |
| `make clean` | Elimina contenedores e imagen                   |
| `make icons` | Regenera los iconos desde `assets/*.svg`        |
| `make help`  | Lista los comandos                              |

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

| Variable           | Por defecto              | Para qué sirve                                                                                                    |
| ------------------ | ------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `PUBLIC_URL`       | se deduce de la petición | Raíz absoluta del sitio para `canonical`, `og:url`, `manifest` y JSON-LD                                          |
| `PORT`             | `5000`                   | Puerto de escucha (lo usa `entrypoint.sh`)                                                                        |
| `WORKERS`          | `4`                      | Nº de workers de gunicorn. Cada uno es un proceso con memoria propia                                              |
| `SHORT_IO_API_KEY` | —                        | Clave secreta de [short.io](https://app.short.io/settings/integrations/api-key). Sin ella no hay botón de acortar |
| `SHORT_IO_DOMAIN`  | —                        | Dominio propio para los enlaces cortos, p. ej. `links.midominio.com`                                              |

Define estas variables en un `.env` en la raíz del proyecto. Hay una plantilla en
[`.env.example`](.env.example):

```bash
cp .env.example .env
$EDITOR .env
```

`.env` está en `.gitignore`, así que la clave de short.io no acaba en el
repositorio. Si no defines nada, todas las variables quedan vacías y la app
funciona igual: los meta tags se deducen de la petición y el botón de acortar no
aparece.

**El `.env` lo leen las dos formas de arrancar.** `make dev` usa `docker compose`,
que lo carga por su cuenta; `make run` usa `docker run`, que lo ignora salvo que
se le pase `--env-file`. Por eso `make run` lo incluye explícitamente:

```makefile
run: build
	docker run -d --name twitch-app -p 5000:5000 \
		$(if $(wildcard .env),--env-file .env,) \
		twitch-extractor
```

Sin ese `--env-file`, `make run` arrancaba igual de limpio pero **sin variables**:
el botón de acortar no aparecía y los meta tags quedaban con la URL deducida. Si
añadir variables al `.env` y no se ven en `make run`, casi siempre es esto.

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

### URLs cortas con short.io (opcional)

Una URL m3u8 de Twitch es un token de ~400 caracteres que además **cambia en cada
extracción**. El botón de enlace publica esa URL bajo un slug estable de tu
dominio, para poder pegarla en un reproductor:

```
twitch.tv/caedrel, calidad 720p60
  → https://links.midominio.com/caedrel-720p60
```

El slug es siempre `<canal>-<calidad>`, o `vod-<id>-<calidad>` para un VOD. El
suffix de calidad no es opcional: una extracción devuelve seis calidades del mismo
canal y, con solo el nombre de canal, las seis apuntarían al mismo path y solo
sobreviviría una.

Cada enlace se crea además con un título legible (`Twitch caedrel 720p60`, o
`Twitch VOD 2899093597 720p60` en un VOD), que se actualiza junto con el destino.

Al pulsar el botón la app comprueba si el enlace ya existe: si no, lo crea; si
existe, lo **actualiza** con la URL nueva. Así el enlace corto va siempre a
apuntar al stream actual.

```bash
docker run -d -p 5000:5000 \
  -e SHORT_IO_API_KEY="tu-clave-secreta" \
  -e SHORT_IO_DOMAIN="links.midominio.com" \
  twitch-extractor
```

Sin esas dos variables el botón no se renderiza y la app funciona exactamente
igual que sin acortado.

⚠️ **Dos cosas que conviene saber:**

- **La clave nunca sale del servidor.** Todo el diálogo con short.io ocurre en
  Flask; el navegador solo recibe la URL corta ya creada. Usa una clave
  **secreta**, no una pública.
- **El destino sigue siendo efímero.** En streams en vivo el token caduca en
  minutos: `links.tu-dominio.com/caedrel-720p60` dejará de reproducir hasta que
  alguien vuelva a extraer y actualizarlo. En **VODs** en cambio la URL es
  estable, así que el enlace corto es de larga duración.

Para probar el endpoint a mano, reenvía el bloque `shorten` que devuelve
`/extract` tal cual:

```bash
curl -sX POST http://localhost:5000/extract \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://twitch.tv/caedrel"}' > /tmp/e.json

jq -c '{url: .streams[0].url} + .streams[0].shorten' /tmp/e.json \
  | curl -sX POST http://localhost:5000/shorten \
      -H 'Content-Type: application/json' --data-binary @-
# {"shortUrl":"https://links.midominio.com/caedrel-720p60","slug":"caedrel-720p60","title":"Twitch caedrel 720p60","action":"created"}
```

`action` es `created`, `updated` o `unchanged`.

**Anti-abuso por firma, no por caché.** `/shorten` solo acepta URLs que este
servidor acaba de emitir. Sin esa comprobación, cualquiera podría subir al
dominio enlaces de phishing disfrazados de URLs cortas tuyas.

`/extract` no guarda esas URLs en ninguna parte: le **cifra** (HMAC-SHA256) la
URL, su slug y su título, y devuelve la firma junto con una marca de tiempo.
`/shorten` la comprueba y, si es auténtica y tiene menos de 30 minutos,
procede. El navegador solo reenvía los datos, no puede alterarlos.

Es sin estado a propósito. La primera versión guardaba las URLs en un
`OrderedDict` en memoria, y **fallaba en producción**: `entrypoint.sh` arranca
gunicorn con 4 workers, cada uno en su propio proceso con su propia memoria, así
que extraer por un worker y acortar por otro daba `400`. Medido: 8 de 12
peticiones fallaban. Además, reiniciar el contenedor borraba todo. Un archivo
compartido o bajar a un solo worker lo tapaban, pero ninguna opción es tan
simple como no guardar nada.

Como el límite de 20 peticiones por minuto y por IP se aplica en memoria, este
también es por worker: con los 4 workers por defecto el tope real es de hasta
80/min. Es una guarda best-effort contra el abuso casual, no un límite estricto;
la garantía dura es la firma. Si necesitas ajustarlo, cambia `--workers` en
`entrypoint.sh` (o pon `WORKERS` en el `.env`) para bajar el multiplicador.

#### Si responde `Domain not found` (HTTP 404)

Casi siempre es que `SHORT_IO_DOMAIN` no coincide **exactamente** con el hostname
de tu cuenta. Basta un tld equivocado (`.io` en vez de `.gy`, p. ej.). Se
comprueba sin tocar la app:

```bash
set -a; . ./.env; set +a
curl -s -H "Authorization: $SHORT_IO_API_KEY" https://api.short.io/api/domains \
  | jq -r '.[].hostname'
# debe incluir EXACTAMENTE lo que has puesto en SHORT_IO_DOMAIN
```

`HTTP 200` con la lista confirma además que la clave es válida. Ojo: la ruta es
`/api/domains`; `/v1/domains` no existe y devuelve 404 aunque la clave sea
correcta, lo que confunde el diagnóstico.

### Por qué no se usa el cliente de PyPI

En PyPI está `short-io-api-client`, pero **no es un cliente oficial de short.io**:
lo publica un tercero, auto-generado con `openapi-python-client` a partir del
OpenAPI spec, sin autor, sin licencia declarada y con una única versión (1.0.0,
2026-01-26). No aparece enlazado en la documentación de short.io.

short.io no publica cliente oficial para Python: los oficiales son
`@short.io/client-browser` y `@short.io/client-node`, ambos JavaScript, y su
propia guía de Python usa `requests` en crudo, que es lo que hace `shortener.py`.

Se evaluó migrar y el flujo pasaba de 56 a 22 líneas, pero arrastraba `httpx` (una
segunda pila HTTP, cuando el proyecto ya usa `requests`), `attrs` y
`python-dateutil`, ocupaba 1.75 MB y 195 modelos generados para tres llamadas, y
su transporte era más difícil de sustituir en tests. Si prefieres esa dependencia,
es un cambio contenido en `shortener.py`.

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

| Herramienta               | Para qué                                      |
| ------------------------- | --------------------------------------------- |
| `rsvg-convert`            | rasteriza los SVG (librsvg)                   |
| `convert`                 | solo para empaquetar el `.ico`                |
| `fontconfig` + una fuente | para el `<text>` de la imagen social          |
| `python3`                 | para inyectar la marca en la plantilla del OG |

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

| Entrada                               | Se interpreta como |
| ------------------------------------- | ------------------ |
| `admiralbulldog`                      | canal en vivo      |
| `twitch.tv/admiralbulldog`            | canal en vivo      |
| `https://twitch.tv/admiralbulldog/`   | canal en vivo      |
| `2899093597`                          | VOD (solo dígitos) |
| `https://twitch.tv/videos/2899093597` | VOD                |

**Respuesta correcta** (`200`):

```json
{
  "streams": [
    {
      "quality": "1080p60",
      "url": "https://eus22.playlist.ttvnw.net/v1/playlist/…"
    },
    {
      "quality": "audio_only",
      "url": "https://eus22.playlist.ttvnw.net/v1/playlist/…"
    }
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

| Mensaje                            | Causa                                                    |
| ---------------------------------- | -------------------------------------------------------- |
| `El canal 'x' está offline.`       | no está emitiendo                                        |
| `El canal 'x' no existe.`          | el canal no existe                                       |
| `No se pudo reproducir ese VOD…`   | eliminado, privado o con restricción de edad/suscripción |
| `Entrada no reconocida…`           | formato no válido                                        |
| `Solo se soportan URLs de Twitch.` | host distinto de `twitch.tv`                             |

Los errores nunca incluyen el token de reproducción de Twitch.

### `POST /shorten`

Solo existe si `SHORT_IO_API_KEY` y `SHORT_IO_DOMAIN` están definidas; si no,
responde `503`.

```bash
curl -sX POST http://localhost:5000/shorten \
  -H 'Content-Type: application/json' \
  -d '{"url": "<URL salida de /extract>"}'
```

```json
{
  "shortUrl": "https://links.midominio.com/caedrel-720p60",
  "slug": "caedrel-720p60",
  "title": "Twitch caedrel 720p60",
  "action": "created"
}
```

Cada enlace lleva además un título legible, del tipo `Twitch caedrel 720p60` o
`Twitch VOD 2899093597 720p60` para un VOD. Se envía tanto al crear el enlace
como al actualizarlo, para que el título no se quede obsoleto.

| `action`    | Significado                                              |
| ----------- | -------------------------------------------------------- |
| `created`   | el enlace no existía                                     |
| `updated`   | existía y apuntaba a una URL anterior; se ha actualizado |
| `unchanged` | ya apuntaba a esa misma URL; no se ha escrito nada       |

Rechaza con `400` cualquier URL que no haya emitido este servidor, y con `429` al
superar 20 peticiones por minuto desde la misma IP.

---

## Estructura del proyecto

```
├── app.py                     Rutas Flask, saneado de errores, URL del sitio
├── twitch_extractor.py        Token, manifiesto y parseo de calidades
├── shortener.py               Acortado con short.io, caché anti-abuso, límite
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
