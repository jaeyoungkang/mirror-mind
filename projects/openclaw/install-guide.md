# OpenClaw 설치 가이드 — 비숙련자 보조용

> 2026-03-01 설치 연습 기반 작성. 내일(3/2) AI 비숙련자 설치 세션 보조 도우미용.

---

## 사전 준비

참가자에게 미리 안내할 것:

- **텔레그램 앱** 설치 (스마트폰 또는 데스크톱, 둘 다 가능)
- **터미널** 사용법 기초 (맥: 터미널.app, 윈도우: WSL2)
- Node.js 22+ 설치 여부 확인: 터미널에서 `node --version` 입력

---

## 설치 절차

### 1단계: 설치 스크립트 실행

```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

**이 명령의 의미:**
- `curl` — 인터넷에서 파일을 다운로드하는 도구
- `-fsSL` — 에러 시 조용히 실패(-f), 진행 바 숨김(-s), 에러는 표시(-S), 리다이렉트 따라감(-L)
- `https://openclaw.ai/install.sh` — 설치 스크립트 주소
- `| bash` — 다운받은 스크립트를 바로 실행

**한 줄 설명:** "인터넷에서 설치 프로그램을 받아서 자동으로 실행하는 것"

**설치 스크립트가 자동으로 처리하는 것:**
1. Node.js 있는지 확인
2. OpenClaw CLI 설치
3. 온보딩 위저드 실행

---

### 2단계: 보안 경고 확인

```
◆ I understand this is personal-by-default and shared/multi-user use requires lock-down. Continue?
  ○ Yes / ● No
```

→ **Yes** 선택

**설명:** OpenClaw은 개인용(1인 사용) 기본 설정이다. 개인 PC에서 혼자 쓸 거니까 Yes.

---

### 3단계: 온보딩 모드

```
Onboarding mode
  ● QuickStart
  ○ Manual
```

→ **QuickStart** 선택

**설명:** 기본 설정으로 빠르게 설치. 세부 설정은 나중에 `openclaw configure`로 변경 가능. Manual은 항목별 직접 선택이라 비숙련자에게 불필요.

---

### 4단계: 모델/인증 선택

```
Model/auth provider
  ● OpenAI (Codex OAuth + API key)
  ○ Anthropic
  ...
```

→ **OpenAI** 선택 (GPT/ChatGPT 사용자인 경우)

**설명:** 참가자가 사용하는 AI 서비스 제공자를 선택. 대부분 OpenAI 계정이 있을 것이다.

---

### 5단계: 채널 선택

```
Select channel (QuickStart)
  ● Telegram (Bot API) (recommended · newcomer-friendly)
  ...
```

→ **Telegram** 선택

**설명:** OpenClaw이 연결될 메신저. Telegram이 비숙련자에게 가장 간단하다.

---

### 6단계: 텔레그램 봇 토큰 생성 (가장 많이 막히는 단계)

온보딩에서 토큰을 요구한다:

```
Telegram bot token
  1) Open Telegram and chat with @BotFather
  2) Run /newbot (or /mybots)
  3) Copy the token (looks like 123456:ABC...)
```

**구체적 절차:**

1. **텔레그램 앱** 열기 (스마트폰 또는 데스크톱)
2. 상단 검색바에서 **@BotFather** 검색
3. BotFather와 대화 시작
4. `/newbot` 입력
5. 봇 이름 입력 (표시 이름, 아무거나 가능. 예: "내 AI 봇")
6. 봇 사용자명 입력 (고유해야 함, `_bot`으로 끝나야 함. 예: `jaeyoung_test_bot`)
7. 토큰이 나온다: `123456:ABC-DEF...` 형태
8. **이 화면을 캡처해두기** — 토큰과 봇 사용자명이 모두 나옴
9. 토큰을 터미널 온보딩 화면에 붙여넣기

**비숙련자 주의사항:**
- BotFather는 봇을 **만드는** 곳이지, 만든 봇과 대화하는 곳이 아님
- 봇 사용자명은 전 세계에서 유일해야 하므로 이미 사용 중이면 다른 이름 시도
- 토큰은 비밀번호와 같으므로 공유하지 않기

---

### 7단계: 스킬 설치

```
◆ Install missing skill dependencies
  ◻ Skip for now
  ◻ 📝 apple-notes
  ...
```

→ **Skip for now** 선택

**설명:** 추가 기능(노트 연동, 이메일 등)인데 초기 설치에는 불필요. 나중에 `openclaw configure`로 개별 추가 가능. 선택지가 40개 넘어서 비숙련자에게 혼란을 줄 수 있으니 스킵이 최선.

---

### 8단계: API 키 설정 (전부 No)

```
◆ Set GOOGLE_PLACES_API_KEY for goplaces? → No
◆ Set NOTION_API_KEY for notion? → No
```

→ 나오는 API 키 질문은 모두 **No**

**설명:** 외부 서비스 연동용 API 키인데, 기본 사용에는 불필요.

---

### 9단계: Hooks 설정

```
◆ Enable hooks?
  ◻ Skip for now
  ...
```

→ **Skip for now** 선택

**설명:** 자동화 기능. 초기 설치에서는 불필요.

