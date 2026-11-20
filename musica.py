"""
SpotyLink - Reprodutor de Música por Link (Estilo Spotify)
Desenvolvido em Python com CustomTkinter, Pygame e yt-dlp.
Suporte a Downloads Automáticos e Playlists Personalizadas.
"""

import os
import sys
import re
import json
import time
import math
import random
import socket
import shutil
import urllib.request
import threading
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw

import customtkinter as ctk
import pygame
import yt_dlp
import imageio_ffmpeg

try:
    import qrcode
except ImportError:
    qrcode = None

# ==========================================
# CONFIGURAÇÕES E CONSTANTES VISUAIS (SPOTIFY)
# ==========================================
SPOTIFY_GREEN = "#1DB954"
SPOTIFY_GREEN_HOVER = "#1ED760"
SPOTIFY_BLACK = "#121212"
SPOTIFY_SIDEBAR = "#000000"
SPOTIFY_CARD = "#181818"
SPOTIFY_CARD_HOVER = "#282828"
SPOTIFY_ACTIVE = "#2A2A2A"
SPOTIFY_BORDER = "#282828"
TEXT_WHITE = "#FFFFFF"
TEXT_MUTED = "#B3B3B3"
TEXT_SUBTLE = "#727272"
ACCENT_RED = "#E91429"

# Diretórios base
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
COVERS_DIR = os.path.join(BASE_DIR, "covers")
LIBRARY_FILE = os.path.join(BASE_DIR, "library.json")

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(COVERS_DIR, exist_ok=True)


