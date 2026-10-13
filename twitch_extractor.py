# twitch_extractor.py
import random
import re
from urllib.parse import urlencode, urlparse

import requests

CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
GQL_URL = "https://gql.twitch.tv/gql"
USHER_URL = "https://usher.ttvnw.net"
SUPPORTED_CODECS = "h264"

RE_VOD = re.compile(r"/(?:[^/]+/)?v(?:ideos?)/(\d+)", re.IGNORECASE)
RE_CHANNEL = re.compile(r"^/([^/?#]+)/?$")
RE_CHANNEL_NAME = re.compile(r"^[A-Za-z0-9_]{4,25}$")
RE_BARE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
RE_BARE_VOD = re.compile(r"^\d{8,12}$")

RE_PLAYBACK_ACCESS_TOKEN = re.compile(r"^(\d+)p(\d+)?$")
RE_RESOLUTION = re.compile(r"RESOLUTION=(\d+)x(\d+)")
RE_RES_VALUE = re.compile(r"^(\d+)x(\d+)$")
RE_FRAME_RATE = re.compile(r"FRAME-RATE=([\d.]+)")
RE_ATTR = re.compile(r'([A-Z-]+)=("[^"]*"|[^,]*)')

HASH_TOKEN = "ed230aa1e33e07eebb8928504583da78a5173989fadfb1ac94be06a04f3cdbe9"
HASH_CHANNEL_SHELL = "fea4573a7bf2644f5b3f2cbbdcbee0d17312e48d2e55f080589d053aad353f11"
HASH_STREAM_METADATA = "b57f9b910f8cd1a4659d894fe7550ccc81ec9052c01e438b290fd66a040b9b93"

BLOCKED_SEGMENTS = ("videos", "video", "directory", "settings", "downloads",
                    "store", "subscriptions", "friends", "wallet", "drops",
                    "following", "search", "popout", "moderator", "u", "p")


class TwitchError(RuntimeError):
    """Error con mensaje apto para mostrar al usuario (nunca contiene tokens)."""


def _gql(queries):
    batched = isinstance(queries, list)
    payload = queries if batched else [queries]
    headers = {"Client-ID": CLIENT_ID, "User-Agent": "Mozilla/5.0"}
    resp = requests.post(GQL_URL, json=payload, headers=headers, timeout=25)
    resp.raise_for_status()
    data = resp.json()
    return data if batched else (data[0] if data else {})


def _persisted_query(operation, sha256, **variables):
    return {
        "operationName": operation,
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": sha256}},
        "variables": variables,
    }


def _validate_channel(name):
    if not RE_CHANNEL_NAME.match(name):
        shown = name[:32] + ("…" if len(name) > 32 else "")
        raise TwitchError(
            f"'{shown}' no es un nombre de canal válido. "
            "Debe tener entre 4 y 25 caracteres (letras, números o _)."
        )
    return name.lower()


def _from_bare_token(raw):
    token = raw.strip("/")
    if RE_BARE_VOD.fullmatch(token):
        return False, token
    if RE_BARE_TOKEN.fullmatch(token):
        return True, _validate_channel(token)
    raise TwitchError(
        "Entrada no reconocida. Usa el nombre del canal (p. ej. admiralbulldog), "
        "un ID de VOD, o una URL completa de Twitch."
    )


def parse_twitch_url(url):
    raw = (url or "").strip()
    if not raw:
        raise TwitchError("URL vacía")

    if "://" not in raw and "." not in raw.split("/")[0]:
        return _from_bare_token(raw)

    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    if not (host == "twitch.tv" or host.endswith(".twitch.tv")):
        raise TwitchError("Solo se soportan URLs de Twitch.")

    path = parsed.path or "/"

    vod = RE_VOD.search(path)
    if vod:
        return False, vod.group(1)

    channel = RE_CHANNEL.match(path)
    if channel:
        name = channel.group(1)
        if name.lower() not in BLOCKED_SEGMENTS:
            return True, _validate_channel(name)

    raise TwitchError("URL de Twitch no válida. Usa twitch.tv/<canal> o twitch.tv/videos/<id>.")


def fetch_playback_token(channel_or_id, is_live=True):
    """Devuelve (token, sig, reason).

    `reason` es None, "notfound" u "offline". No lanza por estar offline:
    ese dato solo sirve para dar un mensaje de error más claro si luego el
    manifiesto falla, ya que `streamPlaybackAccessToken` se devuelve incluso
    para canales desconectados.
    """
    queries = []
    if is_live:
        queries.append(
            _persisted_query("ChannelShell", HASH_CHANNEL_SHELL, login=channel_or_id)
        )
        queries.append(
            _persisted_query(
                "StreamMetadata",
                HASH_STREAM_METADATA,
                channelLogin=channel_or_id,
                includeIsDJ=True,
            )
        )

    token_slot = len(queries)
    queries.append(
        _persisted_query(
            "PlaybackAccessToken",
            HASH_TOKEN,
            isLive=is_live,
            login=channel_or_id if is_live else "",
            isVod=not is_live,
            vodID=channel_or_id if not is_live else "",
            playerType="embed",
            platform="site",
        )
    )

    try:
        data = _gql(queries)
    except requests.RequestException as exc:
        raise TwitchError(f"No se pudo contactar con Twitch: {exc.__class__.__name__}.")

    reason = None
    if is_live:
        shell = data[0].get("data") or {}
        metadata = data[1].get("data") or {}
        user_or_error = shell.get("userOrError") or {}
        user = metadata.get("user")
        if user_or_error.get("__typename") == "UserNotFound" or user is None:
            reason = "notfound"
        elif user.get("stream") is None:
            reason = "offline"

    entry = data[token_slot]
    key = "streamPlaybackAccessToken" if is_live else "videoPlaybackAccessToken"
    token_obj = (entry.get("data") or {}).get(key)

    if not token_obj:
        if reason == "notfound":
            raise TwitchError(f"El canal '{channel_or_id}' no existe.")
        if reason == "offline":
            raise TwitchError(f"El canal '{channel_or_id}' está offline.")
        if entry.get("errors"):
            raise TwitchError("Twitch rechazó la consulta de token de reproducción.")
        if is_live:
            raise TwitchError("Twitch no devolvió un token de reproducción para ese canal.")
        raise TwitchError(
            "No se pudo reproducir ese VOD. Puede estar eliminado, ser privado, "
            "tener restricción de edad o de suscripción."
        )

    return token_obj["value"], token_obj["signature"], reason


