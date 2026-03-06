# 응원 챌린지 DB 마이그레이션 설계서

현재 GAS + Google Sheets 기반 응원 시스템을 PostgreSQL로 점진 전환한다.

---

## 배경

- 현재: 프론트/서버 → GAS 웹앱 → Google Sheets (profiles, cheers 시트)
- 문제: 수만 명 규모에서 전체 시트 순회 O(n), 동시 실행 30개 제한, race condition, cheerCount 비원자적 갱신
- 목표: 기존 PostgreSQL(pg 직접 쿼리 패턴)로 전환, 라이브 서비스 중단 없이

---

## Phase 1 — 쓰기 전환 + 읽기 합산 ✅ 구현 완료

브랜치: `fix/manual-ch-variation-diversity`
커밋: `8acd8a61 feat: 응원 챌린지 DB 마이그레이션 Phase 1`

**구현된 것:**
- challenge_profiles, challenge_cheers 테이블 생성 (migration)
- challenge 라우터 신규: 쓰기(DB) + 읽기(DB+GAS 합산)
- shared.ts: ensureProfile/addCheer를 GAS → DB 직접 쿼리로 전환
- 프론트 challenge-api: GAS → 서버 프록시로 전환
- UserProvider Context로 GET /api/user 호출 4회 → 1회 통합
- referral-cheer: 신규 가입자(10분 이내)만 응원 발생하도록 제한
- 챕터 카드 UI 인터랙션 강화, 설명 영역 가독성 개선

**같은 브랜치의 추가 커밋:**
- `ed653982` MBTI 재료/상황 풀 조합으로 챕터 결과 다양성 개선
- `74479065` checkCheer API 중복 호출 제거 (Provider + cache-first)

### 1. 마이그레이션 SQL

```sql
CREATE TABLE IF NOT EXISTS challenge_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(100) NOT NULL,
  handle VARCHAR(200) NOT NULL,
  university VARCHAR(100) NOT NULL,
  bio TEXT DEFAULT '',
  card_id VARCHAR(50) DEFAULT 'card1',
  cheer_count INTEGER NOT NULL DEFAULT 0,
  image VARCHAR(500) DEFAULT '',
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_challenge_profiles_university ON challenge_profiles(university);
CREATE INDEX IF NOT EXISTS idx_challenge_profiles_cheer_count ON challenge_profiles(cheer_count DESC);

CREATE TABLE IF NOT EXISTS challenge_cheers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cheer_email VARCHAR(255) NOT NULL,
  cheer_university VARCHAR(100),
  target_profile_id UUID NOT NULL REFERENCES challenge_profiles(id),
  message TEXT DEFAULT '',
  marketing_consent BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- 1인 1응원: 시스템 계정(moonlight@corca.ai) 제외한 일반 유저만 제약
-- partial unique index로 구현
CREATE UNIQUE INDEX IF NOT EXISTS idx_challenge_cheers_email_unique
  ON challenge_cheers (cheer_email)
  WHERE cheer_email != 'moonlight@corca.ai';

CREATE INDEX IF NOT EXISTS idx_challenge_cheers_target ON challenge_cheers(target_profile_id);
```

### 2. 서버 API — 쓰기 엔드포인트

기존 `campus-activity/router.ts` 패턴을 따른다. 새 라우터 또는 기존 라우터 확장. **모든 쓰기 엔드포인트에 authMiddleware 필수** (로그인 대학 유저만 참여 가능).

| 엔드포인트 | 동작 |
|-----------|------|
| POST /challenge/profile | DB에 프로필 생성 (email unique, 대학 이메일 검증) |
| POST /challenge/cheer | DB에 응원 기록 + `cheer_count` 원자적 증가 (**트랜잭션**) |
| POST /challenge/profile/update | DB에 프로필 수정 (bio, cardId) |

**cheer 트랜잭션** — INSERT와 count UPDATE를 반드시 묶는다:

```sql
BEGIN;
INSERT INTO challenge_cheers (cheer_email, cheer_university, target_profile_id, message, marketing_consent)
VALUES ($1, $2, $3, $4, $5);
UPDATE challenge_profiles SET cheer_count = cheer_count + 1 WHERE id = $3;
COMMIT;
```

동시성: partial unique index + `ON CONFLICT DO NOTHING`으로 중복 방지.

**corca.ai 예외 처리:**
- 대학 이메일 검증: `corca.ai`를 허용 도메인에 포함 (GAS의 `ALLOWED_NON_STANDARD_DOMAINS`, shared.ts의 `DOMAIN_TO_UNI`와 동일)
- 1인 1응원: `moonlight@corca.ai`는 시스템 계정으로 다수 응원 가능 (partial unique index로 제외됨)
- 자기 자신 응원 방지: 시스템 계정은 예외

