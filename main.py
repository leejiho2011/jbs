import json
import asyncio
import subprocess
import platform
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import JWT_EXPIRE_HOURS, TEMP_DIR
import shutil
from database import (
    init_db, create_music_request, get_all_requests, get_approved_requests,
    update_request_status, delete_request, upsert_schedule,
    get_all_schedules, get_schedule, get_broadcast_logs,
    create_broadcast_log, update_broadcast_log,
    get_played_history, update_song_rating,
    is_student_blocked, block_student, unblock_student, get_blocked_students,
    get_request_by_id
)

def log_admin_action(ip: str, action: str, details: str):
    """관리자 활동 로그 기록 (ad.log)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{ip}] {action}: {details}\n"
    with open("ad.log", "a", encoding="utf-8") as f:
        f.write(log_entry)
from auth import authenticate_admin, create_access_token, get_current_admin
from youtube import is_valid_youtube_url, normalize_youtube_url, fetch_youtube_info, build_optimal_playlist, download_youtube_video
from streamer import streamer
from scheduler import start_scheduler, stop_scheduler

frp_process = None

def start_frp():
    global frp_process
    system = platform.system()
    binary = "frpc.exe" if system == "Windows" else "./frpc"
    
    if system != "Windows":
        try:
            os.chmod(binary, 0o755)
        except:
            pass
        
    try:
        frp_process = subprocess.Popen(
            [binary, "-c", "frpc.toml"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print(f"Started FRP client: {binary}")
    except Exception as e:
        print(f"Failed to start FRP client: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    start_frp()
    yield
    stop_scheduler()
    streamer.stop_broadcast()
    if frp_process:
        frp_process.terminate()
        print("Stopped FRP client")

app = FastAPI(
    title="음악방송 시스템",
    description="학교 음악방송 신청 및 자동 송출 시스템",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None,   
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.get("/admin")
async def admin_page():
    return FileResponse("static/admin.html")

class MusicRequestBody(BaseModel):
    student_id: str
    youtube_url: str

@app.post("/api/request")
async def submit_music_request(body: MusicRequestBody):
    sid = body.student_id.strip()
    if not sid.isdigit() or len(sid) != 5:
        raise HTTPException(400, "학번은 5자리 숫자여야 합니다")

    grade = int(sid[0])
    class_num = int(sid[1:3])
    student_num = int(sid[3:5])

    if not (1 <= grade <= 3):
        raise HTTPException(400, "학년은 1~3학년만 가능합니다")
    if not (1 <= class_num <= 10):
        raise HTTPException(400, "반은 01~10반만 가능합니다")
    if not (1 <= student_num <= 35):
        raise HTTPException(400, "번호는 01~35번만 가능합니다")

    if await is_student_blocked(sid):
        raise HTTPException(403, "신청이 제한된 학번입니다")

    url = normalize_youtube_url(body.youtube_url.strip())
    if not is_valid_youtube_url(url):
        raise HTTPException(400, "유효한 유튜브 URL이 아닙니다")

    info = await fetch_youtube_info(url)
    if not info:
        raise HTTPException(400, "유튜브 영상 정보를 가져올 수 없습니다")

    if info["duration"] > 600:  
        raise HTTPException(400, f"10분 이하의 영상만 신청 가능합니다")

    req_id = await create_music_request(
        student_id=sid,
        youtube_url=url,
        title=info["title"],
        duration=info["duration"],
        thumbnail=info["thumbnail"]
    )

    return {
        "success": True,
        "id": req_id,
        "title": info["title"],
        "duration": info["duration"],
        "message": f"신청 완료!"
    }

@app.get("/api/status")
async def get_status():
    today = datetime.now().strftime("%Y-%m-%d")
    schedule = await get_schedule(today)

    return {
        "is_broadcasting": streamer.is_running,
        "current_song": streamer.current_song.get("title") if streamer.current_song else None,
        "schedule": {
            "start": schedule["start_time"] if schedule else None,
            "end": schedule["end_time"] if schedule else None,
        } if schedule else None
    }

@app.get("/api/history")
async def get_history():
    history = await get_played_history()
    return {"history": history}

class RateBody(BaseModel):
    id: int
    rating: int

@app.post("/api/rate")
async def rate_song(body: RateBody):
    if not (1 <= body.rating <= 5):
        raise HTTPException(400, "평점은 1에서 5 사이여야 합니다")
    
    await update_song_rating(body.id, body.rating)
    return {"success": True, "message": "평점이 반영되었습니다"}

class LoginBody(BaseModel):
    username: str
    password: str

@app.post("/api/admin/login")
async def admin_login(body: LoginBody, request: Request):
    client_ip = request.client.host
    if not authenticate_admin(body.username, body.password):
        log_admin_action(client_ip, "LOGIN_FAILED", f"User: {body.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 틀렸습니다"
        )

    token = create_access_token(
        {"sub": body.username},
        timedelta(hours=JWT_EXPIRE_HOURS)
    )
    log_admin_action(client_ip, "LOGIN_SUCCESS", f"User: {body.username}")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRE_HOURS * 3600
    }

@app.get("/api/admin/requests")
async def get_requests(
    status_filter: Optional[str] = None,
    _: dict = Depends(get_current_admin)
):
    requests = await get_all_requests(status_filter)
    return {"requests": requests, "total": len(requests)}

@app.put("/api/admin/approve/{request_id}")
async def approve_request(
    request_id: int,
    request: Request,
    _: dict = Depends(get_current_admin)
):
    song = await get_request_by_id(request_id)
    title = song["title"] if song else "Unknown"
    await update_request_status(request_id, "approved")
    log_admin_action(request.client.host, "APPROVE_MUSIC", f"ID: {request_id}, Title: {title}")
    return {"success": True, "message": "승인 완료"}

@app.put("/api/admin/reject/{request_id}")
async def reject_request(
    request_id: int,
    request: Request,
    _: dict = Depends(get_current_admin)
):
    song = await get_request_by_id(request_id)
    title = song["title"] if song else "Unknown"
    await update_request_status(request_id, "rejected")
    log_admin_action(request.client.host, "REJECT_MUSIC", f"ID: {request_id}, Title: {title}")
    return {"success": True, "message": "거절 완료"}

@app.delete("/api/admin/delete/{request_id}")
async def delete_request_endpoint(
    request_id: int,
    request: Request,
    _: dict = Depends(get_current_admin)
):
    song = await get_request_by_id(request_id)
    title = song["title"] if song else "Unknown"
    await delete_request(request_id)
    log_admin_action(request.client.host, "DELETE_REQUEST", f"ID: {request_id}, Title: {title}")
    return {"success": True, "message": "삭제 완료"}

class ScheduleBody(BaseModel):
    date: str         
    start_time: str   
    end_time: str     

@app.post("/api/admin/schedule")
async def set_schedule(
    body: ScheduleBody,
    _: dict = Depends(get_current_admin)
):
    try:
        datetime.strptime(body.date, "%Y-%m-%d")
        datetime.strptime(body.start_time, "%H:%M")
        datetime.strptime(body.end_time, "%H:%M")
    except ValueError:
        raise HTTPException(400, "날짜/시간 형식 오류")

    result = await upsert_schedule(body.date, body.start_time, body.end_time)
    return {"success": True, "schedule": result}

@app.get("/api/admin/schedules")
async def get_schedules(_: dict = Depends(get_current_admin)):
    schedules = await get_all_schedules()
    return {"schedules": schedules}

@app.get("/api/admin/broadcast/status")
async def broadcast_status(_: dict = Depends(get_current_admin)):
    from streamer import KST
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    schedule = await get_schedule(today)
    approved = await get_approved_requests()

    playlist_preview = []
    if streamer.is_running and streamer.active_playlist:
        playlist_preview = streamer.active_playlist
    elif schedule:
        try:
            # 시간 형식 유연하게 처리 (HH:MM 또는 HH:MM:SS)
            s_time = schedule['start_time'][:5]
            e_time = schedule['end_time'][:5]
            start_dt = datetime.strptime(f"{today} {s_time}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            end_dt   = datetime.strptime(f"{today} {e_time}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
            
            if end_dt > start_dt:
                playlist_preview = build_optimal_playlist(approved, start_dt, end_dt)
        except Exception as e:
            print(f"[Status API] 스케줄 파싱 오류: {e}")

    return {
        "is_running": streamer.is_running,
        "is_downloading": getattr(streamer, "is_downloading", False),
        "current_song": streamer.current_song,
        "today_schedule": schedule,
        "approved_count": len(approved),
        "playlist_preview": playlist_preview,
    }

@app.post("/api/admin/broadcast/start")
async def start_broadcast_manual(request: Request, _: dict = Depends(get_current_admin)):
    from streamer import KST
    if streamer.is_running:
        raise HTTPException(400, "이미 방송 중입니다")

    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    schedule = await get_schedule(today)
    
    if not schedule:
        raise HTTPException(400, "오늘 방송 스케줄이 없습니다")

    approved = await get_approved_requests()
    if not approved:
        raise HTTPException(400, "승인된 곡이 없습니다")

    start_dt = now
    try:
        end_dt = datetime.strptime(f"{today} {schedule['end_time']}", "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except Exception:
        raise HTTPException(400, "스케줄 종료 시간 형식이 잘못되었습니다")

    if end_dt <= now:
        raise HTTPException(400, "방송 종료 시간이 이미 지났습니다")

    playlist = build_optimal_playlist(approved, start_dt, end_dt)
    if not playlist:
        raise HTTPException(400, "플레이리스트를 만들 수 없습니다 (곡 길이가 부족할 수 있음)")

    # 다운로드 시작 상태 설정
    streamer.is_downloading = True
    try:
        # temp 폴더 정리 및 모든 곡 다운로드
        if os.path.exists(TEMP_DIR):
            try:
                shutil.rmtree(TEMP_DIR)
            except:
                pass
        os.makedirs(TEMP_DIR, exist_ok=True)

        print(f"[Manual Start] {len(playlist)}곡 다운로드 시작...")
        for song in playlist:
            video_id = song.get("video_id") or song["youtube_url"].split("=")[-1]
            file_path = os.path.join(TEMP_DIR, f"{video_id}.mp4")
            success = await download_youtube_video(song["youtube_url"], file_path)
            if success:
                song["local_file"] = os.path.abspath(file_path)
    finally:
        # 다운로드 종료 상태 설정
        streamer.is_downloading = False

    log_id = await create_broadcast_log(
        today, now.strftime("%H:%M"),
        schedule["end_time"],
        json.dumps([{"title": s["title"]} for s in playlist], ensure_ascii=False)
    )

    log_admin_action(request.client.host, "MANUAL_BROADCAST_START", f"Log ID: {log_id}, Songs: {len(playlist)}")

    streamer.broadcast_task = asyncio.create_task(
        streamer.run_playlist(playlist, end_dt, log_id)
    )

    return {
        "success": True,
        "message": f"다운로드 완료 및 방송 시작!",
        "playlist": [{"title": s["title"], "play_at": s["play_at"]} for s in playlist]
    }

@app.post("/api/admin/broadcast/stop")
async def stop_broadcast(_: dict = Depends(get_current_admin)):
    if not streamer.is_running:
        raise HTTPException(400, "방송 중이 아닙니다")
    streamer.stop_broadcast()
    return {"success": True, "message": "방송을 중지했습니다"}

@app.get("/api/admin/logs")
async def get_logs(_: dict = Depends(get_current_admin)):
    logs = await get_broadcast_logs()
    return {"logs": logs}

@app.get("/api/admin/blocked")
async def get_blocked_list(_: dict = Depends(get_current_admin)):
    blocked = await get_blocked_students()
    return {"blocked": blocked}

class BlockBody(BaseModel):
    student_id: str
    reason: Optional[str] = ""

@app.post("/api/admin/block")
async def block_student_endpoint(body: BlockBody, request: Request, _: dict = Depends(get_current_admin)):
    await block_student(body.student_id, body.reason)
    log_admin_action(request.client.host, "BLOCK_STUDENT", f"Student ID: {body.student_id}, Reason: {body.reason}")
    return {"success": True, "message": f"차단되었습니다"}

@app.delete("/api/admin/unblock/{student_id}")
async def unblock_student_endpoint(student_id: str, request: Request, _: dict = Depends(get_current_admin)):
    await unblock_student(student_id)
    log_admin_action(request.client.host, "UNBLOCK_STUDENT", f"Student ID: {student_id}")
    return {"success": True, "message": f"해제되었습니다"}

if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False, log_level="info")
