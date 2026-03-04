"""나의 학기 사용설명서 — 5챕터 샘플 생성"""

import json
import os
from pathlib import Path
from google import genai

# .env에서 키 읽기
env_path = Path(__file__).resolve().parent.parent / ".env"
for line in env_path.read_text().splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

client = genai.Client(api_key=os.environ["GOOGLE_GENERATIVE_AI_API_KEY"])
MODEL = "gemini-3-flash-preview"

MBTI = "INTJ"
DATE = "2026-03-04"
UNIV = "KAIST"
MAJOR = "전산학"
GRADE = "석사 2년차"

CHAPTERS = {
    1: {
        "name": "이번 학기 생존 확률",
        "schema": """{
  "survival_rate": 73,
  "title": "생존 확률을 한 줄로 요약하는 문구 (예: '출석만 해도 반은 간다')",
  "strength": "이번 학기 강점 한 줄",
  "danger": "이번 학기 최대 위험 요소 한 줄",
  "survival_tip": "생존 팁 한 줄",
  "comment": "재밌는 한 줄 코멘트"
}""",
        "guide": """생존 확률은 30~95% 사이에서 MBTI 특성에 맞게 설정.
숫자가 낮으면 위험하다는 느낌, 높으면 자신감.
대학원생(석사/박사)이면 수업이 아니라 연구실 생활이 중심이다.
대학원 맥락: 랩미팅, 논문 리뷰, 지도교수 미팅, 학회 마감, 졸업 요건, 코드 디버깅, 서버 점검, 새벽 연구실 등.
INTJ 석사: 계획적이고 완벽주의적이지만 혼자 파고드느라 소통 부족해지는 특성.
톤: 같은 랩 동기가 장난치듯 직설적이고 웃기게.""",
    },
    2: {
        "name": "나의 학기 스탯",
        "schema": """{
  "stats": [
    { "name": "학점력", "value": 82, "bar": "████████░░" },
    { "name": "인싸력", "value": 65, "bar": "██████░░░░" },
    { "name": "과제력", "value": 45, "bar": "████░░░░░░" },
    { "name": "벼락치기", "value": 88, "bar": "████████░░" },
    { "name": "멘탈", "value": 55, "bar": "█████░░░░░" }
  ],
  "badge": "칭호 (예: '고독한 A+사냥꾼', '열정 과잉 새내기')",
  "description": "이 캐릭터에 대한 한 줄 설명 (찔리거나 웃기게)",
  "hidden_stat": "숨겨진 스탯 이름과 값 (예: '교수님 눈치력 99')"
}""",
        "guide": """RPG 캐릭터 시트 느낌. 스탯 5개는 고정 항목(학점력/인싸력/과제력/벼락치기/멘탈).
value는 10~99. bar는 10칸 중 value/10개를 █로, 나머지 ░로.
MBTI 특성이 스탯에 명확히 드러나야 한다.
대학원생이면 '과제력'은 '논문력'으로, '벼락치기'는 '데드라인 서바이벌'로 읽어도 된다. 대학원 맥락에서 해석.
INTJ 석사: 학점력/논문력 높고, 인싸력 낮고, 멘탈은 지도교수에 의해 좌우.
칭호는 RPG 칭호처럼 웃기고 핵심을 찌르는 이름. 대학원 감성.
숨겨진 스탯은 보너스 재미 요소 — 대학원생만 아는 능력.
전산학 석사면 코딩/서버/논문 관련 맥락을 반영.""",
    },
    3: {
        "name": "새학기 금지어",
        "schema": """{
  "forbidden": [
    {
      "phrase": "이번 학기에 하면 안 되는 말 (따옴표 포함)",
      "roast": "왜 하면 안 되는지 한 줄 디스"
    },
    {
      "phrase": "두 번째 금지어",
      "roast": "디스"
    },
    {
      "phrase": "세 번째 금지어",
      "roast": "디스"
    }
  ],
  "instead": "대신 이번 학기에 해야 할 말 한 줄",
  "comment": "마무리 한 줄 코멘트"
}""",
        "guide": """금지어 3개. 매학기 습관처럼 하는 말인데 결국 후회하는 것들.
MBTI 특성에 맞는 금지어여야 한다.
대학원생 금지어: "이번 달 안에 논문 쓸 수 있을 것 같은데", "지도교수님 피드백 금방 오겠지", "코드 리팩토링 한 번만 더" 같은.
INTJ: 완벽주의 + 혼자 해결하려는 성향에서 오는 금지어.
roast는 짧고 날카롭게. 같은 랩 동기가 "야 너 또 그러냐" 하는 느낌.
instead는 현실적이고 웃긴 대안.
전산학 석사 맥락 반영.""",
    },
    4: {
        "name": "이번 학기 시나리오",
        "schema": """{
  "episodes": [
    { "month": "3월", "emoji": "🌸", "title": "짧은 제목", "description": "2줄 이내 상황 묘사" },
    { "month": "4월", "emoji": "😰", "title": "짧은 제목", "description": "2줄 이내" },
    { "month": "5월", "emoji": "🎉", "title": "짧은 제목", "description": "2줄 이내" },
    { "month": "6월", "emoji": "🔥", "title": "짧은 제목", "description": "2줄 이내" }
  ],
  "ending": "학기 말 결과 한 줄 (예: 'B+ 사수 성공')",
  "moral": "이번 학기의 교훈 한 줄"
}""",
        "guide": """3월~6월 4개 에피소드로 학기를 시간순 서사로 풀어라.
MBTI 특성이 스토리에 녹아야 한다.
대학원생이면 수업보다 연구실 생활이 중심. 랩미팅, 논문, 학회, 지도교수, 졸업 압박.
INTJ 석사: 3월에 야심 찬 연구 계획 → 4월에 혼자 삽질 → 5월에 학회 마감 → 6월에 졸업 요건 계산.
각 에피소드는 대학원생만 아는 구체적 장면.
결말과 교훈은 유머 있게. 전산학 석사 맥락.""",
    },
    5: {
        "name": "교수님 궁합",
        "schema": """{
  "prof_type": "교수님 유형 한 줄 (예: '출석은 안 부르지만 다 알고 계시는 타입')",
  "compatibility": 3,
  "compatibility_label": "궁합 한 줄 (예: '위태로운 공존')",
  "danger_point": "위험 포인트 한 줄 + 확률% (예: '발표 지명 확률 87%')",
  "survival_strategy": "생존 전략 2줄",
  "one_liner": "한줄평 (교수님이 이 학생에 대해 한마디)"
}""",
        "guide": """가상의 교수님(=지도교수님) 유형을 생성하고 MBTI와의 궁합을 본다.
대학원생이면 '교수님'이 아니라 '지도교수님'이다. 관계가 훨씬 밀접하고 긴장감 있다.
compatibility는 1~5 (별점).
지도교수 유형: "논문 리뷰 때만 나타나는 유령형", "새벽 3시에 슬랙 보내는 타입", "논문 한 줄 고치는데 3시간 미팅" 같은.
INTJ와 궁합이 재밌게 나오는 조합으로.
위험 포인트의 확률%는 과장해서 웃기게.
생존 전략은 현실적이면서 위트 있게.
한줄평은 지도교수님 시점에서 이 대학원생을 한마디로.
전산학 교수님 맥락.""",
    },
}

