# 🎵 음악방송 시스템

학교 음악방송을 위한 **음악 신청 → 어드민 관리 → FFmpeg 자동 송출** 통합 시스템

---

## 📐 시스템 구조

```
학생 (일반 사용자)                어드민
      │                              │
      ▼                              ▼
 [index.html]                 [admin.html]
 학번 + 유튜브 URL                JWT 로그인
      │                         ┌──┴──────────────┐
      ▼                         │                 │
 POST /api/request          음악 승인/거절     스케줄 설정
      │                         │                 │
      ▼                         ▼                 ▼
  [SQLite DB] ◄──────────── [FastAPI] ──────► [APScheduler]
                                                    │
                                         방송 시간 도달 시
                                                    ▼
                                          [yt-dlp] → URL 추출
                                                    │
                                                    ▼
                                          [FFmpeg] → 전체화면
                                                    │
                                                    ▼
                                               OBS 캡처
                                                    │
                                                    ▼
                                            유튜브/트위치 송출
```

---

## 🗂️ 파일 구조

```
music-broadcast/
├── main.py            # FastAPI 서버 (메인 엔트리포인트)
├── config.py          # 전체 설정
├── database.py        # SQLite DB 작업
├── auth.py            # JWT 인증 (어드민 전용)
├── youtube.py         # 유튜브 정보 조회 + 플레이리스트 최적화
├── streamer.py        # FFmpeg 스트리밍 컨트롤러
├── scheduler.py       # APScheduler (방송 자동 시작)
├── static/
│   ├── index.html     # 학생용 음악 신청 사이트
│   ├── admin.html     # 어드민 대시보드
│   └── background.jpg # 방송 배경 이미지 (직접 추가)
├── frp/
│   └── frpc.ini       # FRP 클라이언트 설정
├── data/
│   └── music.db       # SQLite 데이터베이스 (자동 생성)
├── .env.example       # 환경 변수 템플릿
├── requirements.txt   # Python 패키지
└── setup.sh           # 설치 스크립트
```

---

## ⚙️ 설치 방법

### 1단계: 시스템 요구사항

- **OS**: Ubuntu 20.04 / 22.04 (Linux 필수 - v4l2loopback)
- **Python**: 3.10 이상
- **패키지**: ffmpeg, v4l2loopback-dkms, yt-dlp

### 2단계: 자동 설치

```bash
chmod +x setup.sh
./setup.sh
```

### 3단계: 수동 설치 (선택)

```bash
# 가상환경
python3 -m venv venv && source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# ffmpeg
sudo apt install ffmpeg

# 가상 카메라 모듈
sudo apt install v4l2loopback-dkms
sudo modprobe v4l2loopback devices=1 video_nr=0 \
  card_label="MusicBroadcast" exclusive_caps=1
```

### 4단계: 환경 설정

```bash
cp .env.example .env
nano .env  # 아래 항목 반드시 수정!
```

**필수 수정 항목:**

| 항목 | 설명 |
|------|------|
| `JWT_SECRET_KEY` | 강력한 랜덤 문자열 (`python3 -c "import secrets; print(secrets.token_hex(32))"`) |
| `ADMIN_PASSWORD` | 어드민 비밀번호 |
| `VIRTUAL_CAMERA_DEVICE` | v4l2 디바이스 경로 (보통 `/dev/video0`) |

---

## 🚀 실행

```bash
# 1. 가상환경 활성화
source venv/bin/activate

# 2. 서버 실행
python main.py

# 3. (별도 터미널) FRP 실행 - 외부 접근용
./frp/frpc -c frp/frpc.ini
```

**접속:**
- 학생 사이트: `http://localhost:8000`
- 어드민: `http://localhost:8000/admin`
- 외부 접근: `http://YOUR_VPS_IP:8080` (FRP 설정 후)

---

## 🔐 보안 구조 (JWT)

```
어드민 로그인 과정:
  1. admin.html → POST /api/admin/login (ID/PW)
  2. 서버에서 bcrypt로 비밀번호 검증
  3. 검증 성공 → JWT 토큰 발급 (HS256, 12시간)
  4. 토큰은 sessionStorage에 저장 (탭 닫으면 삭제)

API 접근:
  모든 /api/admin/* 요청에 Authorization: Bearer <token> 헤더 필요
  → HTML/JS 코드만 봐서는 토큰 없이 어드민 API 전혀 접근 불가
  → 토큰은 서버의 JWT_SECRET_KEY로만 생성/검증 가능
```

---

## 📡 FRP 설정 (외부 접근)

### VPS (서버측) - frps.ini

```ini
[common]
bind_port = 7000
token = YOUR_STRONG_AUTH_TOKEN
vhost_http_port = 8080
```

```bash
# VPS에서 실행
./frps -c frps.ini
```

### 로컬 (클라이언트측) - frpc.ini

```ini
[common]
server_addr = YOUR_VPS_IP
server_port = 7000
token = YOUR_STRONG_AUTH_TOKEN

[music-web]
type = http
local_port = 8000
remote_port = 8080
```

---

## 🎬 OBS 연결

1. OBS → 소스 추가 → **비디오 캡처 장치**
2. 장치: `/dev/video0` (MusicBroadcast) 선택
3. 해상도: 1280×720, FPS: 30 설정

방송 시작 시간이 되면 FFmpeg이 자동으로 가상 카메라에 출력 → OBS가 자동으로 화면 캡처

---

## 🎵 음악방송 흐름

```
1. 학생이 학번 + 유튜브 링크 신청
2. 어드민이 승인 (admin.html)
3. 어드민이 방송 스케줄 설정 (날짜, 시작/종료 시간)
4. APScheduler가 매분 시간 확인
5. 시작 시간 → yt-dlp로 최적 플레이리스트 생성
   (방송 길이에 맞게 곡 선택, 버퍼 시간 고려)
6. FFmpeg로 유튜브 오디오 + 배경 이미지 합성 → 디스플레이에 전체화면으로 띄우기
7. OBS가 프로그램 캡처 → 유튜브/트위치 등으로 라이브 송출
8. 방송 종료 시간 → 자동 중지, 로그 기록
```

---

## 🔧 문제 해결

### v4l2loopback 로드 실패
```bash
# dkms 재빌드
sudo dkms build v4l2loopback/0.12.7
sudo modprobe v4l2loopback
```

### yt-dlp 오류 (봇 차단)
```bash
# 쿠키 사용
yt-dlp --cookies-from-browser chrome ...
# .env에서 YTDLP_COOKIES=cookies.txt 설정
```

