
import re
import subprocess
import json
from datetime import datetime, timedelta
from typing import Optional
from config import YTDLP_COOKIES, SONG_BUFFER_SECONDS


YOUTUBE_URL_PATTERN = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)"
    r"[\w\-]{11}"
)


def is_valid_youtube_url(url: str) -> bool:
    
    return bool(YOUTUBE_URL_PATTERN.search(url))


def normalize_youtube_url(url: str) -> str:
    
    match = re.search(r"(?:youtu\.be/|v=)([\w\-]{11})", url)
    if match:
        return f"https://www.youtube.com/watch?v={match.group(1)}"
    return url


async def fetch_youtube_info(url: str) -> Optional[dict]:
    
    try:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--no-playlist",
        ]

        if YTDLP_COOKIES:
            cmd += ["--cookies", YTDLP_COOKIES]

        cmd.append(url)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print(f"[yt-dlp] 오류: {result.stderr[:200]}")
            return None

        info = json.loads(result.stdout)
        return {
            "title":     info.get("title", "제목 없음"),
            "duration":  int(info.get("duration", 0)),
            "thumbnail": info.get("thumbnail", ""),
            "video_id":  info.get("id", ""),
            "uploader":  info.get("uploader", ""),
        }

    except subprocess.TimeoutExpired:
        print(f"[yt-dlp] 타임아웃: {url}")
        return None
    except Exception as e:
        print(f"[yt-dlp] 예외: {e}")
        return None


def seconds_to_hms(seconds: int) -> str:
    
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_optimal_playlist(
    approved_songs: list,
    broadcast_start: datetime,
    broadcast_end: datetime
) -> list:
    
    total_seconds = int((broadcast_end - broadcast_start).total_seconds())
    print(f"[Playlist] 방송 총 시간: {seconds_to_hms(total_seconds)}")

    if total_seconds <= 0:
        print("[Playlist] 방송 시간이 유효하지 않음")
        return []

    
    processed_songs = []
    max_avg_rating = 0.0
    
    for song in approved_songs:
        r_sum = song.get("rating_sum", 0)
        r_count = song.get("rating_count", 0)
        avg = float(r_sum) / r_count if r_count > 0 else 0.0
        song["avg_rating"] = avg
        if avg > max_avg_rating:
            max_avg_rating = avg
        processed_songs.append(song)

    
    
    processed_songs.sort(key=lambda x: (
        not (x["avg_rating"] == max_avg_rating and max_avg_rating > 0), 
        x.get("play_count", 0),
        x.get("approved_at", "")
    ))

    playlist = []
    used_seconds = 0

    for song in processed_songs:
        duration = song.get("duration", 0)
        if duration <= 0:
            continue

        song_total = duration + SONG_BUFFER_SECONDS

        if used_seconds + song_total > total_seconds:
            remaining = total_seconds - used_seconds
            if duration <= remaining:
                play_time = broadcast_start + timedelta(seconds=used_seconds)
                playlist.append({
                    **song,
                    "play_at": play_time.strftime("%H:%M:%S"),
                    "duration_str": seconds_to_hms(duration),
                    "order": len(playlist) + 1,
                })
                used_seconds += duration
            break

        play_time = broadcast_start + timedelta(seconds=used_seconds)
        playlist.append({
            **song,
            "play_at": play_time.strftime("%H:%M:%S"),
            "duration_str": seconds_to_hms(duration),
            "order": len(playlist) + 1,
        })
        used_seconds += song_total

    remaining_seconds = total_seconds - used_seconds
    print(f"[Playlist] {len(playlist)}곡 선정, "
          f"총 {seconds_to_hms(used_seconds)} / {seconds_to_hms(total_seconds)}, "
          f"여유 시간: {seconds_to_hms(remaining_seconds)}")

    return playlist
