package com.spotylink.app;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.os.Binder;
import android.os.Build;
import android.os.IBinder;
import android.support.v4.media.MediaMetadataCompat;
import android.support.v4.media.session.MediaSessionCompat;
import android.support.v4.media.session.PlaybackStateCompat;

import androidx.core.app.NotificationCompat;

import java.io.File;

public class MusicService extends Service {
    public static final String CHANNEL_ID = "spotylink_playback_channel";
    public static final int NOTIFICATION_ID = 1001;

    public static final String ACTION_PLAY = "com.spotylink.app.ACTION_PLAY";
    public static final String ACTION_PAUSE = "com.spotylink.app.ACTION_PAUSE";
    public static final String ACTION_PREV = "com.spotylink.app.ACTION_PREV";
    public static final String ACTION_NEXT = "com.spotylink.app.ACTION_NEXT";
    public static final String ACTION_STOP = "com.spotylink.app.ACTION_STOP";

    private final IBinder binder = new LocalBinder();
    private MediaPlayer mediaPlayer;
    private MediaSessionCompat mediaSession;
    private String currentTitle = "SpotyLink";
    private String currentArtist = "SpotyLink";
    private String currentPath = "";
    private PlaybackListener listener;

    public interface PlaybackListener {
        void onPlaybackChanged(boolean isPlaying, int currentPosMs, int durationMs);
        void onTrackEnded();
        void onNextRequested();
        void onPrevRequested();
    }

    public class LocalBinder extends Binder {
        public MusicService getService() {
            return MusicService.this;
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();

        mediaSession = new MediaSessionCompat(this, "SpotyLinkSession");
        mediaSession.setCallback(new MediaSessionCompat.Callback() {
            @Override
            public void onPlay() {
                resume();
            }

            @Override
            public void onPause() {
                pause();
            }

            @Override
            public void onSkipToNext() {
                if (listener != null) listener.onNextRequested();
            }

            @Override
            public void onSkipToPrevious() {
                if (listener != null) listener.onPrevRequested();
            }

            @Override
            public void onStop() {
                stopPlayback();
            }

            @Override
            public void onSeekTo(long pos) {
                seekTo((int) pos);
            }
        });
        mediaSession.setActive(true);
    }

    public void setPlaybackListener(PlaybackListener l) {
        this.listener = l;
    }

