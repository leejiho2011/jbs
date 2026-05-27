---
name: secure-chat
description: 대화 기록이나 데이터를 안전하게 암호화하고 복호화합니다. 사용자가 키를 제공하거나 키 생성을 요청할 때, 혹은 대화 기록의 보안이 필요할 때 사용합니다.
---

# Secure Chat Skill

이 스킬은 `cryptography` 라이브러리를 사용하여 대화 기록이나 특정 데이터를 AES 방식으로 암호화하고 복호화하는 기능을 제공합니다.

## 주요 기능

1. **키 생성 (`keygen`)**: 암호화에 사용할 새로운 비밀 키를 생성합니다.
2. **데이터 암호화 (`encrypt`)**: 제공된 키를 사용하여 데이터를 암호화하고 파일로 저장합니다.
3. **데이터 복호화 (`decrypt`)**: 암호화된 파일을 키를 사용하여 복호화합니다.

## 사용 방법

### 1. 키 생성
사용자가 새로운 암호화 키를 원할 때 사용합니다.
```bash
python secure-chat/scripts/secure_chat.py keygen
```

### 2. 데이터 암호화
사용자가 현재 대화 기록이나 특정 데이터를 암호화해달라고 요청할 때 사용합니다. 데이터를 JSON 리스트 형식으로 구성하여 전달해야 합니다.
```bash
python secure-chat/scripts/secure_chat.py encrypt -k "<KEY>" -d '<JSON_DATA>'
```
*예시: `[{"role": "user", "text": "안녕"}, {"role": "model", "text": "안녕하세요"}]`*

### 3. 데이터 복호화
사용자가 키를 제공하며 암호화된 파일(`gemini.yml.enc`)의 내용을 확인하고 싶어할 때 사용합니다.
```bash
python secure-chat/scripts/secure_chat.py decrypt -k "<KEY>"
```

## 주의 사항
- 복호화할 때 키가 틀리면 실패 메시지가 출력됩니다.
- 암호화된 파일은 기본적으로 `gemini.yml.enc`라는 이름으로 저장됩니다.
- 사용자가 키를 잃어버리면 복구가 불가능함을 안내해야 합니다.