def generate_chapter(ch_num: int, ch: dict) -> dict:
    prompt = f"""너는 대학생을 위한 MBTI 콘텐츠 작가다. "나의 학기 사용설명서" 시리즈의 챕터 {ch_num}을 작성한다.

## 정보
- MBTI: {MBTI}
- 날짜: {DATE}
- 대학: {UNIV}
- 전공: {MAJOR}
- 학년: {GRADE}

## 챕터: {ch['name']}

## 작성 가이드
{ch['guide']}

## 출력
반드시 아래 JSON 스키마를 따라 JSON만 출력하라. 다른 텍스트 없이 순수 JSON만.
{ch['schema']}

## 톤
- 친구가 장난치듯 직설적이고 웃기게
- "아 이거 나야ㅋㅋ" 하고 찔리는 수준
- 대학생 일상의 구체적 디테일 (수강신청, 도서관, 학식, 조별과제, 교수님 등)
- 새학기 분위기 (설렘 + 긴장 + 다짐)
"""
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    text = resp.text.strip()
    # strip markdown code fence if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3]
        elif "```" in text:
            text = text[:text.rfind("```")]
    return json.loads(text.strip())


results = {}
for ch_num, ch in CHAPTERS.items():
    print(f"CH.{ch_num} {ch['name']} 생성 중...")
    try:
        result = generate_chapter(ch_num, ch)
        results[f"ch{ch_num}"] = {"name": ch["name"], "result": result}
        print(f"  ✓ 완료")
    except Exception as e:
        print(f"  ✗ 에러: {e}")
        results[f"ch{ch_num}"] = {"name": ch["name"], "error": str(e)}

print("\n" + "=" * 60)
print(f"나의 학기 사용설명서 — {MBTI} · {UNIV} {MAJOR} {GRADE}")
print("=" * 60)

for key in sorted(results):
    ch = results[key]
    num = key.replace("ch", "")
    print(f"\n{'─' * 50}")
    print(f"📖 CH.{num}: {ch['name']}")
    print(f"{'─' * 50}")
    if "error" in ch:
        print(f"  에러: {ch['error']}")
    else:
        print(json.dumps(ch["result"], ensure_ascii=False, indent=2))
