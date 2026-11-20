#!/data/data/com.termux/files/usr/bin/bash
# ========================================================
# Instalador Automatizado do SpotyLink para Android (Termux)
# ========================================================

clear
echo "======================================================="
echo "🎵 Instalador do SpotyLink para Android"
echo "======================================================="
echo ""
echo "[1/3] Instalando dependências (Python, FFmpeg)..."
pkg install -y python ffmpeg

echo "[2/3] Instalando pacotes Python (yt-dlp, flask)..."
pip install yt-dlp flask

echo "[3/3] Configurando comando direto 'spotylink'..."
mkdir -p "$PREFIX/bin"
cat << 'EOF' > "$PREFIX/bin/spotylink"
#!/data/data/com.termux/files/usr/bin/bash
cd ~/musica
echo "Iniciando SpotyLink..."
(sleep 1 && am start -a android.intent.action.VIEW -d http://localhost:5000 2>/dev/null) &
python mobile_server.py
EOF
chmod +x "$PREFIX/bin/spotylink"

echo ""
echo "======================================================="
echo "✅ Instalação concluída com sucesso!"
echo ""
echo "Para abrir o SpotyLink a qualquer momento no celular:"
echo "👉 Basta digitar: spotylink"
echo ""
echo "O SpotyLink abrirá no seu navegador (http://localhost:5000)"
echo "Toque no menu (⋮) e clique em 'Instalar aplicativo'"
echo "para adicionar o ícone verde na sua tela inicial!"
echo "======================================================="