def build_usher_url(channel_or_id, token, sig, is_live=True):
    params = {
        "platform": "web",
        "p": random.randint(0, 999999),
        "allow_source": "true",
        "allow_audio_only": "true",
        "playlist_include_framerate": "true",
        "multigroup_video": "true",
        "supported_codecs": SUPPORTED_CODECS,
    }

    if is_live:
        path = f"/api/v2/channel/hls/{channel_or_id.lower()}.m3u8"
        params["sig"] = sig
        params["token"] = token
        params["fast_bread"] = "true"
    else:
        path = f"/vod/v2/{channel_or_id}.m3u8"
        params["nauthsig"] = sig
        params["nauth"] = token

    return f"{USHER_URL}{path}?{urlencode(params)}"


def _attrs(line):
    return {
        key: value.strip('"')
        for key, value in RE_ATTR.findall(line)
    }


NAME_ATTRS = ("VIDEO", "STABLE-VARIANT-ID", "IVS-NAME", "NAME", "GROUP-ID")


def _stream_name(info_attrs, group_id):
    for key in NAME_ATTRS:
        value = info_attrs.get(key)
        if value:
            return value
    if group_id:
        return group_id

    res = RE_RES_VALUE.match(info_attrs.get("RESOLUTION", ""))
    if res:
        fps = info_attrs.get("FRAME-RATE") or "30"
        try:
            fps_int = int(float(fps.split(".")[0]))
        except ValueError:
            fps_int = 30
        return f"{res.group(2)}p{fps_int}"

    return "unknown"


def _absolutize(url, base_url):
    if url.startswith(("http://", "https://")):
        return url
    return base_url + url.lstrip("/")


def parse_master_m3u8(m3u8_url):
    try:
        resp = requests.get(m3u8_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=25)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status == 404:
            raise TwitchError("Twitch no tiene un manifiesto para esa URL.")
        if status == 403:
            raise TwitchError("Manifiesto restringido por Twitch (403).")
        raise TwitchError(f"Twitch devolvió un error HTTP {status}.")
    except requests.RequestException as exc:
        raise TwitchError(f"No se pudo contactar con Twitch: {exc.__class__.__name__}.")

    base_url = m3u8_url.split("?")[0].rsplit("/", 1)[0] + "/"

    streams = {}
    group_id = None
    pending = None

    for raw in resp.text.splitlines():
        line = raw.strip()
        if not line:
            continue

        if line.startswith("#EXT-X-MEDIA"):
            group_id = _attrs(line).get("GROUP-ID") or group_id
            continue

        if line.startswith("#EXT-X-STREAM-INF"):
            pending = _stream_name(_attrs(line), group_id)
            group_id = None
            continue

        if line.startswith("#"):
            continue

        if pending:
            streams[pending] = {"url": _absolutize(line, base_url)}
            pending = None

    return streams


def quality_score(name):
    if name == "audio_only":
        return 0

    match = RE_PLAYBACK_ACCESS_TOKEN.match(name)
    if match:
        return int(match.group(1)) * 1000 + int(match.group(2) or 30)

    match = RE_RESOLUTION.search(name)
    if match:
        fps = 30
        res = RE_FRAME_RATE.search(name)
        if res:
            fps = int(float(res.group(1)))
        return int(match.group(2)) * 1000 + fps

    return 0


def extract_streams_from_url(twitch_url):
    is_live, target = parse_twitch_url(twitch_url)

    try:
        token, sig, reason = fetch_playback_token(target, is_live=is_live)
        m3u8_url = build_usher_url(target, token, sig, is_live=is_live)
    except TwitchError:
        raise
    except requests.RequestException as exc:
        raise TwitchError(f"No se pudo contactar con Twitch: {exc.__class__.__name__}.")

    try:
        streams = parse_master_m3u8(m3u8_url)
    except TwitchError:
        if reason == "offline":
            raise TwitchError(f"El canal '{target}' está offline.") from None
        if reason == "notfound":
            raise TwitchError(f"El canal '{target}' no existe.") from None
        raise
    except requests.RequestException as exc:
        raise TwitchError(f"No se pudo contactar con Twitch: {exc.__class__.__name__}.")

    if not streams:
        raise TwitchError(
            "No se encontraron streams. El canal podría haberse desconectado "
            "o la emisión tener restricciones de edad."
        )

    return [
        {"quality": quality, "url": info["url"]}
        for quality, info in sorted(
            streams.items(), key=lambda kv: quality_score(kv[0]), reverse=True
        )
    ]


__all__ = [
    "TwitchError",
    "extract_streams_from_url",
    "parse_master_m3u8",
    "parse_twitch_url",
    "quality_score",
]