
import re
import subprocess
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from config import YTDLP_COOKIES, SONG_BUFFER_SECONDS, STREAM_QUALITY


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


async def download_youtube_video(url: str, output_path: str) -> bool:
    """유튜브 영상을 로컬 temp 폴더에 고화질로 다운로드 (mp4 병합)"""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # mp4로 병합하여 저장 (비디오+오디오 합치기)
        cmd = [
            "yt-dlp",
            "-f", STREAM_QUALITY,
            "--merge-output-format", "mp4",
            "-o", output_path,
            "--no-playlist",
            "--force-ipv4"
        ]

        if YTDLP_COOKIES:
            cmd += ["--cookies", YTDLP_COOKIES]

        cmd.append(url)

        print(f"[Download] 시작: {url}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()

        if process.returncode == 0:
            print(f"[Download] 완료: {output_path}")
            return True
        else:
            print(f"[Download] 실패: {stderr.decode()[:200]}")
            return False
    except Exception as e:
        print(f"[Download] 예외 발생: {e}")
        return False


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
    for song in approved_songs:
        f_count = song.get("five_star_count", 0)
        p_count = song.get("play_count", 0)
        
        # 가중치 점수 계산 (최대 1.0)
        # 10%: 5명 이상이 5점을 남긴 경우
        rating_score = 0.1 if f_count >= 5 else 0.0
        # 90%: 재생 횟수가 적을수록 높은 점수
        play_score = 0.9 / (p_count + 1)
        
        song["selection_score"] = rating_score + play_score
        processed_songs.append(song)

    
    # 점수 내림차순 정렬 (높은 점수가 우선)
    processed_songs.sort(key=lambda x: x["selection_score"], reverse=True)

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
    print(f"[Playlist] {len(playlist)}곡 선정 완료, "
          f"총 {seconds_to_hms(used_seconds)} / {seconds_to_hms(total_seconds)}, "
          f"여유 시간: {seconds_to_hms(remaining_seconds)}")

    return playlist
