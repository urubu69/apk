package com.spotylink.app;

import android.Manifest;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.IBinder;
import android.provider.OpenableColumns;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.UUID;

public class MainActivity extends AppCompatActivity implements MusicService.PlaybackListener {

    private static final int PICK_AUDIO_REQUEST = 2001;
    private static final int PERMISSION_REQUEST_CODE = 3001;

    private WebView webView;
    private MusicService musicService;
    private boolean isBound = false;

    private final ServiceConnection serviceConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder binder) {
            MusicService.LocalBinder b = (MusicService.LocalBinder) binder;
            musicService = b.getService();
            musicService.setPlaybackListener(MainActivity.this);
            isBound = true;
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            musicService = null;
            isBound = false;
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Inicia e vincula o serviço de áudio em segundo plano
        Intent serviceIntent = new Intent(this, MusicService.class);
        startService(serviceIntent);
        bindService(serviceIntent, serviceConnection, Context.BIND_AUTO_CREATE);

        // Inicializa o WebView
        webView = new WebView(this);
        setContentView(webView);

        setupWebView();
        checkPermissions();

        // Inicializa o motor nativo yt-dlp e ffmpeg em segundo plano
        new Thread(() -> {
            try {
                com.yausername.youtubedl_android.YoutubeDL.getInstance().init(getApplicationContext());
                com.yausername.ffmpeg.FFmpeg.getInstance().init(getApplicationContext());
            } catch (Exception e) {
                e.printStackTrace();
            }
        }).start();

        // Carrega o aplicativo nativamente do pacote de assets (sem localhost!)
        webView.loadUrl("file:///android_asset/index.html");
    }

    private void setupWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setAllowUniversalAccessFromFileURLs(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());
        webView.addJavascriptInterface(new WebAppInterface(this), "Android");
        webView.setBackgroundColor(0xFF121212);
    }

    private void checkPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(this, new String[]{
                        Manifest.permission.POST_NOTIFICATIONS,
                        Manifest.permission.READ_MEDIA_AUDIO
                }, PERMISSION_REQUEST_CODE);
            }
        }
    }

    public void openAudioPicker() {
        Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
        intent.setType("audio/*");
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(Intent.createChooser(intent, "Selecione uma música"), PICK_AUDIO_REQUEST);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, @Nullable Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == PICK_AUDIO_REQUEST && resultCode == RESULT_OK && data != null) {
            Uri uri = data.getData();
            if (uri != null) {
                importLocalAudioFile(uri);
            }
        }
    }

    private void importLocalAudioFile(Uri uri) {
        try {
            String fileName = "Música Importada";
            String artist = "SpotyLink";
            Cursor cursor = getContentResolver().query(uri, null, null, null, null);
            if (cursor != null) {
                int nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (cursor.moveToFirst() && nameIndex != -1) {
                    fileName = cursor.getString(nameIndex);
                }
                cursor.close();
            }

            if (fileName.contains(".")) {
                fileName = fileName.substring(0, fileName.lastIndexOf('.'));
            }

            try {
                android.media.MediaMetadataRetriever mmr = new android.media.MediaMetadataRetriever();
                mmr.setDataSource(this, uri);
                String metaTitle = mmr.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_TITLE);
                String metaArtist = mmr.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_ARTIST);
                if (metaTitle != null && !metaTitle.trim().isEmpty()) fileName = metaTitle.trim();
                if (metaArtist != null && !metaArtist.trim().isEmpty()) artist = metaArtist.trim();
                mmr.release();
            } catch (Exception ignored) {}

            File dir = new File(getFilesDir(), "downloads");
            if (!dir.exists()) dir.mkdirs();

            String trackId = UUID.randomUUID().toString().substring(0, 10);
            File dest = new File(dir, trackId + ".mp3");

            InputStream is = getContentResolver().openInputStream(uri);
            FileOutputStream fos = new FileOutputStream(dest);
            byte[] buf = new byte[8192];
            int len;
            while ((len = is.read(buf)) != -1) {
                fos.write(buf, 0, len);
            }
            fos.close();
            is.close();

            Toast.makeText(this, "Música importada!", Toast.LENGTH_SHORT).show();

            String js = String.format("javascript:window.onNativeDownloadComplete(true, '%s', '%s', '%s', '%s');",
                    trackId, fileName.replace("'", "\\'"), artist.replace("'", "\\'"), dest.getAbsolutePath().replace("\\", "/"));
            webView.evaluateJavascript(js, null);

        } catch (Exception e) {
            Toast.makeText(this, "Erro ao importar: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    public MusicService getMusicService() {
        return musicService;
    }

    public WebView getWebView() {
        return webView;
    }

    @Override
    public void onPlaybackChanged(boolean isPlaying, int currentPosMs, int durationMs) {
        runOnUiThread(() -> {
            if (webView != null) {
                String js = String.format("javascript:window.onNativePlaybackState(%b, %d, %d);", isPlaying, currentPosMs, durationMs);
                webView.evaluateJavascript(js, null);
            }
        });
    }

    @Override
    public void onTrackEnded() {
        runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript("javascript:window.playNext();", null);
            }
        });
    }

    @Override
    public void onNextRequested() {
        runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript("javascript:window.playNext();", null);
            }
        });
    }

    @Override
    public void onPrevRequested() {
        runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript("javascript:window.playPrev();", null);
            }
        });
    }

    @Override
    public void onBackPressed() {
        // Se a barra lateral estiver aberta, fecha ela primeiro
        webView.evaluateJavascript("javascript:(function(){ if(document.getElementById('sidebarDrawer').classList.contains('open')){ toggleSidebar(false); return true; } return false; })()", value -> {
            if ("true".equals(value)) {
                // Barra lateral fechada, não sai do app
            } else {
                // Move para segundo plano sem fechar para continuar a reprodução
                moveTaskToBack(true);
            }
        });
    }

    @Override
    protected void onDestroy() {
        if (isBound) {
            unbindService(serviceConnection);
            isBound = false;
        }
        super.onDestroy();
    }
}
