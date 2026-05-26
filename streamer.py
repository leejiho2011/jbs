
import asyncio
import subprocess
import json
import os
import platform
import signal
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from config import STREAM_QUALITY

KST = ZoneInfo("Asia/Seoul")


class StreamerManager:

    def __init__(self):
        self.current_song = None
        self.active_playlist = []
        self.mpv_process = None
        self.stop_event = asyncio.Event()
        self.is_downloading = False

        self.is_windows = platform.system() == "Windows"
        if self.is_windows:
            self.ipc_path = r"\\.\pipe\mpvsocket"
        else:
            self.ipc_path = "/tmp/mpvsocket"

    @property
    def is_running(self):
        """mpv 프로세스가 살아있는지 확인"""
        return self.mpv_process is not None and self.mpv_process.poll() is None

    def _cleanup_old_mpv(self):
        """기존 mpv 프로세스 강제 종료"""
        if self.mpv_process:
            try:
                if self.is_windows:
                    self.mpv_process.kill()
                else:
                    os.killpg(os.getpgid(self.mpv_process.pid), signal.SIGKILL)
            except: pass
        
        if not self.is_windows and os.path.exists(self.ipc_path):
            try: os.remove(self.ipc_path)
            except: pass

    def start_mpv(self):
        """mpv 실행"""
        self._cleanup_old_mpv()

        # 시스템별 mpv 경로 설정
        if self.is_windows:
            # mpv 폴더 내의 mpv.exe 경로 (절대 경로로 변환)
            mpv_path = os.path.abspath(os.path.join("mpv", "mpv.exe"))
            # 만약 해당 경로에 파일이 없으면 시스템 환경변수의 mpv 사용
            if not os.path.exists(mpv_path):
                mpv_path = "mpv"
        else:
            mpv_path = "mpv"

        cmd = [
            mpv_path,
            "--fs=yes",
            "--idle=yes",
            "--force-window=yes",
            "--keep-open=no", # 곡 종료 시 즉시 Idle 상태로 전환되도록 함
            "--pause=no",
            "--cache=yes",
            "--cache-secs=30",
            "--demuxer-max-bytes=150M",
            "--geometry=1280x720+0+0",
            f"--input-ipc-server={self.ipc_path}",
            "--really-quiet"
        ]

        try:
            self.mpv_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=None if self.is_windows else os.setsid
            )
            print(f"[Streamer] mpv 프로세스 시작됨 ({mpv_path})")
            return True
        except Exception as e:
            print("[Streamer] mpv 실행 실패:", e)
            return False

    async def send_command(self, command):
        try:
            if self.is_windows:
                for _ in range(5):
                    try:
                        with open(self.ipc_path, "r+", encoding="utf-8") as pipe:
                            pipe.write(json.dumps(command) + "\n")
                            pipe.flush()
                            return json.loads(pipe.readline())
                    except: await asyncio.sleep(0.1)
                return None
            else:
                reader, writer = await asyncio.open_unix_connection(self.ipc_path)
                writer.write((json.dumps(command) + "\n").encode())
                await writer.drain()
                response = await reader.readline()
                writer.close()
                await writer.wait_closed()
                return json.loads(response.decode()) if response else None
        except: return None

    async def load_video(self, video_url):
        """파일 로드 및 재생"""
        for _ in range(50):
            if self.is_windows or os.path.exists(self.ipc_path): break
            await asyncio.sleep(0.1)

        await self.send_command({
            "command": ["loadfile", video_url, "replace"]
        })
        await self.send_command({
            "command": ["set_property", "pause", False]
        })

    async def wait_until_finished(self, end_time):
        """mpv의 상태(Idle -> Playing -> Idle) 변화를 감시하여 곡 종료를 판별"""
        
        # 1. 재생 시작 확인 (Idle 상태가 해제될 때까지 대기)
        started = False
        for _ in range(60): # 최대 6초
            if self.stop_event.is_set() or not self.is_running: return
            res = await self.send_command({"command": ["get_property", "idle-active"]})
            # idle-active가 False이면 무언가 재생을 시작했다는 의미
            if res and res.get("data") == False:
                started = True
                break
            await asyncio.sleep(0.1)
        
        if not started:
            print("[Streamer] 재생 시작 감지 실패 (Timeout)")
            return

        # 2. [핵심] 재생 초기 유예 기간 (2.5초)
        # 곡이 막 시작된 후 로딩/버퍼링으로 인해 일시적으로 idle이 되는 것을 완전히 무시함
        await asyncio.sleep(2.5)

        # 3. 재생 종료 대기 (다시 Idle 상태가 되거나 EOF에 도달할 때까지)
        while True:
            if self.stop_event.is_set() or not self.is_running: break
            if datetime.now(KST) >= end_time: break

            # mpv 상태 확인
            idle_res = await self.send_command({"command": ["get_property", "idle-active"]})
            eof_res = await self.send_command({"command": ["get_property", "eof-reached"]})
            
            # 다시 Idle 상태가 되었거나, 파일 끝에 도달했으면 곡 종료 시도
            if (idle_res and idle_res.get("data") == True) or (eof_res and eof_res.get("data") == True):
                # 일시적인 멈춤인지 실제 종료인지 0.5초 후 재확인
                await asyncio.sleep(0.5)
                final_res = await self.send_command({"command": ["get_property", "idle-active"]})
                if final_res and final_res.get("data") == True:
                    print("[Streamer] 곡 재생 완료 감지")
                    break

            await asyncio.sleep(0.2)

    async def run_playlist(self, playlist, end_time, log_id):
        from database import update_broadcast_log
        self.active_playlist = playlist
        self.stop_event.clear()

        try:
            if not self.start_mpv(): return
            
            # 준비 화면 표시
            start_img = "img/start.png"
            if os.path.exists(start_img):
                await self.load_video(os.path.abspath(start_img))
            elif os.path.exists("static/loading.png"):
                await self.load_video(os.path.abspath("static/loading.png"))
            await asyncio.sleep(2)

            for i, song in enumerate(playlist):
                if self.stop_event.is_set() or not self.is_running: break
                if datetime.now(KST) >= end_time: break

                self.current_song = song
                target = song.get("local_file") or await asyncio.to_thread(self.get_stream_url, song["youtube_url"])

                if not target:
                    print(f"[Streamer] 소스 없음 스킵: {song['title']}")
                    continue

                print(f"[Streamer] 재생 시작 ({i+1}/{len(playlist)}): {song['title']}")
                await self.load_video(target)
                
                # 핵심: mpv 상태를 보고 다음 곡으로 넘어갈지 판단
                await self.wait_until_finished(end_time)

                from database import increment_play_count
                asyncio.create_task(increment_play_count(song["id"]))

            # 모든 곡 종료 후 잠시 대기
            await asyncio.sleep(2)

        finally:
            self.stop_broadcast()
            self.active_playlist = []
            await update_broadcast_log(log_id, "finished", datetime.now(KST).strftime("%H:%M:%S"))

    def stop_broadcast(self):
        """방송 중지 및 프로세스 정리"""
        self.stop_event.set()
        self._cleanup_old_mpv()
        self.mpv_process = None
        self.current_song = None

    def get_stream_url(self, youtube_url) -> Optional[str]:
        from config import YTDLP_COOKIES
        cmd = ["yt-dlp", "-f", STREAM_QUALITY, "--get-url", "--no-playlist", "--force-ipv4"]
        if YTDLP_COOKIES: cmd += ["--cookies", YTDLP_COOKIES]
        cmd.append(youtube_url)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            return result.stdout.strip() if result.returncode == 0 else None
        except: return None

streamer = StreamerManager()