---

### 10단계: 설치 완료 + Health Check

설치가 끝나면 대시보드 URL이 표시된다:

```
Dashboard link: http://127.0.0.1:18789/#token=...
```

**Health check 실패가 나올 수 있다:**

```
Health check failed: gateway closed (1006 abnormal closure)
```

→ 당황하지 말 것. 게이트웨이가 아직 기동 중일 수 있다. 잠시 후 확인:

```bash
openclaw status
```

Gateway 항목에 **reachable**이 보이면 정상.

---

### 11단계: 보안 권한 수정

```bash
chmod 700 ~/.openclaw/credentials
```

**설명:** 인증 정보 디렉토리의 접근 권한을 본인만으로 제한.

---

### 12단계: OAuth 디렉토리 생성 (doctor 실행 시)

```bash
openclaw doctor
```

OAuth dir 생성 물어보면 → **Yes**

---

### 13단계: 텔레그램 봇에게 말 걸기

1. 텔레그램 앱에서 상단 검색바 탭
2. **6단계에서 만든 봇 사용자명** 검색 (예: `@jaeyoung_test_bot`)
3. 봇 선택 → 대화창 열림
4. **시작(Start)** 버튼 누르기
5. 아무 메시지나 보내기

**주의:** BotFather 대화창이 아니라, 내가 만든 봇의 대화창에서 해야 한다.

**봇을 못 찾겠으면:** BotFather 대화를 다시 열어서 `t.me/봇이름_bot` 링크를 찾아 누르기.

---

### 14단계: 페어링 승인

봇에게 메시지를 보내면 이런 응답이 온다:

```
OpenClaw: access not configured.
Your Telegram user id: 8737016402
Pairing code: UW6JPHL9
Ask the bot owner to approve with:
openclaw pairing approve telegram UW6JPHL9
```

→ 터미널에서 실행:

```bash
openclaw pairing approve telegram <페어링코드>
```

(코드는 본인 화면에 나온 것으로 대체)

**설명:** 보안을 위해 봇 소유자가 사용자를 승인하는 과정. 본인이 봇 소유자이므로 본인이 승인.

---

### 15단계: 대화 확인

페어링 승인 후 텔레그램에서 봇에게 다시 메시지를 보내면 AI가 응답한다. 성공!

---

## 비숙련자가 막히는 포인트 요약

| 순서 | 막히는 곳 | 대응 방법 |
|------|----------|----------|
| 1 | Node.js 22+ 미설치 | 사전 안내. `node --version`으로 확인. 없으면 https://nodejs.org 에서 설치 |
| 2 | 텔레그램 앱 없음 | 앱 스토어에서 Telegram 설치부터 |
| 3 | BotFather에서 봇 토큰 만들기 | 6단계 절차 따라가기. 화면 캡처 필수 안내 |
| 4 | 봇 사용자명 중복 | `_bot`으로 끝나는 다른 이름 시도 |
| 5 | 봇과 대화창을 못 찾음 | BotFather ≠ 내 봇. `t.me/봇이름` 링크로 이동 |
| 6 | 페어링 승인 | 봇이 보낸 코드를 터미널에서 `openclaw pairing approve` 실행 |
| 7 | Health check 실패 | 게이트웨이 기동 지연. `openclaw status`로 재확인 |
| 8 | 선택지가 너무 많아 혼란 | 스킬, API 키, Hooks는 전부 Skip/No 안내 |

---

## 유용한 명령어

| 명령어 | 용도 |
|--------|------|
| `openclaw status` | 전체 상태 확인 |
| `openclaw doctor` | 진단 + 자동 수정 |
| `openclaw configure` | 설정 변경 |
| `openclaw logs --follow` | 실시간 로그 확인 |
| `openclaw pairing approve telegram <코드>` | 텔레그램 사용자 승인 |
| `openclaw security audit --deep` | 보안 점검 |

---

## 트러블슈팅 — 응답이 안 올 때

봇에게 메시지를 보냈는데 응답이 늦거나 안 오면:

### 1. 실시간 로그 확인

```bash
openclaw logs --follow
```

게이트웨이가 지금 뭘 하고 있는지 실시간으로 볼 수 있다:
- 모델 호출 중인지
- 도구 실행 중인지
- 에러가 났는지

`Ctrl+C`로 로그 보기 종료.

### 2. 게이트웨이 상태 확인

```bash
openclaw status
```

Gateway 항목이 **reachable**인지, Telegram 채널이 **ON / OK**인지 확인.

### 3. 게이트웨이 재시작

상태가 비정상이면:

```bash
openclaw gateway restart
```

### 4. 로그 파일 직접 확인

실시간 로그로 안 보이면 로그 파일을 직접 열기:

```bash
cat ~/.openclaw/logs/gateway.log
```

---

## 참고

- 웹 검색 기능은 Brave Search API 키가 필요 (무료 $5/월 크레딧, 카드 등록 필요). 초기 세션에서는 스킵 권장.
- 설정 파일 위치: `~/.openclaw/openclaw.json`
- 로그 위치: `~/.openclaw/logs/gateway.log`
- 대시보드: http://127.0.0.1:18789/
