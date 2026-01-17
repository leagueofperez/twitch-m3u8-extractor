# twitch_extractor.py
import re
from urllib.parse import quote as url_quote
import requests

CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"

RE_LIVE = re.compile(r"twitch\.tv/([^/]+)(?:\?|$)")
RE_VOD  = re.compile(r"twitch\.tv/(?:[^/]+/)?videos/(\d+)")

HEADERS = {
    "Client-ID": CLIENT_ID,
    "Accept": "application/vnd.twitchtv.v5+json",
    "User-Agent": "Mozilla/5.0"
}

def parse_master_m3u8(m3u8_url):
    resp = requests.get(m3u8_url, headers={"User-Agent":"Mozilla/5.0"})
    resp.raise_for_status()
    text = resp.text.splitlines()

    streams = {}
    last_info = None

    for line in text:
        line = line.strip()
        if line.startswith("#EXT-X-STREAM-INF:"):
            last_info = line
        elif last_info and line and not line.startswith("#"):
            info = last_info
            res = "unknown"
            fps = ""
            if "RESOLUTION=" in info:
                res = info.split("RESOLUTION=")[1].split(",")[0]
            if "FRAME-RATE=" in info:
                fps = info.split("FRAME-RATE=")[1].split(",")[0]

            name = res
            if fps:
                name = f"{res}_{fps}fps"

            stream_url = line
            if not line.startswith("http"):
                base = "/".join(m3u8_url.split("/")[:-1]) + "/"
                stream_url = base + line

            streams[name] = {"url": stream_url}
            last_info = None

        elif line.startswith("#EXT-X-MEDIA") and "TYPE=AUDIO" in line:
            if 'URI="' in line:
                uri = line.split('URI="')[1].split('"')[0]
                audio_url = uri
                if not uri.startswith("http"):
                    base = "/".join(m3u8_url.split("/")[:-1]) + "/"
                    audio_url = base + uri
                streams["audio_only"] = {"url": audio_url}

    return streams

def get_access_token(channel_or_id, is_live=True):
    url = "https://gql.twitch.tv/gql"
    payload = {
        "query": """
        query PlaybackAccessToken(
          $isLive: Boolean!,
          $login: String!,
          $isVod: Boolean!,
          $vodID: ID!,
          $playerType: String!,
          $platform: String!
        ) {
          streamPlaybackAccessToken(channelName: $login, params: {
            platform: $platform,
            playerBackend: "mediaplayer",
            playerType: $playerType
          }) @include(if: $isLive) {
            value
            signature
          }
          videoPlaybackAccessToken(id: $vodID, params: {
            platform: $platform,
            playerBackend: "mediaplayer",
            playerType: $playerType
          }) @include(if: $isVod) {
            value
            signature
          }
        }
        """,
        "variables": {
            "isLive": is_live,
            "login": channel_or_id if is_live else "",
            "isVod": not is_live,
            "vodID": channel_or_id if not is_live else "",
            "playerType": "site",
            "platform": "web"
        }
    }

    resp = requests.post(url, json=payload, headers=HEADERS)
    data = resp.json()

    if "data" not in data or not data["data"]:
        raise RuntimeError("Twitch no devolvió datos válidos.")

    token_obj = data["data"]["streamPlaybackAccessToken" if is_live else "videoPlaybackAccessToken"]
    if not token_obj:
        raise RuntimeError("No se pudo obtener el token (¿canal offline o VOD privado?)")
    return token_obj["value"], token_obj["signature"]

def build_usher_url(channel_or_id, is_live=True):
    token, sig = get_access_token(channel_or_id, is_live=is_live)
    base = "https://usher.ttvnw.net"
    if is_live:
        path = f"/api/channel/hls/{channel_or_id}.m3u8"
    else:
        path = f"/vod/{channel_or_id}.m3u8"
    params = {
        "client_id": CLIENT_ID,
        "token": token,
        "sig": sig,
        "allow_source": "true",
        "allow_audio_only": "true",
        "type": "any"
    }
    query = "&".join(f"{k}={url_quote(str(v))}" for k, v in params.items())
    return f"{base}{path}?{query}"

def quality_score(name):
    if name == "audio_only":
        return 0
    try:
        base = name.split("_")[0]
        w, h = base.split("x")
        h = int(h)
        fps = 30
        if "_60fps" in name or "_60" in name:
            fps = 60
        return h * 1000 + fps
    except:
        return 0

def extract_streams_from_url(twitch_url):
    m_vod = RE_VOD.search(twitch_url)
    m_live = RE_LIVE.search(twitch_url)

    if m_vod:
        vod_id = m_vod.group(1)
        m3u8_url = build_usher_url(vod_id, is_live=False)
    elif m_live:
        channel = m_live.group(1)
        m3u8_url = build_usher_url(channel, is_live=True)
    else:
        raise ValueError("URL de Twitch no válida")

    streams = parse_master_m3u8(m3u8_url)
    # Convertir a lista de dicts con clave "quality" y "url"
    stream_list = [
        {"quality": quality, "url": info["url"]}
        for quality, info in sorted(
            streams.items(),
            key=lambda x: quality_score(x[0]),
            reverse=True
        )
    ]
    return stream_list