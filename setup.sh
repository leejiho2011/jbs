#!/bin/bash
# ═══════════════════════════════════════════════════════
#  setup_mac.sh - macOS 초기 설치 및 실행 스크립트
#  사용법: chmod +x setup_mac.sh && ./setup_mac.sh
# ═══════════════════════════════════════════════════════

set -e  # 오류 시 중단
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  음악방송 시스템 설치 스크립트 (Mac) ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"

# ─── Homebrew 확인 및 설치 ──────────────────────────────
echo -e "\n${YELLOW}[1/4] Homebrew 패키지 관리자 확인...${NC}"
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Homebrew가 설치되어 있지 않습니다. 설치를 시작합니다...${NC}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Apple Silicon Mac 복사 경로 반영
    if [ -f /opt/homebrew/bin/brew ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [ -f /usr/local/bin/brew ]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
else
    echo -e "${GREEN}✓ Homebrew가 이미 설치되어 있습니다.${NC}"
fi

# ─── 시스템 패키지 설치 ─────────────────────────────────
echo -e "\n${YELLOW}[2/4] 시스템 패키지 설치 (Python, FFmpeg)...${NC}"
brew update
brew install python ffmpeg

# ※ macOS는 Linux용 v4l2loopback를 사용할 수 없으므로 가상 카메라 드라이버 설치는 건너뜁니다.
# 대신 최신 OBS Studio에 내장된 '가상 카메라 시작' 버튼을 활용하면 됩니다.

# ─── Python 가상환경 ─────────────────────────────────────
echo -e "\n${YELLOW}[3/4] Python 가상환경 설정...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip

# requirements.txt 파일 존재 확인 후 설치
if [ -f "requirements.txt" ]; then
  pip install -q -r requirements.txt
else
  echo -e "${YELLOW}⚠ requirements.txt 파일이 없어 패키지 설치를 건너뜁니다.${NC}"
fi

# yt-dlp 설치
pip install -q yt-dlp

# ─── 환경 설정 ──────────────────────────────────────────
echo -e "\n${YELLOW}[4/4] 환경 설정...${NC}"
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo -e "${GREEN}.env 파일 생성됨 - 설정값을 반드시 수정하세요!${NC}"
  else
    touch .env
    echo "JWT_SECRET=your-very-strong-random-secret-key-change-this-now" > .env
    echo -e "${YELLOW}.env.example이 없어 기본 .env 파일을 생성했습니다.${NC}"
  fi

  # 랜덤 JWT 키 자동 생성 (macOS sed 호환성 반영)
  JWT_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
  
  # macOS의 sed는 -i 옵션 뒤에 빈 문자열('')을 붙여야 원본 백업 없이 수정됩니다.
  sed -i '' "s/your-very-strong-random-secret-key-change-this-now/$JWT_KEY/" .env
  echo -e "${GREEN}JWT 키 자동 생성됨${NC}"
else
  echo ".env 파일이 이미 존재합니다"
fi

# 디렉터리 생성
mkdir -p data logs static

echo -e "\n${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Mac용 설치 완료!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}📋 다음 단계:${NC}"
echo "  1. .env 파일에서 ADMIN_PASSWORD 등 설정 변경"
echo "  2. frp/frpc.ini에서 VPS 정보 입력"
echo "     (주의: frp 폴더 내 frpc 바이너리가 Mac용 아키텍처(Intel/M1)인지 확인하세요.)"
echo "  3. static/background.jpg 배경 이미지 추가 (선택)"
echo ""
echo -e "${YELLOW}🚀 실행:${NC}"
echo "  source venv/bin/activate && python main.py"
echo ""
echo -e "${YELLOW}🌐 FRP 실행 (외부 접근):${NC}"
echo "  ./frp/frpc -c frp/frpc.ini &"
echo ""
echo -e "${YELLOW}📡 OBS Studio 설정 (Mac):${NC}"
echo "  1. Mac용 OBS Studio를 실행합니다."
echo "  2. 하단 제어(Controls) 창에서 '가상 카메라 시작(Start Virtual Camera)'을 클릭합니다."
echo "  3. 브라우저 소스나 소스 목록에서 음악방송 웹 UI 화면을 캡처하여 방송을 송출하세요."
echo ""