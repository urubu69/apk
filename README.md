# 🎵 SpotyLink - Reprodutor de Música por Link & Playlists (Estilo Spotify)

Um reprodutor de áudio completo e offline desenvolvido em **Python** inspirado na interface moderna do **Spotify**, com suporte a desktop (Windows) e smartphones **Android**. Permite adicionar músicas diretamente colando o link do vídeo ou da música da internet (YouTube, SoundCloud, vídeos da web, etc.) e conta com gerenciamento completo de playlists.

Criado exclusivamente para estudos pessoais e testes sem fins lucrativos.

---

## ✨ Funcionalidades Principais

1. **100% Offline após o Download**:
   - As músicas baixadas ficam salvas localmente no formato `.mp3` na pasta `downloads/`.
   - Você pode ouvir todas as suas músicas mesmo sem conexão com a internet.

2. **Playlist Fixa "Downloads" (Automática)**:
   - Ao colar um link e clicar em **"＋ Adicionar"**, a música é baixada automaticamente e inserida diretamente na playlist fixa **Downloads**.
   - Ela reúne todas as faixas salvas no seu computador.
   - **Sem reprodução forçada**: o download salva a música na biblioteca silenciosamente para você dar play apenas quando desejar.

3. **Criação de Playlists Personalizadas**:
   - Crie quantas playlists quiser com o nome que desejar (ex: *Treino*, *Favoritas*, *Rock*, *Estudo*).
   - Botão **"＋ Nova"** na barra lateral.
   - Opção para **Renomear** e **Excluir** playlists criadas.

4. **Organização de Músicas**:
   - Cada música possui um botão **`➕`** para abrir o gerenciador rápido de playlists: basta um clique para adicionar ou remover a música de qualquer playlist.
   - **Remoção inteligente**: 
     - Se você excluir uma música de uma playlist personalizada, ela sai apenas daquela playlist (o arquivo `.mp3` continua intacto no seu computador e na playlist Downloads).
     - Se você excluir da playlist Downloads, você pode optar por remover o arquivo do computador.

5. **Reprodução por Contexto de Playlist**:
   - O player toca dentro da playlist selecionada: os botões Próxima (⏭), Anterior (⏮), Aleatório (🔀) e Repetir (🔁) respeitam a lista da playlist ativa.
   - Indicador no canto inferior direito mostra qual playlist está tocando atualmente.

6. **Ícone Oficial Personalizado**:
   - O ícone da nota musical verde pixelada está integrado no executável Windows (`.exe`), na barra de títulos da janela, na barra de tarefas do Windows e no logo da barra lateral.

7. **📱 Adaptação para Smartphones Android**:
   - **Instalação Direta no Celular (Termux - 100% Offline)**: Roda nativamente no celular sem precisar do computador ligado. Salva as músicas na memória do celular e instala como app nativo no Google Chrome com o ícone verde na tela inicial.
   - **Pacote Pronto**: Arquivo `SpotyLink_Android.zip` pronto para transferir para o celular.
   - **Compilação de APK**: Arquivos `android/buildozer.spec` e fluxo `.github/workflows/build_apk.yml` para compilar o `.apk` na nuvem.
   - **Conexão Wi-Fi ao PC**: Permite parear via QR Code ou navegador local.

---

## 🚀 Como Executar no Computador (Windows)

### Opção 1: Pelo Atalho com Ícone ou Executável
- Dê dois cliques no atalho com ícone: [SpotyLink.lnk](file:///c:/Users/carlo/Desktop/Codigos/musica/SpotyLink.lnk)
- Ou direto em `dist\SpotyLink\`[SpotyLink.exe](file:///c:/Users/carlo/Desktop/Codigos/musica/dist/SpotyLink/SpotyLink.exe)
- Ou pelo inicializador [Abrir_SpotyLink.bat](file:///c:/Users/carlo/Desktop/Codigos/musica/Abrir_SpotyLink.bat)

### Opção 2: Pelo Python
```bash
cd c:\Users\carlo\Desktop\Codigos\musica
python musica.py
```

---

## 📱 Como Instalar e Usar no Smartphone Android

Consulte o passo a passo completo e ilustrado em:
👉 [android/README_ANDROID.md](file:///c:/Users/carlo/Desktop/Codigos/musica/android/README_ANDROID.md)

### Resumo rápido (Instalação em 1 Comando no Celular):
1. Baixe o **Termux** no celular pelo [F-Droid](https://f-droid.org/packages/com.termux/) (100% seguro e open source).
2. Copie o arquivo **`SpotyLink_Android.zip`** para a pasta **Downloads** do celular.
3. No Termux, cole o comando:
   ```bash
   termux-setup-storage && pkg install unzip -y && unzip -o /sdcard/Download/SpotyLink_Android.zip -d ~/musica && cd ~/musica && bash android/instalar_spotylink_android.sh
   ```
4. Depois de instalado, para abrir basta digitar `spotylink` no Termux!
