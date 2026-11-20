package com.spotylink.app;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.webkit.JavascriptInterface;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

public class WebAppInterface {
    private final MainActivity activity;
    private final Handler mainHandler;
    private final OkHttpClient httpClient;

    public WebAppInterface(MainActivity activity) {
        this.activity = activity;
        this.mainHandler = new Handler(Looper.getMainLooper());
        this.httpClient = new OkHttpClient.Builder().build();
    }

    @JavascriptInterface
    public String getLibrary() {
        try {
            File file = new File(activity.getFilesDir(), "library.json");
            if (!file.exists()) {
                JSONObject initial = new JSONObject();
                initial.put("tracks", new JSONArray());
                JSONArray playlists = new JSONArray();
                JSONObject dlPl = new JSONObject();
                dlPl.put("id", "downloads");
                dlPl.put("name", "Downloads");
                dlPl.put("track_ids", new JSONArray());
                playlists.put(dlPl);
                initial.put("playlists", playlists);
                return initial.toString();
            }

            FileInputStream fis = new FileInputStream(file);
            byte[] data = new byte[(int) file.length()];
            fis.read(data);
            fis.close();
            return new String(data, "UTF-8");
        } catch (Exception e) {
            e.printStackTrace();
            return "{\"tracks\":[],\"playlists\":[{\"id\":\"downloads\",\"name\":\"Downloads\",\"track_ids\":[]}]}";
        }
    }

