
import json
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from database import (
    get_schedule, get_approved_requests,
    create_broadcast_log, update_broadcast_log
)
from youtube import build_optimal_playlist
from streamer import streamer


scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
KST = ZoneInfo("Asia/Seoul")

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
_app_ref = None  


async def check_and_start_broadcast():
    
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    schedule = await get_schedule(today)
    if not schedule:
        return

    start_time = schedule["start_time"][:5]  
    end_time_str = schedule["end_time"][:5]

    
    if current_time != start_time:
        return

    if streamer.is_running:
        print(f"[Scheduler] 이미 방송 중, 스킵")
        return

    print(f"[Scheduler] 방송 시작 시간 도달: {start_time} ~ {end_time_str}")

    
    approved = await get_approved_requests()
    if not approved:
        print("[Scheduler] 승인된 곡이 없습니다")
        return

    
    broadcast_start = datetime.strptime(f"{today} {start_time}", "%Y-%m-%d %H:%M")
    broadcast_end   = datetime.strptime(f"{today} {end_time_str}", "%Y-%m-%d %H:%M")

    if broadcast_end <= broadcast_start:
        
        broadcast_end += timedelta(days=1)

    
    playlist = build_optimal_playlist(approved, broadcast_start, broadcast_end)

    if not playlist:
        print("[Scheduler] 플레이리스트 생성 실패 (곡 길이 정보 없음)")
        return

    
    log_id = await create_broadcast_log(
        today, start_time, end_time_str,
        json.dumps([{"id": s["id"], "title": s["title"], "play_at": s["play_at"]} for s in playlist],
                   ensure_ascii=False)
    )

    print(f"[Scheduler] 플레이리스트 {len(playlist)}곡:")
    for s in playlist:
        print(f"  [{s['order']}] {s['play_at']} - {s['title']} ({s['duration_str']})")

    
    streamer.broadcast_task = asyncio.create_task(
        streamer.run_playlist(playlist, broadcast_end, log_id)
    )


def start_scheduler():
    
    if not scheduler.running:
        
        scheduler.add_job(
            check_and_start_broadcast,
            CronTrigger(second=0),
            id="broadcast_checker",
            replace_existing=True
        )
        scheduler.start()
        print("[Scheduler] 스케줄러 시작됨 (매분 방송 시간 확인)")


def stop_scheduler():
    
    if scheduler.running:
        scheduler.shutdown(wait=False)
        print("[Scheduler] 스케줄러 종료됨")