**시트 쓰기 freeze:** Phase 1 배포 시점에 시트 쓰기를 중단한다. 프론트/서버의 쓰기가 DB로 전환되면 GAS의 createProfile, cheer, updateProfile은 더 이상 호출되지 않는다. 시트 데이터는 배포 시점에서 freeze.

### 3. 서버 API — 읽기 엔드포인트 (DB + GAS 합산)

Phase 1에서는 시트에 freeze된 기존 데이터가 있으므로, 읽기 시 **DB + GAS 양쪽을 읽어서 합산**한다.

| 엔드포인트 | 동작 |
|-----------|------|
| GET /challenge/leaderboard | DB profiles + GAS getAllProfiles → 이메일 기준 병합, cheerCount 합산, 정렬 |
| GET /challenge/university-stats | DB + GAS 대학별 통계 병합 |
| GET /challenge/profile/:id | DB 먼저 조회, 없으면 GAS 폴백 |
| GET /challenge/profile/email/:email | DB 먼저, 없으면 GAS |
| GET /challenge/check-cheer/:email | DB cheers 확인 OR GAS checkCheer |
| GET /challenge/featured | GAS dashboard 시트 유지 (운영용) |

**합산 로직:**
- 이메일 기준 병합. 같은 이메일이 양쪽에 있으면 cheerCount 합산
- DB에만 있는 프로필은 추가
- 시트에만 있는 프로필(freeze 시점 기존 유저)은 그대로 포함
- GAS 호출 실패 시 DB 데이터만으로 응답 (GAS는 optional)

**GAS에 getAllProfiles, getAllCheers 액션 추가됨** — import와 합산 읽기에 활용.

### 4. 프론트 전환

`challenge-api.ts`의 API_URL을 서버 엔드포인트로 교체.

### 5. shared.ts 전환

`ensureProfile()`, `addCheer()`를 DB 직접 쿼리로 변경. GAS fetch 제거.

### 6. 롤백 계획

문제 발생 시: 프론트 `challenge-api.ts`의 API_URL을 GAS URL로 되돌리면 즉시 롤백. GAS 코드와 시트 데이터는 그대로 남아있으므로 시트 freeze 시점까지의 데이터로 서비스 가능.

---

## Phase 2 — 시트 데이터 이관 + GAS 은퇴

### 7. 시트 → DB import 스크립트

GAS의 `getAllProfiles`, `getAllCheers` 액션으로 전체 데이터 fetch.

**import 순서: profiles → cheers** (cheers의 target_profile_id FK 때문에 profiles 먼저)

```
1. getAllProfiles → challenge_profiles INSERT ... ON CONFLICT (email) DO UPDATE
2. getAllCheers import — 3단계 매핑 필요:
   a. cheers 시트의 targetProfileId (GAS의 pXXXXXXXX 형식)
   b. → profiles 시트에서 해당 profileId의 email 조회
   c. → DB challenge_profiles에서 email로 UUID 조회 → challenge_cheers INSERT
   ※ getAllCheers GAS 스크립트 버그 주의: 시트 컬럼은 row[4]=marketingConsent(Y/N), row[5]=createdAt인데 현재 GAS에서 row[5]를 marketingConsent로 매핑 중. import 시 인덱스 보정 필요.
3. cheer_count 재계산: UPDATE challenge_profiles SET cheer_count = (SELECT COUNT(*) FROM challenge_cheers WHERE target_profile_id = challenge_profiles.id)
```

**이중 카운팅 방지:** import 후 cheer_count를 cheers 레코드 기준으로 재계산한다. 시트의 cheerCount 값은 사용하지 않는다.

### 8. 읽기에서 GAS 호출 제거

Phase 1의 합산 로직에서 GAS 호출 부분 제거. DB만 읽기.

### 9. GAS 은퇴

코드/시트는 삭제하지 않음 (백업 참조용). 프론트/서버에서 호출만 제거.

---

## 참고

- 기존 GAS 코드: `scripts/cheer-challenge-apps-script.js`
- 기존 프론트 API: `packages/moonlight-web/src/app/[lang]/universities/challenge-api.ts`
- 기존 서버 shared: `packages/moonlight-server/src/campus-activity/shared.ts`
- 대학 도메인 맵: shared.ts의 `DOMAIN_TO_UNI` (380+ 대학) — 그대로 재사용
- 기존 DB 패턴: `campus-activity/router.ts` (pg 직접 쿼리, zod 검증, advisory lock)
- GAS 데이터 export: `getAllProfiles`, `getAllCheers` 액션 (GAS에 추가됨)