    @JavascriptInterface
    public void saveLibrary(String jsonStr) {
        try {
            File file = new File(activity.getFilesDir(), "library.json");
            FileOutputStream fos = new FileOutputStream(file);
            fos.write(jsonStr.getBytes("UTF-8"));
            fos.close();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    @JavascriptInterface
    public void playTrack(String audioPath, String title, String artist) {
        mainHandler.post(() -> {
            MusicService service = activity.getMusicService();
            if (service != null) {
                service.play(audioPath, title, artist);
            }
        });
    }

    @JavascriptInterface
    public void pauseTrack() {
        mainHandler.post(() -> {
            MusicService service = activity.getMusicService();
            if (service != null) {
                service.pause();
            }
        });
    }

    @JavascriptInterface
    public void resumeTrack() {
        mainHandler.post(() -> {
            MusicService service = activity.getMusicService();
            if (service != null) {
                service.resume();
            }
        });
    }

    @JavascriptInterface
    public void seekTrack(int posMs) {
        mainHandler.post(() -> {
            MusicService service = activity.getMusicService();
            if (service != null) {
                service.seekTo(posMs);
            }
        });
    }

    @JavascriptInterface
    public void pickLocalAudio() {
        mainHandler.post(activity::openAudioPicker);
    }

    @JavascriptInterface
    public void showToast(String message) {
        mainHandler.post(() -> Toast.makeText(activity, message, Toast.LENGTH_SHORT).show());
    }

    @JavascriptInterface
    public void deleteTrackFile(String trackId) {
        try {
            File dir = new File(activity.getFilesDir(), "downloads");
            if (dir.exists()) {
                File[] files = dir.listFiles((d, name) -> name.startsWith(trackId));
                if (files != null) {
                    for (File f : files) f.delete();
                }
            }
            File coverDir = new File(activity.getFilesDir(), "covers");
            if (coverDir.exists()) {
                File[] covers = coverDir.listFiles((d, name) -> name.startsWith(trackId));
                if (covers != null) {
                    for (File c : covers) c.delete();
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    @JavascriptInterface
    public void downloadAudioLink(String rawUrl) {
        String cleanUrl = cleanMobileUrl(rawUrl);
        showToast("Iniciando download...");

        // Resolve áudio através de endpoint de extração aberta de áudio ou download direto
        String apiUrl = "https://api.cobalt.tools/api/json";
        JSONObject payload = new JSONObject();
        try {
            payload.put("url", cleanUrl);
            payload.put("downloadMode", "audio");
            payload.put("audioFormat", "mp3");
        } catch (Exception ignored) {}

        okhttp3.RequestBody body = okhttp3.RequestBody.create(
                payload.toString(),
                okhttp3.MediaType.parse("application/json; charset=utf-8")
        );

        Request req = new Request.Builder()
                .url(apiUrl)
                .addHeader("Accept", "application/json")
                .addHeader("Content-Type", "application/json")
                .post(body)
                .build();

        httpClient.newCall(req).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, java.io.IOException e) {
                showToast("Erro de rede ao buscar áudio: " + e.getMessage());
                notifyDownloadFinished(false, null, null, null);
            }

            @Override
            public void onResponse(Call call, Response res) throws java.io.IOException {
                try {
                    String respStr = res.body().string();
                    JSONObject json = new JSONObject(respStr);
                    String streamUrl = json.optString("url");
                    String title = json.optString("title", "Música Baixada");

                    if (streamUrl != null && !streamUrl.isEmpty()) {
                        saveRemoteStream(streamUrl, title);
                    } else {
                        // Tenta resolver por serviço alternativo
                        resolveFallback(cleanUrl);
                    }
                } catch (Exception ex) {
                    resolveFallback(cleanUrl);
                }
            }
        });
    }

    private void resolveFallback(String url) {
        // Fallback direto: se for link direto de áudio ou stream
        if (url.endsWith(".mp3") || url.endsWith(".m4a") || url.endsWith(".wav") || url.endsWith(".ogg")) {
            saveRemoteStream(url, "Música " + System.currentTimeMillis());
        } else {
            showToast("Para links do YouTube, use também '📁 Importar MP3' ou aguarde a conexão.");
            notifyDownloadFinished(false, null, null, null);
        }
    }

    private void saveRemoteStream(String streamUrl, String title) {
        Request dlReq = new Request.Builder().url(streamUrl).build();
        httpClient.newCall(dlReq).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, java.io.IOException e) {
                showToast("Falha no download do áudio");
                notifyDownloadFinished(false, null, null, null);
            }

            @Override
            public void onResponse(Call call, Response res) throws java.io.IOException {
                try {
                    File dir = new File(activity.getFilesDir(), "downloads");
                    if (!dir.exists()) dir.mkdirs();

                    String trackId = UUID.randomUUID().toString().substring(0, 10);
                    File audioFile = new File(dir, trackId + ".mp3");

                    InputStream is = res.body().byteStream();
                    FileOutputStream fos = new FileOutputStream(audioFile);
                    byte[] buf = new byte[8192];
                    int len;
                    while ((len = is.read(buf)) != -1) {
                        fos.write(buf, 0, len);
                    }
                    fos.close();
                    is.close();

                    showToast("Música baixada com sucesso!");
                    notifyDownloadFinished(true, trackId, title, audioFile.getAbsolutePath());
                } catch (Exception e) {
                    showToast("Erro ao salvar arquivo: " + e.getMessage());
                    notifyDownloadFinished(false, null, null, null);
                }
            }
        });
    }

    private void notifyDownloadFinished(boolean success, String trackId, String title, String path) {
        mainHandler.post(() -> {
            if (activity.getWebView() != null) {
                String js = String.format("javascript:window.onNativeDownloadComplete(%b, '%s', '%s', '%s');",
                        success,
                        trackId != null ? trackId : "",
                        title != null ? title.replace("'", "\\'") : "",
                        path != null ? path.replace("\\", "/") : "");
                activity.getWebView().evaluateJavascript(js, null);
            }
        });
    }

    private String cleanMobileUrl(String raw) {
        if (raw == null) return "";
        String s = raw.trim();
        Matcher m = Pattern.compile("https?://\\S+").matcher(s);
        if (m.find()) s = m.group(0);
        s = s.replaceAll("m\\.youtube\\.com", "youtube.com");
        s = s.replaceAll("youtube\\.com/shorts/", "youtube.com/watch?v=");
        s = s.replaceAll("[?&]si=[^&]+", "");
        return s;
    }
}
