

import asyncio
import subprocess
import json
import os
import platform
from datetime import datetime
from typing import Optional


class StreamerManager:

    def __init__(self):

        self.is_running = False
        self.current_song = None
        self.active_playlist = []
        self.mpv_process = None
        self.stop_event = asyncio.Event()

        self.is_windows = platform.system() == "Windows"

        
        if self.is_windows:
            self.ipc_path = r"\\.\pipe\mpvsocket"
        else:
            self.ipc_path = "/tmp/mpvsocket"

    
    
    
    def start_mpv(self):

        
        if not self.is_windows:

            try:
                if os.path.exists(self.ipc_path):
                    os.remove(self.ipc_path)
            except:
                pass

        cmd = [
            "mpv",
            
            "--fs=yes",
            
            "--idle=yes",
            "--force-window=yes",
            "--keep-open=yes",

            
            "--pause=no",

            
            "--cache=yes",
            "--cache-secs=20",

            "--cache-pause=no",

            "--prefetch-playlist=yes",

            "--demuxer-max-bytes=50M",
            "--demuxer-max-back-bytes=10M",

            
            "--geometry=1280x720+0+0",

            
            f"--input-ipc-server={self.ipc_path}",

            "--really-quiet"
        ]

        try:

            self.mpv_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            return True

        except Exception as e:

            print("[Streamer] mpv 실행 실패:", e)
            return False

    
    
    
    async def send_command(self, command):

        try:

            
            
            
            if self.is_windows:

                with open(self.ipc_path, "r+", encoding="utf-8") as pipe:

                    pipe.write(json.dumps(command) + "\n")
                    pipe.flush()

                    response = pipe.readline()

                    if response:
                        return json.loads(response)

                    return None

            
            
            
            else:

                reader, writer = await asyncio.open_unix_connection(
                    self.ipc_path
                )

                writer.write(
                    (json.dumps(command) + "\n").encode()
                )

                await writer.drain()

                response = await reader.readline()

                writer.close()
                await writer.wait_closed()

                if response:
                    return json.loads(response.decode())

                return None

        except Exception as e:

            print("[Streamer] IPC 오류:", e)
            return None

    
    
    
    async def load_video(self, video_url):

        
        for _ in range(50):

            if os.path.exists(self.ipc_path):
                break

            await asyncio.sleep(0.1)

        
        await self.send_command({
            "command": [
                "loadfile",
                video_url,
                "replace"
            ]
        })

        
        await self.send_command({
            "command": [
                "set_property",
                "pause",
                False
            ]
        })

    
    
    
    async def wait_until_finished(self, end_time):

        last_time = -1
        same_count = 0

        
        for _ in range(100):
            if self.stop_event.is_set(): return
            result = await self.send_command({"command": ["get_property", "playback-time"]})
            if result and result.get("data", 0) > 0:
                break
            await asyncio.sleep(0.1)

        while True:

            if self.stop_event.is_set():
                break

            if datetime.now() >= end_time:
                break

            if self.mpv_process.poll() is not None:
                raise RuntimeError("mpv 종료됨")

            result = await self.send_command({
                "command": [
                    "get_property",
                    "playback-time"
                ]
            })

            current_time = None

            if result:
                current_time = result.get("data")

            
            if current_time is None:

                await asyncio.sleep(0.1)
                continue

            
            if current_time == last_time:

                same_count += 1

            else:

                same_count = 0

            last_time = current_time

            
            if same_count >= 100:
                break

            await asyncio.sleep(0.03)

    
    
    
    async def run_playlist(self, playlist, end_time, log_id):

        from database import update_broadcast_log

        self.is_running = True
        self.active_playlist = playlist
        self.stop_event.clear()

        try:

            if not self.start_mpv():
                return

            
            await asyncio.sleep(1)

            
            preload_task = asyncio.create_task(
                asyncio.to_thread(
                    self.get_stream_url,
                    playlist[0]["youtube_url"]
                )
            )

            
            
            

            for i, song in enumerate(playlist):

                if self.stop_event.is_set():
                    break

                if datetime.now() >= end_time:
                    break

                self.current_song = song

                
                stream_url = await preload_task

                if not stream_url:
                    continue

                
                if i + 1 < len(playlist):

                    next_song = playlist[i + 1]

                    preload_task = asyncio.create_task(
                        asyncio.to_thread(
                            self.get_stream_url,
                            next_song["youtube_url"]
                        )
                    )

                print(f"[Streamer] 재생 시작: {song['title']}")

                
                await self.load_video(stream_url)

                
                await self.wait_until_finished(end_time)

                
                from database import increment_play_count
                asyncio.create_task(increment_play_count(song["id"]))

        finally:

            self.stop_broadcast()
            self.active_playlist = []

            await update_broadcast_log(
                log_id,
                "finished",
                datetime.now().strftime("%H:%M:%S")
            )

    
    
    
    def stop_broadcast(self):

        self.stop_event.set()

        if self.mpv_process:

            self.mpv_process.terminate()

            try:
                self.mpv_process.wait(timeout=3)

            except subprocess.TimeoutExpired:
                self.mpv_process.kill()

        self.mpv_process = None
        self.current_song = None

        
        if not self.is_windows:

            try:
                if os.path.exists(self.ipc_path):
                    os.remove(self.ipc_path)
            except:
                pass

    
    
    
    def get_stream_url(self, youtube_url) -> Optional[str]:

        from config import YTDLP_COOKIES

        cmd = [
            "yt-dlp",

            "-f", "best",

            "--force-ipv4",

            "--get-url",

            "--no-playlist"
        ]

        if YTDLP_COOKIES:
            cmd += ["--cookies", YTDLP_COOKIES]

        cmd.append(youtube_url)

        try:

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:

                return result.stdout.strip().split("\n")[0]

            print(result.stderr)

            return None

        except Exception as e:

            print("[Streamer] yt-dlp 오류:", e)

            return None






streamer = StreamerManager()