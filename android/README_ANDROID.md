# 📱 Guia Completo de Instalação do SpotyLink no Android

O **SpotyLink** foi adaptado para funcionar perfeitamente em smartphones **Android**, com interface responsiva idêntica ao Spotify, controle na tela de bloqueio, reprodução em segundo plano e atalho oficial com o ícone da nota musical verde na tela inicial.

---

## 🌟 Opção 1: Instalação Direta no Celular (100% Offline e Independente do PC - Recomendado)

Neste método, o SpotyLink roda **diretamente dentro do celular**. Você não precisa do computador ligado e pode ouvir, baixar e organizar suas músicas na rua, academia, viagem ou sem internet!

### 🔒 Dúvida frequente: É seguro usar o Termux?
**Sim, 100% seguro!**
- O **Termux** é um aplicativo de código aberto (Open Source) auditado por milhares de desenvolvedores no mundo todo.
- Ele roda em ambiente isolado (*sandbox*) do Android: **não precisa de root** e **não acessa suas fotos, contatos ou mensagens**.
- Recomendamos baixar o Termux pelo **[F-Droid](https://f-droid.org/packages/com.termux/)** (o maior repositório seguro de software livre para Android) ou direto do [GitHub Oficial do Termux](https://github.com/termux/termux-app/releases).

---

### 🚀 Passo a Passo de Instalação no Celular:

#### 1. Instale o Termux no celular
- Baixe e instale o [Termux no F-Droid](https://f-droid.org/packages/com.termux/).

#### 2. Copie o pacote do SpotyLink para o celular
- Conecte o celular ao computador via cabo USB (ou envie por WhatsApp / Google Drive / Telegram).
- Copie o arquivo **`SpotyLink_Android.zip`** (que está na pasta do SpotyLink no seu computador) para a pasta **Downloads** do seu celular.

#### 3. Execute o instalador automático
Abra o **Termux** no celular, cole o comando abaixo e aperte **Enter**:

```bash
termux-setup-storage && pkg install unzip -y && unzip -o /sdcard/Download/SpotyLink_Android.zip -d ~/musica && cd ~/musica && bash android/instalar_spotylink_android.sh
```

*(Se o Android pedir permissão de acesso aos arquivos para o Termux, toque em "Permitir".)*

O instalador configurará o Python, o conversor de áudio FFmpeg e todas as dependências automaticamente!

---

### 🎵 Como Usar no Dia a Dia:

1. Abra o **Termux** e digite:
   ```bash
   spotylink
   ```
2. O SpotyLink iniciará e abrirá automaticamente no seu **Google Chrome**!
3. **Para instalar o ícone na tela inicial**:
   - No Chrome, toque nos três pontinhos no canto superior direito (**⋮**).
   - Toque em **"Instalar aplicativo"** (ou **"Adicionar à tela inicial"**).
4. Pronto! O ícone da nota musical verde aparecerá na sua tela inicial como um app nativo, com player na tela de bloqueio e funcionamento offline!

---

## 📦 Opção 2: Gerar o Pacote Instalador `.apk` com GitHub Actions

Se você prefere um arquivo `.apk` tradicional para instalar direto sem terminal:

1. Os arquivos de compilação já estão prontos:
   - [`buildozer.spec`](buildozer.spec): Configurado com nome SpotyLink, ícone oficial verde e permissões de áudio em segundo plano.
   - [`.github/workflows/build_apk.yml`](../.github/workflows/build_apk.yml): Fluxo automatizado do GitHub Actions.
2. Ao subir o repositório para a sua conta do GitHub, o GitHub compila o arquivo `SpotyLink.apk` automaticamente na nuvem (em servidores Ubuntu) e disponibiliza o download na aba **Actions -> Artifacts**.

---

## 🌐 Opção 3: Conectar o Celular ao Computador via Wi-Fi

Se você estiver em casa e quiser usar o computador como biblioteca central:

1. No computador, abra o SpotyLink e clique no botão **"📱 Conectar no Celular"** (ou execute `Iniciar_Servidor_Mobile.bat`).
2. Abra a câmera do seu celular e escaneie o **QR Code** exibido na tela.
3. Certifique-se de que o computador e o celular estão conectados na mesma rede Wi-Fi.