# ==========================================
# UTILITÁRIOS AUXILIARES E ÍCONES
# ==========================================
def get_asset_path(filename):
    """Localiza recursos estáticos seja em modo script ou compilado com PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        p = os.path.join(sys._MEIPASS, filename)
        if os.path.exists(p):
            return p
    return os.path.join(BASE_DIR, filename)


def set_window_icon(window):
    """Define o ícone oficial da nota musical verde na janela e na barra de tarefas do Windows."""
    ico_path = get_asset_path("icon.ico")
    png_path = get_asset_path("icon.png")
    if os.path.exists(ico_path):
        try:
            window.iconbitmap(ico_path)
        except Exception:
            pass
    if os.path.exists(png_path):
        try:
            icon_img = ImageTk.PhotoImage(Image.open(png_path))
            window.wm_iconphoto(True, icon_img)
            window._icon_photo_ref = icon_img
        except Exception:
            pass


def format_time(seconds):
    """Converte segundos para formato MM:SS ou HH:MM:SS."""
    if not seconds or seconds < 0:
        return "00:00"
    seconds = int(seconds)
    mins = seconds // 60
    secs = seconds % 60
    if mins >= 60:
        hrs = mins // 60
        mins = mins % 60
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def get_ffmpeg_binary():
    """Localiza o binário do ffmpeg no sistema ou pelo imageio-ffmpeg."""
    sys_ffmpeg = shutil.which("ffmpeg")
    if sys_ffmpeg:
        return sys_ffmpeg
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def get_local_ip():
    """Descobre o IP da máquina na rede local ignorando adaptadores virtuais como Hamachi."""
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


def clean_url(raw_text):
    """Higieniza e adapta links para download no desktop e mobile."""
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
    return f"ytsearch1:{text}"


def create_placeholder_cover(size=(64, 64), text="♫"):
    """Cria uma imagem de capa estilizada padrão caso a música não tenha thumbnail."""
    img = Image.new("RGB", size, color=SPOTIFY_CARD)
    draw = ImageDraw.Draw(img)
    margin = int(size[0] * 0.15)
    draw.ellipse((margin, margin, size[0] - margin, size[1] - margin), fill="#282828", outline=SPOTIFY_GREEN, width=2)
    return img


# ==========================================
# GERENCIADOR DA BIBLIOTECA E PLAYLISTS
# ==========================================
class LibraryManager:
    def __init__(self):
        self.tracks = []      # Lista com todas as músicas salvas
        self.playlists = []   # Lista com as playlists (Downloads + customizadas)
        self.load_library()

    def load_library(self):
        data = None
        if os.path.exists(LIBRARY_FILE):
            try:
                with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"[Aviso] Falha ao ler library.json: {e}")
                data = None

        if isinstance(data, list):
            # Compatibilidade com formato anterior
            self.tracks = data
            self.playlists = [
                {
                    "id": "downloads",
                    "name": "Downloads",
                    "is_system": True,
                    "track_ids": [t.get("id") for t in self.tracks if "id" in t]
                }
            ]
        elif isinstance(data, dict):
            self.tracks = data.get("tracks", [])
            self.playlists = data.get("playlists", [])
        else:
            self.tracks = []
            self.playlists = []

        # Garante que a playlist fixa 'downloads' existe e é a primeira
        has_downloads = False
        for p in self.playlists:
            if p.get("id") == "downloads":
                has_downloads = True
                p["is_system"] = True
                p["name"] = "Downloads"
                break

        if not has_downloads:
            self.playlists.insert(0, {
                "id": "downloads",
                "name": "Downloads",
                "is_system": True,
                "track_ids": [t.get("id") for t in self.tracks if "id" in t]
            })

        # Valida músicas existentes fisicamente no disco
        valid_tracks = []
        valid_ids = set()
        for t in self.tracks:
            if os.path.exists(t.get("file_path", "")):
                valid_tracks.append(t)
                valid_ids.add(t["id"])
        self.tracks = valid_tracks

        # Remove IDs fantasmas das playlists
        for p in self.playlists:
            p["track_ids"] = [tid for tid in p.get("track_ids", []) if tid in valid_ids]

        # Garante que toda música baixada está na playlist Downloads
        downloads_pl = self.get_playlist("downloads")
        if downloads_pl:
            for tid in valid_ids:
                if tid not in downloads_pl["track_ids"]:
                    downloads_pl["track_ids"].append(tid)

        self.save_library()

    def save_library(self):
        try:
            data = {
                "tracks": self.tracks,
                "playlists": self.playlists
            }
            with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Erro] Falha ao salvar library.json: {e}")

    # --- Métodos de Músicas ---
    def get_track_by_id(self, track_id):
        for t in self.tracks:
            if t["id"] == track_id:
                return t
        return None

    def add_downloaded_track(self, track_data):
        """Adiciona uma música e a vincula automaticamente à playlist Downloads."""
        # Se já existe, atualiza
        existing_idx = -1
        for i, t in enumerate(self.tracks):
            if t["id"] == track_data["id"]:
                existing_idx = i
                self.tracks[i] = track_data
                break
        if existing_idx == -1:
            self.tracks.append(track_data)

        # Adiciona obrigatoriamente na playlist fixa 'downloads'
        downloads_pl = self.get_playlist("downloads")
        if downloads_pl and track_data["id"] not in downloads_pl["track_ids"]:
            downloads_pl["track_ids"].append(track_data["id"])

        self.save_library()
        return track_data

    def remove_track_from_library(self, track_id):
        """Exclui permanentemente uma música do disco e de todas as playlists."""
        for p in self.playlists:
            if track_id in p.get("track_ids", []):
                p["track_ids"].remove(track_id)

        track_to_remove = None
        for t in self.tracks:
            if t["id"] == track_id:
                track_to_remove = t
                break

        if track_to_remove:
            self.tracks.remove(track_to_remove)
            try:
                if os.path.exists(track_to_remove.get("file_path", "")):
                    os.remove(track_to_remove["file_path"])
                if os.path.exists(track_to_remove.get("cover_path", "")):
                    os.remove(track_to_remove["cover_path"])
            except Exception as e:
                print(f"[Aviso] Falha ao deletar arquivo local: {e}")

        self.save_library()

    # --- Métodos de Playlists ---
    def get_playlist(self, playlist_id):
        for p in self.playlists:
            if p["id"] == playlist_id:
                return p
        return None

    def get_playlist_tracks(self, playlist_id):
        pl = self.get_playlist(playlist_id)
        if not pl:
            return []
        lookup = {t["id"]: t for t in self.tracks}
        return [lookup[tid] for tid in pl.get("track_ids", []) if tid in lookup]

    def create_playlist(self, name):
        name = name.strip()
        if not name:
            return None
        pl_id = f"pl_{int(time.time() * 1000)}_{random.randint(100, 999)}"
        new_pl = {
            "id": pl_id,
            "name": name,
            "is_system": False,
            "track_ids": []
        }
        self.playlists.append(new_pl)
        self.save_library()
        return new_pl

    def delete_playlist(self, playlist_id):
        if playlist_id == "downloads":
            return False  # Downloads não pode ser deletada
        for p in self.playlists:
            if p["id"] == playlist_id:
                self.playlists.remove(p)
                self.save_library()
                return True
        return False

    def rename_playlist(self, playlist_id, new_name):
        if playlist_id == "downloads":
            return False
        new_name = new_name.strip()
        if not new_name:
            return False
        for p in self.playlists:
            if p["id"] == playlist_id:
                p["name"] = new_name
                self.save_library()
                return True
        return False

    def add_track_to_playlist(self, playlist_id, track_id):
        pl = self.get_playlist(playlist_id)
        if pl:
            if track_id not in pl["track_ids"]:
                pl["track_ids"].append(track_id)
                self.save_library()
                return True
        return False

    def remove_track_from_playlist(self, playlist_id, track_id):
        if playlist_id == "downloads":
            self.remove_track_from_library(track_id)
            return True
        pl = self.get_playlist(playlist_id)
        if pl and track_id in pl["track_ids"]:
            pl["track_ids"].remove(track_id)
            self.save_library()
            return True
        return False

    def clear_all(self):
        for t in self.tracks:
            try:
                if os.path.exists(t.get("file_path", "")):
                    os.remove(t["file_path"])
                if os.path.exists(t.get("cover_path", "")):
                    os.remove(t["cover_path"])
            except Exception:
                pass
        self.tracks = []
        self.playlists = [
            {
                "id": "downloads",
                "name": "Downloads",
                "is_system": True,
                "track_ids": []
            }
        ]
        self.save_library()


# ==========================================
# MOTOR DE ÁUDIO (PYGAME AUDIO PLAYER)
# ==========================================
class AudioEngine:
    def __init__(self):
        pygame.mixer.init()
        self.current_track = None
        self.current_index = -1
        self.is_playing = False
        self.is_paused = False
        self.current_pos = 0.0
        self.duration = 0.0
        self.volume = 0.8
        self.last_tick = time.time()
        self.shuffle = False
        self.repeat_mode = "off"  # "off", "all", "one"
        pygame.mixer.music.set_volume(self.volume)

    def load_and_play(self, track, index, start_pos=0.0):
        try:
            pygame.mixer.music.unload()
            file_path = track["file_path"]
            if not os.path.exists(file_path):
                return False

            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play(start=start_pos)
            self.current_track = track
            self.current_index = index
            self.is_playing = True
            self.is_paused = False
            self.current_pos = start_pos
            self.duration = track.get("duration", 0.0)
            self.last_tick = time.time()
            return True
        except Exception as e:
            print(f"[Erro de Reprodução]: {e}")
            self.is_playing = False
            return False

    def pause(self):
        if self.is_playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True

    def resume(self):
        if self.is_playing and self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.last_tick = time.time()

    def toggle_play_pause(self):
        if not self.is_playing and self.current_track:
            return self.load_and_play(self.current_track, self.current_index, self.current_pos)
        if self.is_paused:
            self.resume()
        else:
            self.pause()
        return True

    def stop(self):
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        self.is_playing = False
        self.is_paused = False
        self.current_pos = 0.0

    def seek(self, target_seconds):
        if not self.current_track:
            return
        target_seconds = max(0.0, min(float(target_seconds), self.duration))
        try:
            pygame.mixer.music.play(start=target_seconds)
            self.current_pos = target_seconds
            self.last_tick = time.time()
            if self.is_paused:
                pygame.mixer.music.pause()
        except Exception as e:
            print(f"[Erro ao buscar]: {e}")

    def set_volume(self, vol):
        self.volume = max(0.0, min(1.0, float(vol)))
        pygame.mixer.music.set_volume(self.volume)


# ==========================================
# INTERFACE PRINCIPAL (SPOTIFY CLONE)
# ==========================================
class SpotyLinkApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurações da Janela
        self.title("SpotyLink - Reprodutor de Música por Link & Playlists")
        self.geometry("1140x740")
        self.minsize(1000, 620)
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("green")
        self.configure(fg_color=SPOTIFY_BLACK)

        # Aplica o ícone da nota musical verde
        set_window_icon(self)

        # Componentes do Backend
        self.library = LibraryManager()
        self.player = AudioEngine()
        self.is_dragging_slider = False
        self.cover_cache = {}

        # Estado da Interface
        self.active_playlist_id = "downloads"  # Playlist atualmente aberta na tela
        self.playback_playlist_id = "downloads"  # Playlist atualmente tocando no player
        self.playback_tracks = []  # Faixas da playlist em reprodução
        self.active_search_query = ""

        # Placeholder Cover
        self.placeholder_img = create_placeholder_cover((64, 64))
        self.placeholder_thumb = create_placeholder_cover((44, 44))

        # Construção dos Layouts
        self._build_gui()

        # Teclas de atalho e Teclas Multimídia (Teclado, Fones e Dispositivos Bluetooth)
        self.bind("<space>", lambda e: self._on_play_pause_clicked())
        self.bind("<Right>", lambda e: self._on_next_clicked())
        self.bind("<Left>", lambda e: self._on_prev_clicked())
        for sym, cmd in [
            ("<XF86AudioPlay>", lambda e: self._on_play_pause_clicked()),
            ("<XF86AudioNext>", lambda e: self._on_next_clicked()),
            ("<XF86AudioPrev>", lambda e: self._on_prev_clicked()),
        ]:
            try:
                self.bind_all(sym, cmd)
            except Exception:
                pass

        # Atualiza a interface
        self._refresh_playlists_sidebar()
        self._select_playlist("downloads")

        # Inicia loop de tick de áudio
        self.after(100, self._audio_tick)

    # -------------------------------------------------------------
    # CONSTRUÇÃO VISUAL (LAYOUT)
    # -------------------------------------------------------------
    def _build_gui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # Barra inferior fixa
        self.grid_columnconfigure(0, weight=0)  # Barra lateral
        self.grid_columnconfigure(1, weight=1)  # Conteúdo principal

        # 1. Barra Lateral (Sidebar)
        self._build_sidebar()

        # 2. Área Central de Conteúdo
        self._build_main_area()

        # 3. Barra Inferior do Player (Estilo Spotify)
        self._build_player_bar()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=SPOTIFY_SIDEBAR, border_width=0)
        sidebar.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        sidebar.grid_propagate(False)

        # Logo / Marca com o ícone oficial
        logo_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=18, pady=(20, 12))

        png_icon_path = get_asset_path("icon.png")
        if os.path.exists(png_icon_path):
            try:
                pil_icon = Image.open(png_icon_path).convert("RGBA")
                ctk_icon = ctk.CTkImage(light_image=pil_icon, dark_image=pil_icon, size=(30, 30))
                logo_icon = ctk.CTkLabel(logo_frame, text="", image=ctk_icon)
                logo_icon.pack(side="left", padx=(0, 10))
            except Exception:
                logo_icon = ctk.CTkLabel(logo_frame, text="♫", font=ctk.CTkFont(size=26, weight="bold"), text_color=SPOTIFY_GREEN)
                logo_icon.pack(side="left", padx=(0, 10))
        else:
            logo_icon = ctk.CTkLabel(logo_frame, text="♫", font=ctk.CTkFont(size=26, weight="bold"), text_color=SPOTIFY_GREEN)
            logo_icon.pack(side="left", padx=(0, 10))

        logo_title = ctk.CTkLabel(
            logo_frame,
            text="SpotyLink",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT_WHITE
        )
        logo_title.pack(side="left")

        # Divisor
        div = ctk.CTkFrame(sidebar, height=1, fg_color=SPOTIFY_BORDER)
        div.pack(fill="x", padx=16, pady=6)

        # Seção Playlists
        pl_header_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        pl_header_frame.pack(fill="x", padx=18, pady=(8, 4))

        lbl_playlists = ctk.CTkLabel(
            pl_header_frame,
            text="PLAYLISTS",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_SUBTLE
        )
        lbl_playlists.pack(side="left")

        # Botão Criar Playlist
        btn_new_playlist = ctk.CTkButton(
            pl_header_frame,
            text="＋ Nova",
            width=64,
            height=26,
            corner_radius=13,
            fg_color="#282828",
            hover_color=SPOTIFY_GREEN,
            text_color=TEXT_WHITE,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._prompt_create_playlist
        )
        btn_new_playlist.pack(side="right")

        # Playlist Fixa "Downloads" (Músicas baixadas)
        self.btn_pl_downloads = ctk.CTkButton(
            sidebar,
            text="📥  Downloads (Todas)",
            anchor="w",
            height=38,
            corner_radius=8,
            fg_color=SPOTIFY_ACTIVE,
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=SPOTIFY_GREEN,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._select_playlist("downloads")
        )
        self.btn_pl_downloads.pack(fill="x", padx=14, pady=(6, 4))

        # Divisor suave
        div_pl = ctk.CTkFrame(sidebar, height=1, fg_color="#202020")
        div_pl.pack(fill="x", padx=20, pady=4)

        # Lista Rolável de Playlists Personalizadas
        self.scroll_playlists = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#252525",
            scrollbar_button_hover_color="#404040"
        )
        self.scroll_playlists.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Campo de Busca/Filtro na Playlist Aberta
        search_box_frame = ctk.CTkFrame(sidebar, fg_color=SPOTIFY_CARD, corner_radius=15, height=34)
        search_box_frame.pack(fill="x", padx=16, pady=(4, 8))
        search_box_frame.pack_propagate(False)

        search_icon = ctk.CTkLabel(search_box_frame, text="🔍", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED)
        search_icon.pack(side="left", padx=(10, 5))

        self.search_entry = ctk.CTkEntry(
            search_box_frame,
            placeholder_text="Filtrar músicas...",
            placeholder_text_color=TEXT_SUBTLE,
            text_color=TEXT_WHITE,
            fg_color="transparent",
            border_width=0,
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", self._on_filter_changed)

        # Botões de Ações Rápidas na Sidebar
        btn_mobile = ctk.CTkButton(
            sidebar,
            text="📱 SpotyLink no Celular",
            fg_color="#182A1C",
            hover_color="#203825",
            text_color=SPOTIFY_GREEN,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            corner_radius=8,
            command=self._open_mobile_sync_dialog
        )
        btn_mobile.pack(fill="x", padx=16, pady=(0, 4))

        btn_open_folder = ctk.CTkButton(
            sidebar,
            text="📁 Abrir Pasta Local",
            fg_color=SPOTIFY_CARD,
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=TEXT_WHITE,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            corner_radius=8,
            command=self._open_downloads_folder
        )
        btn_open_folder.pack(fill="x", padx=16, pady=3)

        btn_clear = ctk.CTkButton(
            sidebar,
            text="🗑 Limpar Tudo",
            fg_color="transparent",
            hover_color="#301515",
            text_color="#FF6B6B",
            font=ctk.CTkFont(size=11),
            height=28,
            corner_radius=8,
            command=self._confirm_clear_library
        )
        btn_clear.pack(fill="x", padx=16, pady=(2, 14))

    def _build_main_area(self):
        main_frame = ctk.CTkFrame(self, fg_color=SPOTIFY_BLACK, corner_radius=0)
        main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # --- BARRA SUPERIOR: ADICIONAR LINK ---
        top_bar = ctk.CTkFrame(main_frame, fg_color=SPOTIFY_CARD, corner_radius=12)
        top_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))

        input_header_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        input_header_frame.pack(fill="x", padx=16, pady=(10, 4))

        input_header = ctk.CTkLabel(
            input_header_frame,
            text="Adicionar Música via Link (YouTube, SoundCloud, Vídeos)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_WHITE
        )
        input_header.pack(side="left")

        input_sub = ctk.CTkLabel(
            input_header_frame,
            text="• Vai direto para a playlist Downloads",
            font=ctk.CTkFont(size=11),
            text_color=SPOTIFY_GREEN
        )
        input_sub.pack(side="left", padx=8)

        input_row = ctk.CTkFrame(top_bar, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(0, 10))

        # Campo de URL
        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Cole o link do vídeo aqui (ex: https://www.youtube.com/watch?v=...)",
            placeholder_text_color=TEXT_SUBTLE,
            text_color=TEXT_WHITE,
            fg_color="#101010",
            border_color=SPOTIFY_BORDER,
            border_width=1,
            corner_radius=20,
            height=38,
            font=ctk.CTkFont(size=13)
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.url_entry.bind("<Return>", lambda e: self._on_add_clicked())

        # Botão Colar
        btn_paste = ctk.CTkButton(
            input_row,
            text="📋 Colar",
            fg_color="#2A2A2A",
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=TEXT_WHITE,
            font=ctk.CTkFont(size=12, weight="bold"),
            width=75,
            height=38,
            corner_radius=20,
            command=self._paste_clipboard
        )
        btn_paste.pack(side="left", padx=(0, 8))

        # Botão Adicionar
        self.btn_add = ctk.CTkButton(
            input_row,
            text="＋ Adicionar",
            fg_color=SPOTIFY_GREEN,
            hover_color=SPOTIFY_GREEN_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=110,
            height=38,
            corner_radius=20,
            command=self._on_add_clicked
        )
        self.btn_add.pack(side="left")

        # Barra de Status do Download
        self.status_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=SPOTIFY_GREEN
        )
        self.status_label.pack(side="left", padx=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(
            self.status_frame,
            orientation="horizontal",
            mode="indeterminate",
            progress_color=SPOTIFY_GREEN,
            height=5
        )
        self.progress_bar.pack(side="left", fill="x", expand=True)

        # --- CABEÇALHO DA PLAYLIST SELECIONADA ---
        pl_banner = ctk.CTkFrame(main_frame, fg_color="transparent")
        pl_banner.grid(row=1, column=0, sticky="ew", padx=20, pady=(6, 4))
        pl_banner.grid_columnconfigure(1, weight=1)

        # Ícone Grande da Playlist
        self.pl_icon_lbl = ctk.CTkLabel(
            pl_banner,
            text="📥",
            width=54,
            height=54,
            corner_radius=8,
            fg_color=SPOTIFY_CARD,
            font=ctk.CTkFont(size=26)
        )
        self.pl_icon_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")

        # Info da Playlist
        pl_info_frame = ctk.CTkFrame(pl_banner, fg_color="transparent")
        pl_info_frame.grid(row=0, column=1, sticky="w")

        self.pl_title_lbl = ctk.CTkLabel(
            pl_info_frame,
            text="Downloads",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TEXT_WHITE,
            anchor="w"
        )
        self.pl_title_lbl.pack(anchor="w")

        self.pl_meta_lbl = ctk.CTkLabel(
            pl_info_frame,
            text="Playlist Fixa • 0 músicas • 00:00",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            anchor="w"
        )
        self.pl_meta_lbl.pack(anchor="w")

        # Botões de Ação da Playlist (Renomear / Excluir)
        self.pl_actions_frame = ctk.CTkFrame(pl_banner, fg_color="transparent")
        self.pl_actions_frame.grid(row=0, column=2, sticky="e", padx=10)

        self.btn_rename_pl = ctk.CTkButton(
            self.pl_actions_frame,
            text="✏️ Renomear",
            width=85,
            height=30,
            corner_radius=6,
            fg_color=SPOTIFY_CARD,
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=TEXT_WHITE,
            font=ctk.CTkFont(size=11),
            command=self._prompt_rename_current_playlist
        )
        self.btn_rename_pl.pack(side="left", padx=4)

        self.btn_delete_pl = ctk.CTkButton(
            self.pl_actions_frame,
            text="🗑 Excluir Playlist",
            width=110,
            height=30,
            corner_radius=6,
            fg_color="#301515",
            hover_color="#451A1A",
            text_color="#FF6B6B",
            font=ctk.CTkFont(size=11),
            command=self._confirm_delete_current_playlist
        )
        self.btn_delete_pl.pack(side="left", padx=4)

        # Cabeçalho da Tabela
        table_hdr = ctk.CTkFrame(main_frame, fg_color="transparent")
        table_hdr.grid(row=1, column=0, sticky="sew", padx=20, pady=(70, 0))
        table_hdr.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(table_hdr, text="#", width=35, text_color=TEXT_SUBTLE, font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=0, padx=4)
        ctk.CTkLabel(table_hdr, text="Capa", width=50, text_color=TEXT_SUBTLE, font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=1, padx=4)
        ctk.CTkLabel(table_hdr, text="Título & Artista", text_color=TEXT_SUBTLE, anchor="w", font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=2, sticky="w", padx=10)
        ctk.CTkLabel(table_hdr, text="⏱ Duração", width=70, text_color=TEXT_SUBTLE, font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=3, padx=10)
        ctk.CTkLabel(table_hdr, text="Ações", width=120, text_color=TEXT_SUBTLE, font=ctk.CTkFont(size=11, weight="bold")).grid(row=0, column=4, padx=10)

        div_list = ctk.CTkFrame(main_frame, height=1, fg_color=SPOTIFY_BORDER)
        div_list.grid(row=1, column=0, sticky="sew", padx=20)

        # --- LISTA ROLÁVEL DE MÚSICAS ---
        self.scroll_tracks = ctk.CTkScrollableFrame(
            main_frame,
            fg_color="transparent",
            corner_radius=0,
            scrollbar_button_color="#303030",
            scrollbar_button_hover_color="#505050"
        )
        self.scroll_tracks.grid(row=2, column=0, sticky="nsew", padx=16, pady=(4, 8))

    def _build_player_bar(self):
        player_frame = ctk.CTkFrame(self, height=92, fg_color=SPOTIFY_CARD, corner_radius=0, border_width=1, border_color=SPOTIFY_BORDER)
        player_frame.grid(row=1, column=0, columnspan=2, sticky="sew", padx=0, pady=0)
        player_frame.grid_propagate(False)

        player_frame.grid_rowconfigure(0, weight=1)
        player_frame.grid_columnconfigure(0, weight=1)  # Info da música (esquerda)
        player_frame.grid_columnconfigure(1, weight=2)  # Controles e Timeline (centro)
        player_frame.grid_columnconfigure(2, weight=1)  # Volume e Utilitários (direita)

        # ---------------- ESQUERDA: CAPA E INFO ----------------
        left_info = ctk.CTkFrame(player_frame, fg_color="transparent")
        left_info.grid(row=0, column=0, sticky="w", padx=18)

        self.current_cover_label = ctk.CTkLabel(
            left_info,
            text="",
            image=ctk.CTkImage(light_image=self.placeholder_img, dark_image=self.placeholder_img, size=(54, 54))
        )
        self.current_cover_label.pack(side="left", padx=(0, 12))

        text_container = ctk.CTkFrame(left_info, fg_color="transparent")
        text_container.pack(side="left", fill="y", pady=12)

        self.current_title_label = ctk.CTkLabel(
            text_container,
            text="Nenhuma música tocando",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_WHITE,
            anchor="w"
        )
        self.current_title_label.pack(anchor="w")

        self.current_artist_label = ctk.CTkLabel(
            text_container,
            text="Cole um link acima para adicionar",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            anchor="w"
        )
        self.current_artist_label.pack(anchor="w")

        # ---------------- CENTRO: CONTROLES E TIMELINE ----------------
        center_controls = ctk.CTkFrame(player_frame, fg_color="transparent")
        center_controls.grid(row=0, column=1, sticky="nsew", pady=8)

        btns_row = ctk.CTkFrame(center_controls, fg_color="transparent")
        btns_row.pack(anchor="center")

        # Shuffle
        self.btn_shuffle = ctk.CTkButton(
            btns_row,
            text="🔀",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=14),
            command=self._on_shuffle_clicked
        )
        self.btn_shuffle.pack(side="left", padx=8)

        # Previous
        btn_prev = ctk.CTkButton(
            btns_row,
            text="⏮",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=TEXT_WHITE,
            font=ctk.CTkFont(size=15),
            command=self._on_prev_clicked
        )
        btn_prev.pack(side="left", padx=6)

        # Play / Pause Circular Button
        self.btn_play = ctk.CTkButton(
            btns_row,
            text="▶",
            width=38,
            height=38,
            corner_radius=19,
            fg_color=SPOTIFY_GREEN,
            hover_color=SPOTIFY_GREEN_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._on_play_pause_clicked
        )
        self.btn_play.pack(side="left", padx=10)

        # Next
        btn_next = ctk.CTkButton(
            btns_row,
            text="⏭",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=TEXT_WHITE,
            font=ctk.CTkFont(size=15),
            command=self._on_next_clicked
        )
        btn_next.pack(side="left", padx=6)

        # Repeat
        self.btn_repeat = ctk.CTkButton(
            btns_row,
            text="🔁",
            width=32,
            height=32,
            fg_color="transparent",
            hover_color=SPOTIFY_CARD_HOVER,
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=14),
            command=self._on_repeat_clicked
        )
        self.btn_repeat.pack(side="left", padx=8)

        # Timeline
        timeline_row = ctk.CTkFrame(center_controls, fg_color="transparent")
        timeline_row.pack(fill="x", padx=10, pady=(2, 0))

        self.lbl_time_cur = ctk.CTkLabel(timeline_row, text="00:00", font=ctk.CTkFont(size=11), text_color=TEXT_SUBTLE, width=38)
        self.lbl_time_cur.pack(side="left")

        self.slider_progress = ctk.CTkSlider(
            timeline_row,
            from_=0,
            to=100,
            height=14,
            progress_color=SPOTIFY_GREEN,
            button_color=TEXT_WHITE,
            button_hover_color=SPOTIFY_GREEN_HOVER,
            button_length=12,
            fg_color="#404040",
            command=self._on_slider_move
        )
        self.slider_progress.set(0)
        self.slider_progress.pack(side="left", fill="x", expand=True, padx=6)
        self.slider_progress.bind("<ButtonPress-1>", self._on_slider_press)
        self.slider_progress.bind("<ButtonRelease-1>", self._on_slider_release)

        self.lbl_time_total = ctk.CTkLabel(timeline_row, text="00:00", font=ctk.CTkFont(size=11), text_color=TEXT_SUBTLE, width=38)
        self.lbl_time_total.pack(side="left")

        # ---------------- DIREITA: VOLUME E CONTEXTO ----------------
        right_controls = ctk.CTkFrame(player_frame, fg_color="transparent")
        right_controls.grid(row=0, column=2, sticky="e", padx=18)

        self.btn_mute = ctk.CTkButton(
            right_controls,
            text="🔊",
            width=26,
            height=26,
            fg_color="transparent",
            hover_color=SPOTIFY_CARD_HOVER,
            font=ctk.CTkFont(size=13),
            command=self._on_mute_clicked
        )
        self.btn_mute.pack(side="left", padx=(0, 4))

        self.slider_volume = ctk.CTkSlider(
            right_controls,
            from_=0,
            to=100,
            width=85,
            height=13,
            progress_color=TEXT_WHITE,
            button_color=TEXT_WHITE,
            button_hover_color=SPOTIFY_GREEN,
            button_length=10,
            fg_color="#404040",
            command=self._on_volume_changed
        )
        self.slider_volume.set(self.player.volume * 100)
        self.slider_volume.pack(side="left", padx=(0, 10))

        counter_container = ctk.CTkFrame(right_controls, fg_color="transparent")
        counter_container.pack(side="left")

        self.lbl_track_counter = ctk.CTkLabel(
            counter_container,
            text="- / -",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_WHITE
        )
        self.lbl_track_counter.pack(anchor="e")

        self.lbl_playing_pl_name = ctk.CTkLabel(
            counter_container,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=SPOTIFY_GREEN
        )
        self.lbl_playing_pl_name.pack(anchor="e")

    # -------------------------------------------------------------
    # GERENCIAMENTO E SELEÇÃO DE PLAYLISTS
    # -------------------------------------------------------------
    def _refresh_playlists_sidebar(self):
        """Re-renderiza a lista de playlists na barra lateral."""
        for widget in self.scroll_playlists.winfo_children():
            widget.destroy()

        # Atualiza o botão fixo de Downloads
        dl_tracks = self.library.get_playlist_tracks("downloads")
        self.btn_pl_downloads.configure(
            text=f"📥  Downloads ({len(dl_tracks)})"
        )
        if self.active_playlist_id == "downloads":
            self.btn_pl_downloads.configure(fg_color=SPOTIFY_ACTIVE, text_color=SPOTIFY_GREEN)
        else:
            self.btn_pl_downloads.configure(fg_color="transparent", text_color=TEXT_WHITE)

        # Renderiza as playlists personalizadas
        custom_playlists = [p for p in self.library.playlists if not p.get("is_system")]
        for pl in custom_playlists:
            is_active = (self.active_playlist_id == pl["id"])
            btn_bg = SPOTIFY_ACTIVE if is_active else "transparent"
            btn_text_color = SPOTIFY_GREEN if is_active else TEXT_WHITE

            pl_row = ctk.CTkFrame(self.scroll_playlists, fg_color=btn_bg, corner_radius=6, height=34)
            pl_row.pack(fill="x", pady=2)
            pl_row.pack_propagate(False)

            num_tracks = len(pl.get("track_ids", []))
            pl_name = pl.get("name", "Playlist")

            btn_pl = ctk.CTkButton(
                pl_row,
                text=f"🎵 {pl_name} ({num_tracks})",
                anchor="w",
                fg_color="transparent",
                hover_color=SPOTIFY_CARD_HOVER,
                text_color=btn_text_color,
                font=ctk.CTkFont(size=12, weight="bold" if is_active else "normal"),
                command=lambda pid=pl["id"]: self._select_playlist(pid)
            )
            btn_pl.pack(side="left", fill="both", expand=True, padx=(4, 0))

    def _select_playlist(self, playlist_id):
        """Seleciona uma playlist para exibir seu conteúdo na tela."""
        pl = self.library.get_playlist(playlist_id)
        if not pl:
            playlist_id = "downloads"
            pl = self.library.get_playlist("downloads")

        self.active_playlist_id = playlist_id
        self.search_entry.delete(0, "end")
        self.active_search_query = ""

        # Atualiza o banner no topo da lista
        pl_name = pl.get("name", "Playlist")
        tracks = self.library.get_playlist_tracks(playlist_id)
        total_sec = sum(t.get("duration", 0) for t in tracks)

        if pl.get("is_system"):
            self.pl_icon_lbl.configure(text="📥")
            self.pl_title_lbl.configure(text="Downloads")
            self.pl_meta_lbl.configure(text=f"Playlist Fixa (Todas as Baixadas) • {len(tracks)} músicas • {format_time(total_sec)}")
            self.btn_rename_pl.pack_forget()
            self.btn_delete_pl.pack_forget()
        else:
            self.pl_icon_lbl.configure(text="🎵")
            self.pl_title_lbl.configure(text=pl_name)
            self.pl_meta_lbl.configure(text=f"Playlist Personalizada • {len(tracks)} músicas • {format_time(total_sec)}")
            self.btn_rename_pl.pack(side="left", padx=4)
            self.btn_delete_pl.pack(side="left", padx=4)

        self._refresh_playlists_sidebar()
        self._refresh_track_list()

    def _prompt_create_playlist(self):
        """Abre caixa de diálogo para criar uma nova playlist personalizada."""
        dialog = ctk.CTkInputDialog(
            text="Digite o nome da nova playlist:",
            title="Criar Playlist"
        )
        name = dialog.get_input()
        if name and name.strip():
            new_pl = self.library.create_playlist(name.strip())
            if new_pl:
                self._select_playlist(new_pl["id"])

    def _prompt_rename_current_playlist(self):
        """Renomeia a playlist personalizada atualmente aberta."""
        if self.active_playlist_id == "downloads":
            return
        pl = self.library.get_playlist(self.active_playlist_id)
        if not pl:
            return

        dialog = ctk.CTkInputDialog(
            text=f"Novo nome para '{pl['name']}':",
            title="Renomear Playlist"
        )
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            self.library.rename_playlist(self.active_playlist_id, new_name.strip())
            self._select_playlist(self.active_playlist_id)

    def _confirm_delete_current_playlist(self):
        """Exclui a playlist personalizada atualmente aberta."""
        if self.active_playlist_id == "downloads":
            return
        pl = self.library.get_playlist(self.active_playlist_id)
        if not pl:
            return

        ans = messagebox.askyesno(
            "Excluir Playlist",
            f"Deseja realmente excluir a playlist '{pl['name']}'?\n\n(As músicas continuarão salvas no seu computador na playlist Downloads)."
        )
        if ans:
            self.library.delete_playlist(self.active_playlist_id)
            self._select_playlist("downloads")

    # -------------------------------------------------------------
    # MODAL PARA ADICIONAR MÚSICA A UMA PLAYLIST
    # -------------------------------------------------------------
    def _open_add_to_playlist_dialog(self, track):
        """Abre janela pop-up moderna para gerenciar em quais playlists a música está."""
        modal = ctk.CTkToplevel(self)
        modal.title("Adicionar à Playlist")
        modal.geometry("450x480")
        modal.minsize(400, 400)
        modal.configure(fg_color=SPOTIFY_BLACK)
        modal.transient(self)
        modal.grab_set()
        set_window_icon(modal)

        # Cabeçalho da Música
        hdr = ctk.CTkFrame(modal, fg_color=SPOTIFY_CARD, corner_radius=10)
        hdr.pack(fill="x", padx=16, pady=16)

        thumb_img = self._get_cover_image(track.get("cover_path"), size=(48, 48))
        lbl_thumb = ctk.CTkLabel(hdr, text="", image=thumb_img)
        lbl_thumb.pack(side="left", padx=10, pady=10)

        info_box = ctk.CTkFrame(hdr, fg_color="transparent")
        info_box.pack(side="left", fill="both", expand=True, pady=10)

        ctk.CTkLabel(
            info_box,
            text=track.get("title", "Sem título")[:38],
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_WHITE,
            anchor="w"
        ).pack(anchor="w")

        ctk.CTkLabel(
            info_box,
            text=track.get("artist", "Artista")[:38],
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            anchor="w"
        ).pack(anchor="w")

        # Seção de Playlists
        ctk.CTkLabel(
            modal,
            text="Selecione as playlists:",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_WHITE
        ).pack(anchor="w", padx=18, pady=(4, 6))

        scroll_pl_modal = ctk.CTkScrollableFrame(modal, fg_color=SPOTIFY_CARD, corner_radius=8)
        scroll_pl_modal.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        def refresh_modal_list():
            for w in scroll_pl_modal.winfo_children():
                w.destroy()

            custom_pls = [p for p in self.library.playlists if not p.get("is_system")]
            if not custom_pls:
                ctk.CTkLabel(
                    scroll_pl_modal,
                    text="Nenhuma playlist personalizada criada ainda.\nCrie uma abaixo!",
                    font=ctk.CTkFont(size=12),
                    text_color=TEXT_MUTED
                ).pack(pady=30)
                return

            for pl in custom_pls:
                row = ctk.CTkFrame(scroll_pl_modal, fg_color="#202020", corner_radius=6, height=40)
                row.pack(fill="x", pady=3, padx=4)
                row.pack_propagate(False)

                is_in_pl = track["id"] in pl.get("track_ids", [])

                ctk.CTkLabel(
                    row,
                    text=f"🎵 {pl['name']}",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=TEXT_WHITE
                ).pack(side="left", padx=10)

                def toggle_in_playlist(pid=pl["id"], currently_in=is_in_pl):
                    if currently_in:
                        self.library.remove_track_from_playlist(pid, track["id"])
                    else:
                        self.library.add_track_to_playlist(pid, track["id"])
                    refresh_modal_list()
                    self._refresh_playlists_sidebar()
                    if self.active_playlist_id == pid:
                        self._refresh_track_list()

                btn_toggle = ctk.CTkButton(
                    row,
                    text="✓ Adicionada (Remover)" if is_in_pl else "＋ Adicionar",
                    width=135,
                    height=28,
                    corner_radius=14,
                    fg_color=SPOTIFY_GREEN if is_in_pl else "#303030",
                    hover_color="#E91429" if is_in_pl else SPOTIFY_GREEN,
                    text_color="#000000" if is_in_pl else TEXT_WHITE,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    command=toggle_in_playlist
                )
                btn_toggle.pack(side="right", padx=8)

        refresh_modal_list()

        # Criação Rápida no Modal
        quick_create_box = ctk.CTkFrame(modal, fg_color="transparent")
        quick_create_box.pack(fill="x", padx=16, pady=(0, 10))

        entry_new_pl = ctk.CTkEntry(
            quick_create_box,
            placeholder_text="Nome de uma nova playlist...",
            height=32,
            font=ctk.CTkFont(size=12)
        )
        entry_new_pl.pack(side="left", fill="x", expand=True, padx=(0, 6))

        def create_and_add():
            name = entry_new_pl.get().strip()
            if name:
                new_pl = self.library.create_playlist(name)
                if new_pl:
                    self.library.add_track_to_playlist(new_pl["id"], track["id"])
                    entry_new_pl.delete(0, "end")
                    refresh_modal_list()
                    self._refresh_playlists_sidebar()

        btn_create_add = ctk.CTkButton(
            quick_create_box,
            text="Criar e Adicionar",
            width=120,
            height=32,
            fg_color=SPOTIFY_GREEN,
            hover_color=SPOTIFY_GREEN_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=create_and_add
        )
        btn_create_add.pack(side="left")

        # Botão Fechar
        btn_close = ctk.CTkButton(
            modal,
            text="Concluir",
            fg_color="#2A2A2A",
            hover_color=SPOTIFY_CARD_HOVER,
            height=32,
            command=modal.destroy
        )
        btn_close.pack(fill="x", padx=16, pady=(0, 14))

    # -------------------------------------------------------------
    # CONECTAR AO APLICATIVO ANDROID / SMARTPHONE
    # -------------------------------------------------------------
    def _open_mobile_sync_dialog(self):
        """Abre o guia interativo de conexão e instalação para smartphone Android."""
        # Garante que BASE_DIR está no sys.path para imports locais
        if BASE_DIR not in sys.path:
            sys.path.insert(0, BASE_DIR)

        # Inicia o servidor móvel em segundo plano se ainda não foi iniciado
        if not getattr(self, "_mobile_server_started", False):
            try:
                import mobile_server
                th = threading.Thread(target=mobile_server.run_mobile_server, daemon=True)
                th.start()
                self._mobile_server_started = True
            except Exception as e:
                print(f"[Aviso] Servidor mobile: {e}")

        modal = ctk.CTkToplevel(self)
        modal.title("SpotyLink no Celular (Android)")
        modal.geometry("520x680")
        modal.minsize(460, 580)
        modal.configure(fg_color=SPOTIFY_BLACK)
        modal.transient(self)
        modal.grab_set()
        set_window_icon(modal)

        scroll = ctk.CTkScrollableFrame(modal, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=16)

        # Cabeçalho
        ctk.CTkLabel(
            scroll,
            text="📱 SpotyLink no seu Smartphone Android",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_WHITE
        ).pack(pady=(4, 4))

        ctk.CTkLabel(
            scroll,
            text="Escolha a forma que preferir para usar no celular:",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED
        ).pack(pady=(0, 16))

        # =========================================================
        # SEÇÃO 1: INSTALAR DIRETO NO CELULAR (TERMUX - 100% OFFLINE)
        # =========================================================
        box_termux = ctk.CTkFrame(scroll, fg_color=SPOTIFY_CARD, corner_radius=10, border_width=1, border_color="#203825")
        box_termux.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            box_termux,
            text="🌟 Opção 1: Direto no Celular (Recomendado - 100% Offline)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=SPOTIFY_GREEN
        ).pack(anchor="w", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            box_termux,
            text=(
                "Roda de forma independente dentro do celular via Termux (grátis e seguro),\n"
                "sem precisar do PC ligado. Salva as músicas no celular e instala o ícone no Chrome!"
            ),
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            justify="left"
        ).pack(anchor="w", padx=14, pady=(0, 10))

        termux_cmd = "termux-setup-storage && pkg install unzip -y && unzip -o /sdcard/Download/SpotyLink_Android.zip -d ~/musica && cd ~/musica && bash android/instalar_spotylink_android.sh"

        cmd_frame = ctk.CTkFrame(box_termux, fg_color="#101010", corner_radius=6)
        cmd_frame.pack(fill="x", padx=14, pady=(0, 10))

        lbl_cmd = ctk.CTkLabel(
            cmd_frame,
            text=termux_cmd[:55] + "...",
            font=ctk.CTkFont(size=10, family="Consolas"),
            text_color=TEXT_MUTED
        )
        lbl_cmd.pack(side="left", padx=10, pady=8)

        def copy_termux():
            self.clipboard_clear()
            self.clipboard_append(termux_cmd)
            btn_copy_cmd.configure(text="✓ Copiado!")
            self.after(2000, lambda: btn_copy_cmd.configure(text="Copiar Comando"))

        btn_copy_cmd = ctk.CTkButton(
            cmd_frame,
            text="Copiar Comando",
            width=110,
            height=26,
            fg_color="#2A2A2A",
            hover_color=SPOTIFY_CARD_HOVER,
            font=ctk.CTkFont(size=11),
            command=copy_termux
        )
        btn_copy_cmd.pack(side="right", padx=8)

        def open_folder_zip():
            try:
                os.startfile(BASE_DIR)
            except Exception:
                pass

        btn_open_zip = ctk.CTkButton(
            box_termux,
            text="📁 Abrir Pasta com o arquivo 'SpotyLink_Android.zip'",
            fg_color="#2A2A2A",
            hover_color=SPOTIFY_CARD_HOVER,
            height=28,
            font=ctk.CTkFont(size=11),
            command=open_folder_zip
        )
        btn_open_zip.pack(fill="x", padx=14, pady=(0, 12))

        # =========================================================
        # SEÇÃO 2: CONECTAR VIA WI-FI AO PC
        # =========================================================
        box_wifi = ctk.CTkFrame(scroll, fg_color=SPOTIFY_CARD, corner_radius=10)
        box_wifi.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            box_wifi,
            text="🌐 Opção 2: Conectar ao PC via Wi-Fi (QR Code)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_WHITE
        ).pack(anchor="w", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            box_wifi,
            text="Acesse as músicas salvas no PC direto pelo navegador do celular no mesmo Wi-Fi:",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED
        ).pack(anchor="w", padx=14, pady=(0, 10))

        ip = get_local_ip()
        mobile_url = f"http://{ip}:5000"

        # Gera QR Code se biblioteca qrcode estiver instalada
        qr_frame = ctk.CTkFrame(box_wifi, fg_color="#FFFFFF", corner_radius=8, width=180, height=180)
        qr_frame.pack(pady=4)
        qr_frame.pack_propagate(False)

        if qrcode:
            try:
                qr = qrcode.QRCode(box_size=5, border=2)
                qr.add_data(mobile_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
                ctk_qr = ctk.CTkImage(light_image=qr_img, dark_image=qr_img, size=(160, 160))
                lbl_qr = ctk.CTkLabel(qr_frame, text="", image=ctk_qr)
                lbl_qr.pack(expand=True)
            except Exception:
                ctk.CTkLabel(qr_frame, text=mobile_url, text_color="#000000").pack(expand=True)
        else:
            ctk.CTkLabel(qr_frame, text=mobile_url, text_color="#000000").pack(expand=True)

        url_box = ctk.CTkFrame(box_wifi, fg_color="#101010", corner_radius=6)
        url_box.pack(fill="x", padx=14, pady=10)

        lbl_url = ctk.CTkLabel(url_box, text=mobile_url, font=ctk.CTkFont(size=12, weight="bold"), text_color=SPOTIFY_GREEN)
        lbl_url.pack(side="left", padx=10, pady=6)

        def copy_wifi_url():
            self.clipboard_clear()
            self.clipboard_append(mobile_url)
            btn_copy_wifi.configure(text="✓ Copiado!")
            self.after(2000, lambda: btn_copy_wifi.configure(text="Copiar"))

        btn_copy_wifi = ctk.CTkButton(url_box, text="Copiar", width=70, height=26, fg_color="#2A2A2A", command=copy_wifi_url)
        btn_copy_wifi.pack(side="right", padx=8)

        # Botão Fechar
        btn_close = ctk.CTkButton(
            modal,
            text="Fechar",
            fg_color="#2A2A2A",
            hover_color=SPOTIFY_CARD_HOVER,
            height=32,
            command=modal.destroy
        )
        btn_close.pack(fill="x", padx=16, pady=(0, 14))

    # -------------------------------------------------------------
    # ADICIONAR MÚSICA POR LINK (DOWNLOAD EM BACKGROUND)
    # -------------------------------------------------------------
    def _paste_clipboard(self):
        try:
            text = self.clipboard_get().strip()
            if text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, text)
        except Exception:
            pass

    def _on_add_clicked(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showinfo("SpotyLink", "Por favor, cole o link da música ou vídeo.")
            return

        self.btn_add.configure(state="disabled", text="Baixando...")
        self.status_frame.pack(fill="x", padx=16, pady=(0, 8))
        self.progress_bar.start()
        self.status_label.configure(text="Conectando e obtendo dados...")

        thread = threading.Thread(target=self._download_worker, args=(url,), daemon=True)
        thread.start()

    def _download_worker(self, url):
        url = clean_url(url)
        ffmpeg_exe = get_ffmpeg_binary()

        ydl_opts = {
            'format': 'bestaudio/best',
            'ffmpeg_location': ffmpeg_exe,
            'outtmpl': os.path.join(DOWNLOADS_DIR, '%(id)s.%(ext)s'),
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._update_status_safe("Obtendo informações...")
                info = ydl.extract_info(url, download=False)

                track_id = info.get("id") or str(int(time.time()))
                title = info.get("title") or "Música Sem Título"
                uploader = info.get("uploader") or info.get("channel") or info.get("artist") or "Artista Desconhecido"
                duration = info.get("duration") or 0
                thumb_url = info.get("thumbnail")

                self._update_status_safe(f"Baixando: {title[:40]}...")

                ydl.download([url])

                mp3_path = os.path.join(DOWNLOADS_DIR, f"{track_id}.mp3")
                cover_path = os.path.join(COVERS_DIR, f"{track_id}.jpg")

                if thumb_url:
                    try:
                        req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=8) as resp, open(cover_path, "wb") as f_out:
                            f_out.write(resp.read())
                    except Exception as e:
                        print(f"[Aviso] Falha ao baixar capa: {e}")

                track_data = {
                    "id": track_id,
                    "title": title,
                    "artist": uploader,
                    "duration": duration,
                    "duration_str": format_time(duration),
                    "file_path": mp3_path,
                    "cover_path": cover_path if os.path.exists(cover_path) else "",
                    "url": url,
                    "added_at": time.time()
                }

                self.after(0, self._on_download_success, track_data)

        except Exception as e:
            err_msg = str(e)
            print(f"[Erro no Download]: {err_msg}")
            self.after(0, self._on_download_error, err_msg)

    def _update_status_safe(self, msg):
        self.after(0, lambda: self.status_label.configure(text=msg))

    def _on_download_success(self, track_data):
        self.progress_bar.stop()
        self.status_frame.pack_forget()
        self.btn_add.configure(state="normal", text="＋ Adicionar")
        self.url_entry.delete(0, "end")

        # Adiciona na biblioteca e automaticamente na playlist fixa 'Downloads'
        self.library.add_downloaded_track(track_data)

        # Atualiza a interface (a música fica disponível na lista sem iniciar automaticamente)
        self._refresh_playlists_sidebar()
        self._select_playlist(self.active_playlist_id)

    def _on_download_error(self, err_msg):
        self.progress_bar.stop()
        self.status_frame.pack_forget()
        self.btn_add.configure(state="normal", text="＋ Adicionar")
        messagebox.showerror(
            "Erro ao Adicionar Música",
            f"Não foi possível processar o link fornecido.\n\nDetalhes:\n{err_msg[:250]}"
        )

    # -------------------------------------------------------------
    # RENDERIZAÇÃO DA LISTA DE MÚSICAS DA PLAYLIST
    # -------------------------------------------------------------
    def _on_filter_changed(self, event=None):
        self.active_search_query = self.search_entry.get().strip().lower()
        self._refresh_track_list()

    def _get_displayed_tracks(self):
        tracks = self.library.get_playlist_tracks(self.active_playlist_id)
        if not self.active_search_query:
            return list(enumerate(tracks))
        result = []
        for i, t in enumerate(tracks):
            if (self.active_search_query in t["title"].lower() or 
                self.active_search_query in t["artist"].lower()):
                result.append((i, t))
        return result

    def _get_cover_image(self, cover_path, size=(44, 44)):
        cache_key = (cover_path, size)
        if cache_key in self.cover_cache:
            return self.cover_cache[cache_key]

        img = None
        if cover_path and os.path.exists(cover_path):
            try:
                pil_img = Image.open(cover_path).convert("RGB")
                pil_img = pil_img.resize(size, Image.Resampling.LANCZOS)
                img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
            except Exception:
                img = None

        if img is None:
            placeholder = create_placeholder_cover(size)
            img = ctk.CTkImage(light_image=placeholder, dark_image=placeholder, size=size)

        self.cover_cache[cache_key] = img
        return img

    def _refresh_track_list(self):
        for widget in self.scroll_tracks.winfo_children():
            widget.destroy()

        displayed = self._get_displayed_tracks()

        if not displayed:
            empty_frame = ctk.CTkFrame(self.scroll_tracks, fg_color="transparent")
            empty_frame.pack(fill="both", expand=True, pady=50)

            empty_icon = ctk.CTkLabel(empty_frame, text="🎵", font=ctk.CTkFont(size=44))
            empty_icon.pack(pady=(0, 8))

            if self.active_search_query:
                empty_text = f"Nenhuma música encontrada para '{self.active_search_query}' nesta playlist."
            elif self.active_playlist_id == "downloads":
                empty_text = "Nenhuma música baixada ainda!\nCole um link do YouTube ou vídeo acima para começar."
            else:
                empty_text = "Esta playlist está vazia!\nVá até a playlist 'Downloads' e clique em ➕ para adicionar músicas aqui."

            empty_lbl = ctk.CTkLabel(
                empty_frame,
                text=empty_text,
                font=ctk.CTkFont(size=13),
                text_color=TEXT_MUTED,
                justify="center"
            )
            empty_lbl.pack()
            return

        # Renderiza cada música
        for row_pos, (real_idx, track) in enumerate(displayed):
            is_active = (
                self.player.current_track and 
                self.player.current_track.get("id") == track["id"] and 
                self.player.is_playing
            )
            row_bg = SPOTIFY_ACTIVE if is_active else SPOTIFY_CARD

            row = ctk.CTkFrame(
                self.scroll_tracks,
                fg_color=row_bg,
                corner_radius=8,
                height=54
            )
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            row.grid_columnconfigure(2, weight=1)

            # 1. Número da Faixa
            num_text = "🔊" if is_active else str(real_idx + 1)
            num_color = SPOTIFY_GREEN if is_active else TEXT_SUBTLE
            lbl_num = ctk.CTkLabel(
                row,
                text=num_text,
                width=35,
                text_color=num_color,
                font=ctk.CTkFont(size=12, weight="bold")
            )
            lbl_num.grid(row=0, column=0, padx=4, pady=6)

            # 2. Imagem da Capa
            thumb_img = self._get_cover_image(track.get("cover_path"), size=(40, 40))
            lbl_thumb = ctk.CTkLabel(row, text="", image=thumb_img)
            lbl_thumb.grid(row=0, column=1, padx=4, pady=6)

            # 3. Título e Artista
            info_frame = ctk.CTkFrame(row, fg_color="transparent")
            info_frame.grid(row=0, column=2, sticky="w", padx=10, pady=4)

            title_color = SPOTIFY_GREEN if is_active else TEXT_WHITE
            lbl_title = ctk.CTkLabel(
                info_frame,
                text=track.get("title", "Sem Título"),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=title_color,
                anchor="w"
            )
            lbl_title.pack(anchor="w")

            lbl_artist = ctk.CTkLabel(
                info_frame,
                text=track.get("artist", "Artista Desconhecido"),
                font=ctk.CTkFont(size=11),
                text_color=TEXT_MUTED,
                anchor="w"
            )
            lbl_artist.pack(anchor="w")

            # 4. Duração
            lbl_dur = ctk.CTkLabel(
                row,
                text=track.get("duration_str", "00:00"),
                width=70,
                font=ctk.CTkFont(size=12),
                text_color=TEXT_MUTED
            )
            lbl_dur.grid(row=0, column=3, padx=10)

            # 5. Ações (Tocar, Adicionar a Playlist, Excluir)
            act_frame = ctk.CTkFrame(row, fg_color="transparent", width=120)
            act_frame.grid(row=0, column=4, padx=8)

            btn_play_row = ctk.CTkButton(
                act_frame,
                text="⏸" if (is_active and not self.player.is_paused) else "▶",
                width=30,
                height=30,
                corner_radius=15,
                fg_color=SPOTIFY_GREEN if is_active else "#2B2B2B",
                hover_color=SPOTIFY_GREEN_HOVER if is_active else "#3D3D3D",
                text_color="#000000" if is_active else TEXT_WHITE,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda idx=real_idx: self._play_track_from_active_view(idx)
            )
            btn_play_row.pack(side="left", padx=3)

            btn_add_pl = ctk.CTkButton(
                act_frame,
                text="➕",
                width=30,
                height=30,
                corner_radius=15,
                fg_color="#282828",
                hover_color=SPOTIFY_CARD_HOVER,
                text_color=SPOTIFY_GREEN,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda trk=track: self._open_add_to_playlist_dialog(trk)
            )
            btn_add_pl.pack(side="left", padx=3)

            btn_del = ctk.CTkButton(
                act_frame,
                text="✕",
                width=28,
                height=28,
                corner_radius=14,
                fg_color="transparent",
                hover_color="#451A1A",
                text_color=TEXT_SUBTLE,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda trk=track: self._handle_delete_track_action(trk)
            )
            btn_del.pack(side="left", padx=2)

            # Duplo clique toca a música
            row.bind("<Double-Button-1>", lambda e, idx=real_idx: self._play_track_from_active_view(idx))

    # -------------------------------------------------------------
    # CONTROLE DE REPRODUÇÃO (PLAYBACK)
    # -------------------------------------------------------------
    def _play_track_from_active_view(self, index):
        """Inicia a reprodução definindo a playlist atual da tela como a playlist ativa no player."""
        self.playback_playlist_id = self.active_playlist_id
        self.playback_tracks = self.library.get_playlist_tracks(self.playback_playlist_id)
        self._play_playback_track(index)

    def _play_playback_track(self, index, start_pos=0.0):
        if not self.playback_tracks or index < 0 or index >= len(self.playback_tracks):
            return

        track = self.playback_tracks[index]
        success = self.player.load_and_play(track, index, start_pos)
        if success:
            self.current_title_label.configure(text=track.get("title", "Música"))
            self.current_artist_label.configure(text=track.get("artist", "Artista"))
            self.lbl_time_total.configure(text=track.get("duration_str", "00:00"))
            self.slider_progress.configure(to=max(1, track.get("duration", 100)))
            self.slider_progress.set(start_pos)
            self.btn_play.configure(text="⏸")

            large_cover = self._get_cover_image(track.get("cover_path"), size=(54, 54))
            self.current_cover_label.configure(image=large_cover)

            # Atualiza indicador de qual playlist está tocando
            pl = self.library.get_playlist(self.playback_playlist_id)
            pl_name = pl.get("name", "Downloads") if pl else "Downloads"
            self.lbl_track_counter.configure(text=f"{index + 1} de {len(self.playback_tracks)}")
            self.lbl_playing_pl_name.configure(text=f"Tocando: {pl_name}")

            self._refresh_track_list()

    def _on_play_pause_clicked(self):
        if not self.playback_tracks:
            # Se não houver faixas carregadas, carrega da tela atual
            self.playback_playlist_id = self.active_playlist_id
            self.playback_tracks = self.library.get_playlist_tracks(self.playback_playlist_id)

        if not self.playback_tracks:
            return

        if self.player.current_index == -1:
            self._play_playback_track(0)
            return

        self.player.toggle_play_pause()
        if self.player.is_playing and not self.player.is_paused:
            self.btn_play.configure(text="⏸")
        else:
            self.btn_play.configure(text="▶")
        self._refresh_track_list()

    def _on_next_clicked(self):
        if not self.playback_tracks:
            return
        total = len(self.playback_tracks)

        if self.player.shuffle:
            next_idx = random.randint(0, total - 1)
        else:
            next_idx = (self.player.current_index + 1) % total

        self._play_playback_track(next_idx)

    def _on_prev_clicked(self):
        if not self.playback_tracks:
            return
        total = len(self.playback_tracks)

        if self.player.current_pos > 3.0:
            self.player.seek(0)
            return

        if self.player.shuffle:
            prev_idx = random.randint(0, total - 1)
        else:
            prev_idx = (self.player.current_index - 1 + total) % total

        self._play_playback_track(prev_idx)

    def _on_shuffle_clicked(self):
        self.player.shuffle = not self.player.shuffle
        if self.player.shuffle:
            self.btn_shuffle.configure(text_color=SPOTIFY_GREEN)
        else:
            self.btn_shuffle.configure(text_color=TEXT_MUTED)

    def _on_repeat_clicked(self):
        modes = ["off", "all", "one"]
        cur_idx = modes.index(self.player.repeat_mode)
        next_mode = modes[(cur_idx + 1) % len(modes)]
        self.player.repeat_mode = next_mode

        if next_mode == "off":
            self.btn_repeat.configure(text="🔁", text_color=TEXT_MUTED)
        elif next_mode == "all":
            self.btn_repeat.configure(text="🔁", text_color=SPOTIFY_GREEN)
        elif next_mode == "one":
            self.btn_repeat.configure(text="🔂", text_color=SPOTIFY_GREEN)

    def _handle_delete_track_action(self, track):
        """Trata o clique no botão '✕' dependendo da playlist atual."""
        track_id = track["id"]

        if self.active_playlist_id == "downloads":
            # Está na playlist Downloads -> Exclusão definitiva do disco
            ans = messagebox.askyesno(
                "Excluir Música",
                f"Deseja excluir permanentemente '{track.get('title')}' do seu computador e de todas as playlists?"
            )
            if ans:
                is_current = (self.player.current_track and self.player.current_track.get("id") == track_id)
                if is_current:
                    self._reset_player_ui()

                self.library.remove_track_from_library(track_id)
                self.playback_tracks = self.library.get_playlist_tracks(self.playback_playlist_id)
                self._select_playlist(self.active_playlist_id)
        else:
            # Está em uma playlist personalizada -> Apenas remove desta playlist
            pl = self.library.get_playlist(self.active_playlist_id)
            pl_name = pl.get("name", "esta playlist") if pl else "esta playlist"
            self.library.remove_track_from_playlist(self.active_playlist_id, track_id)
            if self.playback_playlist_id == self.active_playlist_id:
                self.playback_tracks = self.library.get_playlist_tracks(self.playback_playlist_id)
            self._select_playlist(self.active_playlist_id)

    def _reset_player_ui(self):
        self.player.stop()
        self.btn_play.configure(text="▶")
        self.current_title_label.configure(text="Nenhuma música tocando")
        self.current_artist_label.configure(text="")
        self.lbl_time_cur.configure(text="00:00")
        self.lbl_time_total.configure(text="00:00")
        self.slider_progress.set(0)
        self.lbl_track_counter.configure(text="- / -")
        self.lbl_playing_pl_name.configure(text="")
        self.current_cover_label.configure(
            image=ctk.CTkImage(light_image=self.placeholder_img, dark_image=self.placeholder_img, size=(54, 54))
        )
        self.player.current_index = -1

    def _confirm_clear_library(self):
        ans = messagebox.askyesno(
            "Limpar Tudo",
            "Deseja realmente limpar toda a biblioteca, excluir todas as músicas baixadas e apagar as playlists criadas?"
        )
        if ans:
            self._reset_player_ui()
            self.library.clear_all()
            self._select_playlist("downloads")

    def _open_downloads_folder(self):
        try:
            os.startfile(DOWNLOADS_DIR)
        except Exception as e:
            messagebox.showinfo("SpotyLink", f"Caminho das músicas:\n{DOWNLOADS_DIR}")

    # -------------------------------------------------------------
    # SEEK / VOLUME / TIMELINE
    # -------------------------------------------------------------
    def _on_slider_press(self, event):
        self.is_dragging_slider = True

    def _on_slider_move(self, value):
        self.lbl_time_cur.configure(text=format_time(value))

    def _on_slider_release(self, event):
        target = self.slider_progress.get()
        self.player.seek(target)
        self.is_dragging_slider = False

    def _on_volume_changed(self, value):
        vol = float(value) / 100.0
        self.player.set_volume(vol)
        if vol == 0:
            self.btn_mute.configure(text="🔇")
        elif vol < 0.5:
            self.btn_mute.configure(text="🔉")
        else:
            self.btn_mute.configure(text="🔊")

    def _on_mute_clicked(self):
        if self.player.volume > 0:
            self._prev_vol = self.player.volume
            self.slider_volume.set(0)
            self._on_volume_changed(0)
        else:
            prev = getattr(self, "_prev_vol", 0.8)
            self.slider_volume.set(prev * 100)
            self._on_volume_changed(prev * 100)

    # -------------------------------------------------------------
    # LOOP DE TICK DO ÁUDIO
    # -------------------------------------------------------------
    def _audio_tick(self):
        if self.player.is_playing and not self.player.is_paused:
            now = time.time()
            dt = now - self.player.last_tick
            self.player.last_tick = now
            self.player.current_pos += dt

            music_ended = (not pygame.mixer.music.get_busy()) or (
                self.player.duration > 0 and self.player.current_pos >= self.player.duration
            )

            if music_ended:
                self._handle_track_finished()
            else:
                if not self.is_dragging_slider:
                    self.slider_progress.set(self.player.current_pos)
                    self.lbl_time_cur.configure(text=format_time(self.player.current_pos))

        self.after(100, self._audio_tick)

    def _handle_track_finished(self):
        if self.player.repeat_mode == "one":
            self.player.seek(0)
        elif self.player.repeat_mode == "all":
            self._on_next_clicked()
        else:  # "off"
            total = len(self.playback_tracks)
            if self.player.current_index + 1 < total:
                self._on_next_clicked()
            else:
                self._reset_player_ui()
                self._refresh_track_list()


# ==========================================
# ENTRADA PRINCIPAL DO PROGRAMA
# ==========================================
if __name__ == "__main__":
    app = SpotyLinkApp()
    app.mainloop()
