# 🎵 JBS (Junior Broadcasting System)
학교 음악방송 신청 및 자동 송출 시스템

JBS는 학교 점심시간이나 쉬는 시간의 음악방송을 자동화하기 위해 설계된 시스템입니다. 학생들이 유튜브 URL을 통해 음악을 신청하면, 관리자가 승인한 곡들을 정해진 스케줄에 맞춰 **1080p 고화질**로 자동 송출합니다.

---

## ✨ 주요 기능

*   **고화질 송출**: 유튜브 스트리밍의 불안정성을 해결하기 위해 방송 1분 전 곡을 미리 다운로드하여 mp4 로컬 파일로 끊김 없이 재생합니다.
*   **스마트 플레이리스트**: 신청 곡의 평점(별점)과 재생 횟수를 계산하여 자동으로 최적의 플레이리스트를 생성합니다.
*   **실시간 mpv 제어**: mpv 플레이어의 IPC(Inter-Process Communication)를 사용하여 곡 전환 지연을 2초 이내로 최소화합니다.
*   **관리자 대시보드**: 신청 곡 승인/거절, 방송 수동 시작/중지, 학생 차단 관리 등을 한눈에 확인하고 제어할 수 있습니다.
*   **보안 및 로깅**: 모든 관리자 활동(로그인, 승인, 차단 등)을 `ad.log`에 접속 IP와 함께 상세히 기록합니다.
*   **자동 최적화**: `temp` 폴더에 동영상이 7개 이상 쌓이면 현재 방송에 필요 없는 파일을 자동으로 삭제하여 용량을 관리합니다.

---

## 🛠 설치 및 준비 사항

### 1. 필수 소프트웨어
*   **Python 3.10 이상**: 시스템의 메인 엔진입니다.
*   **mpv**: 영상 재생을 담당하는 플레이어입니다.
    *   **Windows**: 프로젝트 루트의 `mpv/` 폴더 내에 `mpv.exe`가 있어야 합니다.
    *   **Mac/Linux**: `brew install mpv` 또는 `sudo apt install mpv`로 설치가 필요합니다.
*   **yt-dlp**: 유튜브 영상 추출 및 다운로드를 담당합니다. (`pip`로 자동 설치됨)

### 2. Python 가상환경(venv) 설정
시스템 의존성을 독립적으로 관리하기 위해 가상환경 사용을 권장합니다.

```bash
# 1. 가상환경 생성
python -m venv venv

# 2. 가상환경 활성화
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 3. 필요한 패키지 설치
pip install -r requirements.txt
```

---

## ⚙️ 환경 설정 (.env)

보안과 화질 설정을 위해 프로젝트 루트에 `.env` 파일을 생성하고 다음 내용을 설정하십시오. (설정하지 않을 경우 `config.py`의 기본값이 사용됩니다.)

```env
# 관리자 계정 설정
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password

# 보안 설정 (반드시 복잡한 문자열로 변경하세요)
JWT_SECRET_KEY=y0ur_v3ry_s3cur3_k3y_h3r3

# 방송 화질 설정 (기본 1080p)
# 720p로 낮추려면: bestvideo[height<=720]+bestaudio/best
STREAM_QUALITY=bestvideo[height<=1080]+bestaudio/best[height<=1080]/best

# 주간 정리 스케줄 (매주 월요일 새벽 4시에 별점 낮은 곡 삭제)
CLEANUP_DAY=mon
CLEANUP_HOUR=4
CLEANUP_COUNT=5
```

---

## 🚀 실행 방법

### 서버 가동
가상환경이 활성화된 상태에서 아래 명령어를 입력합니다.

```bash
python main.py
```
*   **사용자 페이지**: `http://localhost:8000` (음악 신청)
*   **관리자 페이지**: `http://localhost:8000/admin` (방송 제어)

### 방송 가이드
1.  **방송 1분 전**: 시스템이 자동으로 승인된 곡들을 `temp/` 폴더에 다운로드하기 시작합니다.
2.  **방송 시작 시간**: `mpv` 창이 열리며 준비 화면(`img/start.png`)이 나타난 후 음악이 재생됩니다.
3.  **수동 시작**: 관리자 페이지에서 '방송 시작' 버튼을 누르면 즉시 다운로드가 진행되고 방송이 시작됩니다.

---

## 📁 디렉토리 구조
*   `main.py`: FastAPI 서버 및 API 엔드포인트
*   `streamer.py`: mpv 플레이어 제어 및 상태 감시
*   `scheduler.py`: 정기 다운로드 및 방송 시작 스케줄러
*   `youtube.py`: 유튜브 정보 추출 및 다운로드를 담당
*   `database.py`: SQLite DB 관리
*   `static/`: 웹 프론트엔드 파일 (HTML, CSS, JS)
*   `temp/`: 방송용 임시 영상 저장 폴더
*   `ad.log`: 관리자 활동 로그 파일

---

## ⚠️ 보안 주의 사항
*   `.env` 파일과 `data/music.db` 파일은 절대 외부에 공유하지 마십시오.
*   공개 서버에 배포 시 `frpc` 설정의 토큰을 반드시 변경하십시오.
*   `ad.log`를 주기적으로 확인하여 비정상적인 접속 시도가 있는지 모니터링하십시오.

---
**Copyright 2026. 이지호**