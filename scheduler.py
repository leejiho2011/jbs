
import json
import asyncio
import os
import shutil
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import (
    get_schedule, get_approved_requests,
    create_broadcast_log, update_broadcast_log,
    perform_weekly_cleanup
)
from youtube import build_optimal_playlist, download_youtube_video
from streamer import streamer
from config import CLEANUP_COUNT, CLEANUP_DAY, CLEANUP_HOUR


scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
KST = ZoneInfo("Asia/Seoul")

_app_ref = None  

TEMP_DIR = "temp"


async def cleanup_temp_dir(current_playlist: list):
    """temp 폴더에 파일이 7개 이상이면 현재 플레이리스트에 없는 파일 삭제"""
    try:
        if not os.path.exists(TEMP_DIR):
            return

        files = [f for f in os.listdir(TEMP_DIR) if f.endswith(".mp4")]
        if len(files) < 7:
            return

        # 현재 플레이리스트의 파일명 목록 생성
        current_files = []
        for song in current_playlist:
            video_id = song.get("video_id") or song["youtube_url"].split("=")[-1]
            current_files.append(f"{video_id}.mp4")

        deleted_count = 0
        for f in files:
            if f not in current_files:
                file_path = os.path.join(TEMP_DIR, f)
                try:
                    os.remove(file_path)
                    deleted_count += 1
                except:
                    pass
        
        if deleted_count > 0:
            print(f"[Cleanup] temp 폴더 정리 완료: {deleted_count}개 삭제됨")
    except Exception as e:
        print(f"[Cleanup] temp 폴더 정리 중 오류: {e}")


async def prepare_broadcast_files():
    """방송 시작 1분 전에 실행되어 곡들을 미리 다운로드"""
    now = datetime.now(KST)
    
    # 1분 후의 시간을 계산하여 스케줄 확인
    target_time = now + timedelta(minutes=1)
    today = target_time.strftime("%Y-%m-%d")
    current_hm = target_time.strftime("%H:%M")

    schedule = await get_schedule(today)
    if not schedule or schedule["start_time"][:5] != current_hm:
        return

    print(f"[Scheduler] 방송 1분 전, 다운로드 시작: {current_hm}")

    approved = await get_approved_requests()
    if not approved:
        return

    broadcast_start = datetime.strptime(f"{today} {schedule['start_time'][:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    broadcast_end   = datetime.strptime(f"{today} {schedule['end_time'][:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    
    if broadcast_end <= broadcast_start:
        broadcast_end += timedelta(days=1)

    playlist = build_optimal_playlist(approved, broadcast_start, broadcast_end)
    if not playlist:
        return

    # 다운로드 상태 설정
    streamer.is_downloading = True
    try:
        # temp 폴더 생성 확인 (기존 shutil.rmtree는 제거하여 파일 유지)
        os.makedirs(TEMP_DIR, exist_ok=True)

        # 모든 곡 다운로드
        for song in playlist:
            video_id = song.get("video_id") or song["youtube_url"].split("=")[-1]
            file_path = os.path.join(TEMP_DIR, f"{video_id}.mp4")
            
            # 이미 파일이 있으면 다운로드 스킵
            if os.path.exists(file_path):
                song["local_file"] = os.path.abspath(file_path)
                continue

            success = await download_youtube_video(song["youtube_url"], file_path)
            if success:
                song["local_file"] = os.path.abspath(file_path)
            else:
                print(f"[Scheduler] 다운로드 실패: {song['title']}")
        
        # 전역 변수나 상태로 플레이리스트 저장 (정각에 사용)
        streamer.pending_playlist = playlist
        print(f"[Scheduler] {len(playlist)}곡 준비 완료")

    finally:
        streamer.is_downloading = False
        await cleanup_temp_dir(playlist)


async def check_and_start_broadcast():
    
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    schedule = await get_schedule(today)
    if not schedule or current_time != schedule["start_time"][:5]:
        return

    if streamer.is_running:
        return

    print(f"[Scheduler] 방송 시작 시간: {current_time}")

    # 미리 준비된 플레이리스트 확인
    playlist = getattr(streamer, "pending_playlist", None)
    
    if not playlist:
        # 혹시나 미리 준비 안된 경우 (수동 시작 대비 등) 즉석 구성
        approved = await get_approved_requests()
        if not approved: return
        broadcast_start = now
        broadcast_end = datetime.strptime(f"{today} {schedule['end_time'][:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        playlist = build_optimal_playlist(approved, broadcast_start, broadcast_end)

    if not playlist:
        print("[Scheduler] 재생할 곡이 없습니다")
        return

    log_id = await create_broadcast_log(
        today, current_time, schedule["end_time"][:5],
        json.dumps([{"id": s["id"], "title": s["title"], "play_at": s["play_at"]} for s in playlist],
                   ensure_ascii=False)
    )

    # 방송 종료 시간 (datetime 객체)
    broadcast_end = datetime.strptime(f"{today} {schedule['end_time'][:5]}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)

    print(f"[Scheduler] 방송 시작 태스크 생성 (Log ID: {log_id})")
    
    # 별도 태스크로 실행하여 스케줄러가 블로킹되지 않도록 함
    asyncio.create_task(streamer.run_playlist(playlist, broadcast_end, log_id))


async def run_weekly_cleanup():
    print(f"[Cleanup] 주간 정리 시작 (설정: {CLEANUP_COUNT}곡)")
    deleted_count = await perform_weekly_cleanup(CLEANUP_COUNT)
    print(f"[Cleanup] 주간 정리 완료: {deleted_count}곡 삭제됨")


def start_scheduler():
    
    if not scheduler.running:
        
        # 1분마다 방송 시작 여부 체크
        scheduler.add_job(
            check_and_start_broadcast,
            CronTrigger(second=0),
            id="broadcast_checker",
            replace_existing=True
        )

        # 1분마다 방송 1분 전인지 체크하여 다운로드
        scheduler.add_job(
            prepare_broadcast_files,
            CronTrigger(second=0),
            id="broadcast_preparer",
            replace_existing=True
        )

        
        scheduler.add_job(
            run_weekly_cleanup,
            CronTrigger(day_of_week=CLEANUP_DAY, hour=CLEANUP_HOUR, minute=0),
            id="weekly_cleanup",
            replace_existing=True
        )

        scheduler.start()
        print(f"[Scheduler] 스케줄러 시작됨 (다운로드/방송 감지 가동 중)")


def stop_scheduler():
    
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Scheduler] 스케줄러 종료됨")