    public void play(String path, String title, String artist) {
        this.currentPath = path;
        this.currentTitle = (title != null && !title.isEmpty()) ? title : "Música";
        this.currentArtist = (artist != null && !artist.isEmpty()) ? artist : "SpotyLink";

        try {
            if (mediaPlayer != null) {
                mediaPlayer.stop();
                mediaPlayer.release();
                mediaPlayer = null;
            }

            mediaPlayer = new MediaPlayer();
            mediaPlayer.setAudioAttributes(new AudioAttributes.Builder()
                    .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .build());

            if (path.startsWith("http://") || path.startsWith("https://")) {
                mediaPlayer.setDataSource(path);
            } else {
                mediaPlayer.setDataSource(path);
            }

            mediaPlayer.setOnPreparedListener(mp -> {
                mp.start();
                updateMediaSession(true);
                startForeground(NOTIFICATION_ID, buildNotification(true));
                if (listener != null) {
                    listener.onPlaybackChanged(true, mp.getCurrentPosition(), mp.getDuration());
                }
            });

            mediaPlayer.setOnCompletionListener(mp -> {
                updateMediaSession(false);
                startForeground(NOTIFICATION_ID, buildNotification(false));
                if (listener != null) {
                    listener.onTrackEnded();
                }
            });

            mediaPlayer.setOnErrorListener((mp, what, extra) -> {
                stopPlayback();
                return false;
            });

            mediaPlayer.prepareAsync();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void pause() {
        if (mediaPlayer != null && mediaPlayer.isPlaying()) {
            mediaPlayer.pause();
            updateMediaSession(false);
            startForeground(NOTIFICATION_ID, buildNotification(false));
            if (listener != null) {
                listener.onPlaybackChanged(false, mediaPlayer.getCurrentPosition(), mediaPlayer.getDuration());
            }
        }
    }

    public void resume() {
        if (mediaPlayer != null && !mediaPlayer.isPlaying()) {
            mediaPlayer.start();
            updateMediaSession(true);
            startForeground(NOTIFICATION_ID, buildNotification(true));
            if (listener != null) {
                listener.onPlaybackChanged(true, mediaPlayer.getCurrentPosition(), mediaPlayer.getDuration());
            }
        }
    }

    public void seekTo(int posMs) {
        if (mediaPlayer != null) {
            mediaPlayer.seekTo(posMs);
            updateMediaSession(mediaPlayer.isPlaying());
        }
    }

    public boolean isPlaying() {
        return mediaPlayer != null && mediaPlayer.isPlaying();
    }

    public int getCurrentPosition() {
        return mediaPlayer != null ? mediaPlayer.getCurrentPosition() : 0;
    }

    public int getDuration() {
        return mediaPlayer != null ? mediaPlayer.getDuration() : 0;
    }

    public void stopPlayback() {
        if (mediaPlayer != null) {
            try {
                mediaPlayer.stop();
                mediaPlayer.release();
            } catch (Exception ignored) {}
            mediaPlayer = null;
        }
        stopForeground(true);
        if (listener != null) {
            listener.onPlaybackChanged(false, 0, 0);
        }
    }

    private void updateMediaSession(boolean isPlaying) {
        if (mediaSession == null) return;

        PlaybackStateCompat.Builder stateBuilder = new PlaybackStateCompat.Builder()
                .setActions(PlaybackStateCompat.ACTION_PLAY |
                        PlaybackStateCompat.ACTION_PAUSE |
                        PlaybackStateCompat.ACTION_PLAY_PAUSE |
                        PlaybackStateCompat.ACTION_SKIP_TO_NEXT |
                        PlaybackStateCompat.ACTION_SKIP_TO_PREVIOUS |
                        PlaybackStateCompat.ACTION_SEEK_TO)
                .setState(isPlaying ? PlaybackStateCompat.STATE_PLAYING : PlaybackStateCompat.STATE_PAUSED,
                        mediaPlayer != null ? mediaPlayer.getCurrentPosition() : 0, 1.0f);

        mediaSession.setPlaybackState(stateBuilder.build());

        MediaMetadataCompat.Builder metaBuilder = new MediaMetadataCompat.Builder()
                .putString(MediaMetadataCompat.METADATA_KEY_TITLE, currentTitle)
                .putString(MediaMetadataCompat.METADATA_KEY_ARTIST, currentArtist)
                .putLong(MediaMetadataCompat.METADATA_KEY_DURATION, mediaPlayer != null ? mediaPlayer.getDuration() : 0);

        mediaSession.setMetadata(metaBuilder.build());
    }

    private Notification buildNotification(boolean isPlaying) {
        Intent openAppIntent = new Intent(this, MainActivity.class);
        PendingIntent contentIntent = PendingIntent.getActivity(this, 0, openAppIntent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        PendingIntent prevIntent = PendingIntent.getService(this, 1,
                new Intent(this, MusicService.class).setAction(ACTION_PREV),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        PendingIntent playPauseIntent = PendingIntent.getService(this, 2,
                new Intent(this, MusicService.class).setAction(isPlaying ? ACTION_PAUSE : ACTION_PLAY),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        PendingIntent nextIntent = PendingIntent.getService(this, 3,
                new Intent(this, MusicService.class).setAction(ACTION_NEXT),
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        int playIcon = isPlaying ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play;

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(currentTitle)
                .setContentText(currentArtist)
                .setSmallIcon(R.drawable.ic_notification)
                .setContentIntent(contentIntent)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setOnlyAlertOnce(true)
                .addAction(android.R.drawable.ic_media_previous, "Anterior", prevIntent)
                .addAction(playIcon, isPlaying ? "Pausar" : "Tocar", playPauseIntent)
                .addAction(android.R.drawable.ic_media_next, "Próxima", nextIntent)
                .setStyle(new androidx.media.app.NotificationCompat.MediaStyle()
                        .setMediaSession(mediaSession.getSessionToken())
                        .setShowActionsInCompactView(0, 1, 2))
                .build();
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    "SpotyLink Reprodução",
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Controles de reprodução de música do SpotyLink");
            channel.setShowBadge(false);
            channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);

            NotificationManager nm = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && intent.getAction() != null) {
            String act = intent.getAction();
            if (ACTION_PLAY.equals(act)) {
                resume();
            } else if (ACTION_PAUSE.equals(act)) {
                pause();
            } else if (ACTION_PREV.equals(act)) {
                if (listener != null) listener.onPrevRequested();
            } else if (ACTION_NEXT.equals(act)) {
                if (listener != null) listener.onNextRequested();
            } else if (ACTION_STOP.equals(act)) {
                stopPlayback();
            }
        }
        return START_NOT_STICKY;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    @Override
    public void onDestroy() {
        stopPlayback();
        if (mediaSession != null) {
            mediaSession.release();
        }
        super.onDestroy();
    }
}
