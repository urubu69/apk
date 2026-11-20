"""
SpotyLink Mobile Server - Servidor Web & PWA para Android
Permite usar o SpotyLink no celular com o mesmo visual do Spotify,
suportando reprodução em segundo plano na tela de bloqueio do Android e instalação PWA.
"""

import os
import sys
import re
import json
import time
import socket
import shutil
import urllib.request
from flask import Flask, render_template, send_from_directory, jsonify, request, send_file, Response

import yt_dlp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
COVERS_DIR = os.path.join(BASE_DIR, "covers")
LIBRARY_FILE = os.path.join(BASE_DIR, "library.json")
MOBILE_DIR = os.path.join(BASE_DIR, "mobile")
TEMPLATES_DIR = os.path.join(MOBILE_DIR, "templates")
STATIC_DIR = os.path.join(MOBILE_DIR, "static")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(COVERS_DIR, exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)


def get_local_ip():
    """Descobre o IP da máquina na rede Wi-Fi local ignorando adaptadores virtuais como Hamachi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("25.") and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                return ip
    except Exception:
        pass
    return "127.0.0.1"


def get_ffmpeg_binary():
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    return None


def clean_url(raw_text):
    """
    Higieniza e adapta links para download no mobile:
    - Extrai a URL se houver texto ao redor (ex: link compartilhado pelo app do YouTube)
    - Converte m.youtube.com para www.youtube.com
    - Converte links de Shorts (youtube.com/shorts/ID) para formato padrão (watch?v=ID)
    - Remove parâmetros de rastreamento (si=, feature=)
    - Se for apenas texto (ex: nome da música), converte para busca automática no YouTube (ytsearch1:)
    """
    if not raw_text:
        return ""
    text = raw_text.strip()
    match = re.search(r'(https?://[^\s]+)', text)
    if match:
        url = match.group(1).rstrip('.,;!?)]}"\'')
        if "youtube.com" in url or "youtu.be" in url:
            url = url.replace("m.youtube.com", "www.youtube.com")
            if "/shorts/" in url:
                parts = url.split("/shorts/")[1].split("?")[0].split("&")[0]
                url = f"https://www.youtube.com/watch?v={parts}"
        return url
    
    # Se o usuário digitou o nome da música em vez de um link:
    return f"ytsearch1:{text}"


def format_time(seconds):
    if not seconds or seconds < 0:
        return "00:00"
    seconds = int(seconds)
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"


def load_library_data():
    if not os.path.exists(LIBRARY_FILE):
        return {"tracks": [], "playlists": [{"id": "downloads", "name": "Downloads", "is_system": True, "track_ids": []}]}
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return {"tracks": data, "playlists": [{"id": "downloads", "name": "Downloads", "is_system": True, "track_ids": [t["id"] for t in data]}]}
            return data
    except Exception:
        return {"tracks": [], "playlists": [{"id": "downloads", "name": "Downloads", "is_system": True, "track_ids": []}]}


def save_library_data(data):
    try:
        with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Erro] Falha ao salvar: {e}")


# --- ROTAS DA INTERFACE MÓVEL ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/manifest.json")
def manifest():
    return send_from_directory(MOBILE_DIR, "manifest.json", mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    return send_from_directory(MOBILE_DIR, "sw.js", mimetype="application/javascript")


# --- APIS REST ---
@app.route("/api/state")
def api_state():
    return jsonify(load_library_data())


@app.route("/api/audio/<track_id>")
def api_audio(track_id):
    # Procura por qualquer formato de áudio existente no disco
    for ext in ["mp3", "m4a", "webm", "opus", "ogg", "wav", "flac"]:
        path = os.path.join(DOWNLOADS_DIR, f"{track_id}.{ext}")
        if os.path.exists(path):
            mimes = {
                "mp3": "audio/mpeg",
                "m4a": "audio/mp4",
                "webm": "audio/webm",
                "opus": "audio/ogg",
                "ogg": "audio/ogg",
                "wav": "audio/wav",
                "flac": "audio/flac"
            }
            return send_file(path, mimetype=mimes.get(ext, "audio/mpeg"), conditional=True)
    return "Áudio não encontrado", 404


@app.route("/api/cover/<track_id>")
def api_cover(track_id):
    path = os.path.join(COVERS_DIR, f"{track_id}.jpg")
    if os.path.exists(path):
        return send_file(path, mimetype="image/jpeg")
    return send_from_directory(STATIC_DIR, "icon-192.png")


@app.route("/api/download", methods=["POST"])
def api_download():
    body = request.get_json() or {}
    raw_url = body.get("url", "").strip()
    if not raw_url:
        return jsonify({"success": False, "error": "Digite um link ou nome de música"}), 400

    url = clean_url(raw_url)
    ffmpeg_exe = get_ffmpeg_binary()

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOADS_DIR, '%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web', 'mweb']
            }
        }
    }

    # Se FFmpeg estiver disponível, converte para MP3; caso contrário, mantém formato nativo (ex: m4a/webm)
    if ffmpeg_exe:
        ydl_opts['ffmpeg_location'] = ffmpeg_exe
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Baixa e extrai tudo em uma única operação confiável
            info = ydl.extract_info(url, download=True)
            if 'entries' in info and info['entries']:
                info = info['entries'][0]

            track_id = info.get("id") or str(int(time.time()))
            title = info.get("title") or "Música Sem Título"
            uploader = info.get("uploader") or info.get("channel") or info.get("artist") or "Artista Desconhecido"
            duration = info.get("duration") or 0
            thumb_url = info.get("thumbnail")

            # Localiza o arquivo de áudio real gerado
            actual_file = None
            for ext in ["mp3", "m4a", "webm", "opus", "ogg", "wav"]:
                candidate = os.path.join(DOWNLOADS_DIR, f"{track_id}.{ext}")
                if os.path.exists(candidate):
                    actual_file = candidate
                    break

            cover_path = os.path.join(COVERS_DIR, f"{track_id}.jpg")
            if thumb_url:
                try:
                    req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=8) as resp, open(cover_path, "wb") as f_out:
                        f_out.write(resp.read())
                except Exception:
                    pass

            track_data = {
                "id": track_id,
                "title": title,
                "artist": uploader,
                "duration": duration,
                "duration_str": format_time(duration),
                "file_path": actual_file or os.path.join(DOWNLOADS_DIR, f"{track_id}.mp3"),
                "cover_path": cover_path if os.path.exists(cover_path) else "",
                "url": raw_url,
                "added_at": time.time()
            }

            data = load_library_data()
            exists = False
            for i, t in enumerate(data["tracks"]):
                if t["id"] == track_id:
                    data["tracks"][i] = track_data
                    exists = True
                    break
            if not exists:
                data["tracks"].append(track_data)

            # Garante presença na playlist Downloads
            dl_pl = next((p for p in data["playlists"] if p.get("id") == "downloads"), None)
            if dl_pl and track_id not in dl_pl["track_ids"]:
                dl_pl["track_ids"].append(track_id)

            save_library_data(data)
            return jsonify({"success": True, "track": track_data})

    except Exception as e:
        err_msg = str(e)
        if "ffprobe and ffmpeg not found" in err_msg:
            err_msg = "FFmpeg não encontrado. Execute no Termux: pkg install ffmpeg -y"
        return jsonify({"success": False, "error": err_msg}), 500


@app.route("/api/playlist/create", methods=["POST"])
def api_playlist_create():
    body = request.get_json() or {}
    name = body.get("name", "").strip()
    if not name:
        return jsonify({"success": False}), 400

    data = load_library_data()
    pl_id = f"pl_{int(time.time() * 1000)}"
    new_pl = {"id": pl_id, "name": name, "is_system": False, "track_ids": []}
    data["playlists"].append(new_pl)
    save_library_data(data)
    return jsonify({"success": True, "playlist": new_pl})


@app.route("/api/playlist/delete", methods=["POST"])
def api_playlist_delete():
    body = request.get_json() or {}
    pl_id = body.get("playlist_id")
    if not pl_id or pl_id == "downloads":
        return jsonify({"success": False, "error": "Playlist protegida"}), 400

    data = load_library_data()
    data["playlists"] = [p for p in data["playlists"] if p.get("id") != pl_id]
    save_library_data(data)
    return jsonify({"success": True})


@app.route("/api/playlist/rename", methods=["POST"])
def api_playlist_rename():
    body = request.get_json() or {}
    pl_id = body.get("playlist_id")
    new_name = body.get("name", "").strip()
    if not pl_id or not new_name or pl_id == "downloads":
        return jsonify({"success": False, "error": "Nome inválido"}), 400

    data = load_library_data()
    for p in data["playlists"]:
        if p.get("id") == pl_id:
            p["name"] = new_name
            break
    save_library_data(data)
    return jsonify({"success": True})


@app.route("/api/playlist/add_track", methods=["POST"])
def api_playlist_add():
    body = request.get_json() or {}
    pl_id = body.get("playlist_id")
    track_id = body.get("track_id")

    data = load_library_data()
    for p in data["playlists"]:
        if p["id"] == pl_id:
            if track_id not in p["track_ids"]:
                p["track_ids"].append(track_id)
            break
    save_library_data(data)
    return jsonify({"success": True})


@app.route("/api/playlist/remove_track", methods=["POST"])
def api_playlist_remove():
    body = request.get_json() or {}
    pl_id = body.get("playlist_id")
    track_id = body.get("track_id")

    data = load_library_data()
    for p in data["playlists"]:
        if p["id"] == pl_id:
            if track_id in p["track_ids"]:
                p["track_ids"].remove(track_id)
            break
    save_library_data(data)
    return jsonify({"success": True})


@app.route("/api/track/delete", methods=["POST"])
def api_track_delete():
    body = request.get_json() or {}
    track_id = body.get("track_id")

    data = load_library_data()
    # Remove das playlists
    for p in data["playlists"]:
        if track_id in p["track_ids"]:
            p["track_ids"].remove(track_id)

    # Remove de tracks
    data["tracks"] = [t for t in data["tracks"] if t["id"] != track_id]
    save_library_data(data)

    # Exclui arquivos
    try:
        for ext in ["mp3", "m4a", "webm", "opus", "ogg", "wav", "flac"]:
            p = os.path.join(DOWNLOADS_DIR, f"{track_id}.{ext}")
            if os.path.exists(p):
                os.remove(p)
        jpg_p = os.path.join(COVERS_DIR, f"{track_id}.jpg")
        if os.path.exists(jpg_p):
            os.remove(jpg_p)
    except Exception:
        pass

    return jsonify({"success": True})


def run_mobile_server(host=None, port=5000):
    # Detecta se está rodando diretamente no Android (Termux)
    is_android_termux = os.path.exists("/data/data/com.termux") or "PREFIX" in os.environ

    # Argumentos CLI para controle de segurança de rede
    if "--network" in sys.argv:
        host = "0.0.0.0"
    elif "--local" in sys.argv or is_android_termux:
        host = host or "127.0.0.1"
    else:
        host = host or "0.0.0.0"

    for i, arg in enumerate(sys.argv):
        if arg == "--host" and i + 1 < len(sys.argv):
            host = sys.argv[i + 1]

    ip = get_local_ip()
    print(f"\n=======================================================")
    print(f"🎵 SpotyLink Mobile Server iniciado!")
    if host == "127.0.0.1":
        print(f"🔒 Modo Local 100% Seguro (loopback 127.0.0.1)")
        print(f"   Inacessível para outros aparelhos na rede Wi-Fi.")
        print(f"📱 Abra no navegador: http://localhost:{port}")
    else:
        print(f"🌐 Modo Rede (0.0.0.0)")
        print(f"📱 Abra no navegador do Android: http://{ip}:{port} ou http://localhost:{port}")
    print(f"=======================================================\n")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    run_mobile_server()
