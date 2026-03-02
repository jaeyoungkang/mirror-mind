# OpenClaw Docker + Discord 설치 가이드

실제 설치 과정에서 겪은 시행착오를 포함한 가이드. (2026-03-02, OpenClaw 2026.3.1)

---

## 1. Docker 설치

```bash
git clone https://github.com/openclaw/openclaw.git
cd openclaw
./docker-setup.sh
```

### onboarding 선택지
- Gateway: **Local**
- Model/auth provider: 원하는 프로바이더 선택
- Channel: **Discord (Bot API)**

### 시행착오: OAuth 인증
- Docker 컨테이너가 "remote/VPS environment"로 감지되어 수동 OAuth 플로우로 빠진다
- 브라우저에서 OAuth URL 열고 → 로그인 → 리다이렉트된 URL 복사 (페이지가 안 열려도 주소창 URL 복사) → 터미널에 붙여넣기
- **더 간단한 방법: API 키 방식 선택** (OAuth보다 훨씬 수월)

---

## 2. Discord 봇 설정

### 2-1. 봇 생성
1. [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**
2. 왼쪽 **Bot** 탭 → **Reset Token** → 토큰 복사

### 2-2. Privileged Gateway Intents 활성화 (필수!)
Bot 탭 → **Privileged Gateway Intents** 섹션에서 3개 모두 ON:
- **Presence Intent**
- **Server Members Intent**
- **Message Content Intent** ← 이거 안 켜면 `WebSocket code 4014`로 연결 끊김

### 2-3. 서버에 봇 초대
1. **OAuth2 → URL Generator** → Scopes에서 `bot` 체크
2. Bot Permissions: **Send Messages**, **Read Message History** 체크
3. 생성된 URL → 브라우저에서 열고 → 서버 선택 → 초대

### 시행착오: 봇 토큰 형식
- onboarding에서 입력한 토큰이 hex로 저장되는 경우가 있다
- 실제 Discord 봇 토큰은 `MTQ3Nzg0...` 같은 Base64 형태여야 한다
- `openclaw.json`의 `channels.discord.token`을 직접 확인/수정

---

## 3. openclaw.json 설정

파일 위치: `~/.openclaw/openclaw.json`

### 3-1. 채널 정책

**open 모드** (모든 채널에서 반응, 테스트용):
```json
"channels": {
  "discord": {
    "groupPolicy": "open",
    "guilds": {
      "서버ID": {
        "requireMention": false
      }
    }
  }
}
```

**allowlist 모드** (특정 채널만):
```json
"channels": {
  "discord": {
    "groupPolicy": "allowlist",
    "guilds": {
      "서버ID": {
        "requireMention": true,
        "channels": {
          "채널ID": { "allow": true }
        }
      }
    }
  }
}
```

### 시행착오: 채널 설정 키 이름
- ~~`allowChannels`~~ → 올바른 키는 `channels`
- `guilds`가 비어있으면 (`{}`) 채널이 `unresolved` 상태로 메시지 무시
- `requireMention: true`이면 반드시 `@봇이름`으로 **실제 멘션** 해야 함 (텍스트로 `@봇이름` 타이핑하면 안 됨, 자동완성에서 선택해야 함)

### 3-2. Gateway (Docker 환경)
Docker에서 Control UI 관련 에러가 나면 추가:
```json
"gateway": {
  "controlUi": {
    "dangerouslyAllowHostHeaderOriginFallback": true
  }
}
```

### ID 확인 방법
- 디스코드 설정 → 고급 → **개발자 모드** ON
- 서버 아이콘 우클릭 → 서버 ID 복사
- 채널 우클릭 → 채널 ID 복사

---

## 4. 페어링 (Pairing)

봇에 DM을 보내면 페어링 코드가 표시된다:
```
Pairing code: FJXFPBCY
Ask the bot owner to approve with:
openclaw pairing approve discord FJXFPBCY
```

승인 명령:
```bash
docker exec openclaw-openclaw-gateway-1 openclaw pairing approve discord <코드>
```

### 시행착오: 페어링 초기화
- `docker compose down && up`으로 컨테이너를 재생성하면 **페어링이 초기화**될 수 있다
- 가능하면 `docker restart`를 사용 (컨테이너 재생성 안 함)
- 재생성 후에는 DM으로 다시 페어링 필요

---

## 5. AI 모델 + API 키 설정

### 5-1. docker-compose.yml에 환경변수 추가

```yaml
services:
  openclaw-gateway:
    environment:
      # Google Gemini
      GOOGLE_API_KEY: ${GOOGLE_API_KEY:-}
      GEMINI_API_KEY: ${GOOGLE_API_KEY:-}
      # 또는 OpenAI
      # OPENAI_API_KEY: ${OPENAI_API_KEY:-}
```

### 5-2. .env에 키 추가

파일: `~/openclaw/.env`
```
GOOGLE_API_KEY=AIzaSy...
GEMINI_API_KEY=AIzaSy...
```

### 5-3. openclaw.json 모델 설정

```json
"agents": {
  "defaults": {
    "model": {
      "primary": "google/gemini-3-flash-preview"
    },
    "models": {
      "google/gemini-3-flash-preview": {}
    }
  }
}
```

### 5-4. auth-profiles.json (Google Gemini 필수!)

파일: `~/.openclaw/agents/main/agent/auth-profiles.json`

```json
{
  "version": 1,
  "profiles": {
    "google": {
      "provider": "google",
      "type": "api_key",
      "key": "실제_API_키"
    }
  }
}
```

디렉토리가 없으면 생성:
```bash
mkdir -p ~/.openclaw/agents/main/agent
```

### 시행착오: 프로바이더별 인증 차이

| 프로바이더 | 환경변수만으로 동작? | auth-profiles.json 필요? |
|-----------|:---:|:---:|
| OpenAI | O | X |
| Google Gemini | X | **O (필수)** |

- OpenAI는 `OPENAI_API_KEY` 환경변수만 있으면 바로 동작
- Google Gemini는 환경변수 + `auth-profiles.json` **둘 다 필요**
- auth-profiles.json 형식이 버전마다 다름 — 2026.3.1 기준 위 형식이 정답

### 시행착오: auth-profiles.json 형식 삽질 기록

시도한 형식들과 결과:

| 형식 | 결과 |
|------|------|
| `{"google": {"apiKey": "..."}}` | `invalid_type` |
| `{"profiles": {"google:default": {"type": "api_key", "key": "..."}}}` | `missing_provider` |
| `{"profiles": {"google": {"auth": "api-key", "apiKey": "..."}}}` | `invalid_type` |
| `{"profiles": {"google": {"provider": "google", "type": "api_key", "key": "..."}}}` | **성공** |

핵심: `profiles` 래퍼 + `provider` + `type: "api_key"` + `key` — 4가지가 모두 있어야 함.

---

## 6. 반영 방법

### 설정 파일 수정만 한 경우 (openclaw.json, auth-profiles.json)
```bash
docker restart openclaw-openclaw-gateway-1
```

### 환경변수(.env) 또는 docker-compose.yml 수정한 경우
```bash
cd ~/openclaw
docker compose down && docker compose up -d openclaw-gateway
```
⚠️ `down && up`은 페어링이 초기화될 수 있으므로 주의

---

## 7. 디버깅

### 로그 확인
```bash
# Docker stdout 로그
docker logs openclaw-openclaw-gateway-1 --tail 20

# 컨테이너 내부 상세 로그
docker exec openclaw-openclaw-gateway-1 cat /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | tail -20

# 특정 키워드 필터
docker exec openclaw-openclaw-gateway-1 cat /tmp/openclaw/openclaw-$(date +%Y-%m-%d).log | grep -i "error\|auth\|discord\|invalid"
```

### 자주 만나는 에러

| 에러 | 원인 | 해결 |
|------|------|------|
| `WebSocket code 4014` | Message Content Intent 미활성화 | Discord Developer Portal → Bot → Intents ON |
| `401: Unauthorized` | 봇 토큰 잘못됨 | 토큰 재복사, Base64 형태 확인 |
| `channels unresolved` | 서버/채널 ID 불일치 또는 봇 미초대 | ID 재확인, 봇 서버 초대 |
| `no-mention` (skipping) | 멘션 없이 메시지 보냄 | `requireMention: false` 설정 또는 @멘션 사용 |
| `No API key found for provider` | auth-profiles.json 없거나 형식 오류 | 위 §5-4 형식 참고 |
| `API rate limit reached` | 무료 티어 API 한도 | 결제 정보 등록 또는 다른 키 사용 |
| `access not configured` + 페어링 코드 | 사용자 미승인 | `docker exec ... openclaw pairing approve discord <코드>` |
