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
        showToast("Iniciando download com yt-dlp...");

        new Thread(() -> {
            try {
                // Garante que YoutubeDL e FFmpeg estejam inicializados
                try {
                    com.yausername.youtubedl_android.YoutubeDL.getInstance().init(activity.getApplicationContext());
                    com.yausername.ffmpeg.FFmpeg.getInstance().init(activity.getApplicationContext());
                } catch (Exception ignored) {}

                File dir = new File(activity.getFilesDir(), "downloads");
                if (!dir.exists()) dir.mkdirs();

                String trackId = UUID.randomUUID().toString().substring(0, 10);
                File destFile = new File(dir, trackId + ".mp3");

                // Tenta buscar metadados de Título e Artista
                String title = "Música";
                String artist = "SpotyLink";
                try {
                    com.yausername.youtubedl_android.YoutubeDLRequest infoRequest =
                            new com.yausername.youtubedl_android.YoutubeDLRequest(cleanUrl);
                    com.yausername.youtubedl_android.mapper.VideoInfo info =
                            com.yausername.youtubedl_android.YoutubeDL.getInstance().getInfo(infoRequest);
                    if (info != null) {
                        if (info.getTitle() != null && !info.getTitle().isEmpty()) {
                            title = info.getTitle();
                        }
                        if (info.getUploader() != null && !info.getUploader().isEmpty()) {
                            artist = info.getUploader();
                        }
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }

                // Prepara a requisição para o yt-dlp nativo
                com.yausername.youtubedl_android.YoutubeDLRequest request =
                        new com.yausername.youtubedl_android.YoutubeDLRequest(cleanUrl);

                request.addOption("--extract-audio");
                request.addOption("--audio-format", "mp3");
                request.addOption("--audio-quality", "0");
                request.addOption("--no-playlist");
                request.addOption("-o", new File(dir, trackId + ".%(ext)s").getAbsolutePath());

                // Executa download e conversão nativa
                com.yausername.youtubedl_android.YoutubeDL.getInstance().execute(request);

                File finalFile = null;
                if (destFile.exists() && destFile.length() > 0) {
                    finalFile = destFile;
                } else {
                    File[] matching = dir.listFiles((d, name) -> name.startsWith(trackId));
                    if (matching != null && matching.length > 0 && matching[0].length() > 0) {
                        finalFile = matching[0];
                    }
                }

                if (finalFile != null) {
                    if ("Música".equals(title)) {
                        try {
                            android.media.MediaMetadataRetriever mmr = new android.media.MediaMetadataRetriever();
                            mmr.setDataSource(finalFile.getAbsolutePath());
                            String metaTitle = mmr.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_TITLE);
                            String metaArtist = mmr.extractMetadata(android.media.MediaMetadataRetriever.METADATA_KEY_ARTIST);
                            if (metaTitle != null && !metaTitle.trim().isEmpty()) title = metaTitle.trim();
                            if (metaArtist != null && !metaArtist.trim().isEmpty()) artist = metaArtist.trim();
                            mmr.release();
                        } catch (Exception ignored) {}
                    }

                    showToast("Download concluído com sucesso!");
                    notifyDownloadFinished(true, trackId, title, artist, finalFile.getAbsolutePath());
                } else {
                    showToast("Falha ao salvar áudio.");
                    notifyDownloadFinished(false, null, null, null, null);
                }

            } catch (Exception e) {
                e.printStackTrace();
                showToast("Erro no download: " + (e.getMessage() != null ? e.getMessage() : "URL inválida ou indisponível"));
                notifyDownloadFinished(false, null, null, null, null);
            }
        }).start();
    }

    private void notifyDownloadFinished(boolean success, String trackId, String title, String artist, String path) {
        mainHandler.post(() -> {
            if (activity.getWebView() != null) {
                String js = String.format("javascript:window.onNativeDownloadComplete(%b, '%s', '%s', '%s', '%s');",
                        success,
                        trackId != null ? trackId : "",
                        title != null ? title.replace("'", "\\'").replace("\n", " ") : "",
                        artist != null ? artist.replace("'", "\\'").replace("\n", " ") : "",
                        path != null ? path.replace("\\", "/") : "");
                activity.getWebView().evaluateJavascript(js, null);
            }
        });
    }

    @JavascriptInterface
    public void searchOnline(String query) {
        new Thread(() -> {
            try {
                try {
                    com.yausername.youtubedl_android.YoutubeDL.getInstance().init(activity.getApplicationContext());
                } catch (Exception ignored) {}

                String searchPrefix = "ytsearch6:";
                String cleanQuery = query.trim();
                if (cleanQuery.toLowerCase().startsWith("sc:") || cleanQuery.toLowerCase().startsWith("soundcloud:")) {
                    searchPrefix = "scsearch6:";
                    cleanQuery = cleanQuery.replaceFirst("^(?i)(sc:|soundcloud:)", "").trim();
                }

                com.yausername.youtubedl_android.YoutubeDLRequest request =
                        new com.yausername.youtubedl_android.YoutubeDLRequest(searchPrefix + cleanQuery);
                request.addOption("--dump-json");
                request.addOption("--flat-playlist");

                com.yausername.youtubedl_android.YoutubeDLResponse response =
                        com.yausername.youtubedl_android.YoutubeDL.getInstance().execute(request);

                String out = response.getOut();
                JSONArray results = new JSONArray();
                if (out != null && !out.isEmpty()) {
                    String[] lines = out.split("\n");
                    for (String line : lines) {
                        line = line.trim();
                        if (!line.isEmpty()) {
                            try {
                                JSONObject obj = new JSONObject(line);
                                JSONObject item = new JSONObject();
                                item.put("title", obj.optString("title", "Música"));
                                item.put("uploader", obj.optString("uploader", obj.optString("channel", "Artista")));

                                String durationStr = obj.optString("duration_string", "");
                                if (durationStr.isEmpty() && obj.has("duration")) {
                                    int secs = obj.optInt("duration", 0);
                                    int mins = secs / 60;
                                    int remSecs = secs % 60;
                                    durationStr = String.format("%d:%02d", mins, remSecs);
                                }
                                item.put("duration", durationStr);

                                String webUrl = obj.optString("url", "");
                                if (webUrl.isEmpty() && obj.has("id")) {
                                    webUrl = "https://www.youtube.com/watch?v=" + obj.getString("id");
                                }
                                item.put("url", webUrl);

                                String thumb = "";
                                if (obj.has("thumbnails")) {
                                    JSONArray thumbs = obj.getJSONArray("thumbnails");
                                    if (thumbs.length() > 0) {
                                        thumb = thumbs.getJSONObject(thumbs.length() - 1).optString("url", "");
                                    }
                                } else if (obj.has("thumbnail")) {
                                    thumb = obj.optString("thumbnail", "");
                                }
                                item.put("thumbnail", thumb);

                                results.put(item);
                            } catch (Exception ignored) {}
                        }
                    }
                }

                mainHandler.post(() -> {
                    if (activity.getWebView() != null) {
                        String js = "javascript:window.onSearchResults(" + results.toString() + ");";
                        activity.getWebView().evaluateJavascript(js, null);
                    }
                });

            } catch (Exception e) {
                e.printStackTrace();
                mainHandler.post(() -> {
                    showToast("Erro na pesquisa: " + (e.getMessage() != null ? e.getMessage() : "tente novamente"));
                    if (activity.getWebView() != null) {
                        activity.getWebView().evaluateJavascript("javascript:window.onSearchResults([]);", null);
                    }
                });
            }
        }).start();
    }

    @JavascriptInterface
    public void streamTrack(String rawUrl, String title, String artist, String coverUrl) {
        showToast("Carregando reprodução online...");
        new Thread(() -> {
            try {
                try {
                    com.yausername.youtubedl_android.YoutubeDL.getInstance().init(activity.getApplicationContext());
                } catch (Exception ignored) {}

                String cleanUrl = cleanMobileUrl(rawUrl);
                com.yausername.youtubedl_android.YoutubeDLRequest request =
                        new com.yausername.youtubedl_android.YoutubeDLRequest(cleanUrl);
                request.addOption("-g");
                request.addOption("-f", "bestaudio/best");

                com.yausername.youtubedl_android.YoutubeDLResponse response =
                        com.yausername.youtubedl_android.YoutubeDL.getInstance().execute(request);

                String streamUrl = response.getOut();
                if (streamUrl != null) {
                    streamUrl = streamUrl.trim();
                    if (streamUrl.contains("\n")) {
                        streamUrl = streamUrl.split("\n")[0].trim();
                    }
                }

                if (streamUrl != null && !streamUrl.isEmpty()) {
                    final String finalStreamUrl = streamUrl;
                    mainHandler.post(() -> {
                        MusicService service = activity.getMusicService();
                        if (service != null) {
                            service.play(finalStreamUrl, title, artist);
                        }
                        if (activity.getWebView() != null) {
                            String js = String.format("javascript:window.onNativeStreamStarted('%s', '%s', '%s');",
                                    title != null ? title.replace("'", "\\'") : "",
                                    artist != null ? artist.replace("'", "\\'") : "",
                                    coverUrl != null ? coverUrl.replace("'", "\\'") : "");
                            activity.getWebView().evaluateJavascript(js, null);
                        }
                    });
                } else {
                    showToast("Não foi possível carregar áudio para streaming.");
                }

            } catch (Exception e) {
                e.printStackTrace();
                showToast("Erro ao iniciar áudio online: " + (e.getMessage() != null ? e.getMessage() : "indisponível"));
            }
        }).start();
    }

    @JavascriptInterface
    public String getClipboard() {
        try {
            android.content.ClipboardManager clipboard = (android.content.ClipboardManager) activity.getSystemService(Context.CLIPBOARD_SERVICE);
            if (clipboard != null && clipboard.hasPrimaryClip() && clipboard.getPrimaryClip().getItemCount() > 0) {
                CharSequence text = clipboard.getPrimaryClip().getItemAt(0).getText();
                if (text != null) return text.toString();
            }
        } catch (Exception ignored) {}
        return "";
    }

    private String cleanMobileUrl(String raw) {
        if (raw == null) return "";
        String s = raw.trim();
        Matcher m = Pattern.compile("https?://\\S+").matcher(s);
        if (m.find()) {
            s = m.group(0);
        } else if (!s.startsWith("http://") && !s.startsWith("https://")) {
            return "ytsearch1:" + s;
        }
        if (s.contains("youtube.com") || s.contains("youtu.be")) {
            s = s.replaceAll("m\\.youtube\\.com", "youtube.com");
            s = s.replaceAll("youtube\\.com/shorts/", "youtube.com/watch?v=");
            s = s.replaceAll("[?&]si=[^&]+", "");
        }
        return s;
    }
}
