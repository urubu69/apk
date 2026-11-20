"""
SpotyLink Android Client (Kivy)
Permite executar o SpotyLink nativamente no Android.
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.core.audio import SoundLoader
import json
import os

class SpotyLinkMobile(App):
    def build(self):
        self.title = "SpotyLink"
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Header
        header = Label(
            text="♫ SpotyLink Mobile",
            font_size='22sp',
            bold=True,
            color=(0.11, 0.73, 0.33, 1),
            size_hint_y=None,
            height=50
        )
        layout.add_widget(header)

        # URL Input
        input_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50, spacing=6)
        self.url_input = TextInput(hint_text="Cole o link do vídeo aqui...", multiline=False)
        btn_add = Button(text="＋ Baixar", size_hint_x=0.35, background_color=(0.11, 0.73, 0.33, 1))
        btn_add.bind(on_press=self.start_download)
        input_box.add_widget(self.url_input)
        input_box.add_widget(btn_add)
        layout.add_widget(input_box)

        # Status
        self.lbl_status = Label(text="Pronto para reproduzir", size_hint_y=None, height=30, color=(0.7, 0.7, 0.7, 1))
        layout.add_widget(self.lbl_status)

        # Lista de Músicas
        scroll = ScrollView(size_hint=(1, 1))
        self.track_grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        self.track_grid.bind(minimum_height=self.track_grid.setter('height'))
        scroll.add_widget(self.track_grid)
        layout.add_widget(scroll)

        self.sound = None
        self.refresh_tracks()
        return layout

    def start_download(self, instance):
        url = self.url_input.text.strip()
        if not url:
            return
        self.lbl_status.text = "Baixando áudio..."
        # Download logic com yt-dlp
        import threading
        threading.Thread(target=self._dl_worker, args=(url,), daemon=True).start()

    def _dl_worker(self, url):
        import yt_dlp
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'quiet': True
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.lbl_status.text = "Download concluído!"
            self.refresh_tracks()
        except Exception as e:
            self.lbl_status.text = f"Erro: {str(e)[:30]}"

    def refresh_tracks(self):
        self.track_grid.clear_widgets()
        os.makedirs("downloads", exist_ok=True)
        files = [f for f in os.listdir("downloads") if f.endswith(".mp3")]
        if not files:
            self.track_grid.add_widget(Label(text="Nenhuma música baixada ainda.", size_hint_y=None, height=40))
            return

        for f in files:
            btn = Button(
                text=f"▶ {f}",
                size_hint_y=None,
                height=45,
                background_color=(0.15, 0.15, 0.15, 1)
            )
            btn.bind(on_press=lambda inst, fn=f: self.play_file(fn))
            self.track_grid.add_widget(btn)

    def play_file(self, filename):
        if self.sound:
            self.sound.stop()
        path = os.path.join("downloads", filename)
        self.sound = SoundLoader.load(path)
        if self.sound:
            self.sound.play()
            self.lbl_status.text = f"Tocando: {filename}"

if __name__ == '__main__':
    SpotyLinkMobile().run()
