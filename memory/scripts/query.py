#!/usr/bin/env python3
"""기억 조회: 에피소드 필터링 및 출력

사용법:
  python3 memory/scripts/query.py                          # 최근 10건
  python3 memory/scripts/query.py --project lighthouse      # 프로젝트별
  python3 memory/scripts/query.py --type decision           # 활동 유형별
  python3 memory/scripts/query.py --emotion frustration     # 감정별
  python3 memory/scripts/query.py --keyword "속도"          # 키워드 검색
  python3 memory/scripts/query.py --scope permanent         # 스코프별
  python3 memory/scripts/query.py --session 세션15          # 세션별
  python3 memory/scripts/query.py --recent 5                # 최근 N건
  python3 memory/scripts/query.py --milestone               # 마일스톤만
  python3 memory/scripts/query.py --relationship            # 관계 변화 에피소드만
  python3 memory/scripts/query.py --stats                   # 통계 요약

필터는 조합 가능:
  python3 memory/scripts/query.py --project lighthouse --emotion excitement --recent 3
"""

import json
import argparse
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EPISODES_FILE = PROJECT_ROOT / "memory" / "episodes.json"


def load_episodes() -> list[dict]:
    if not EPISODES_FILE.exists():
        return []
    with open(EPISODES_FILE, encoding="utf-8") as f:
        return json.load(f)


def filter_episodes(episodes: list[dict], args) -> list[dict]:
    result = episodes

    if args.project:
        result = [e for e in result if e.get("project") == args.project]

    if args.type:
        result = [e for e in result if e.get("activity_type") == args.type]

    if args.emotion:
        result = [e for e in result if e.get("emotion") == args.emotion]

    if args.scope:
        result = [e for e in result if e.get("scope") == args.scope]

    if args.session:
        result = [e for e in result if args.session in e.get("session", "")]

    if args.milestone:
        result = [e for e in result if e.get("milestone_key")]

    if args.relationship:
        result = [e for e in result if e.get("relationship_type")]

    if args.keyword:
        kw = args.keyword.lower()
        result = [
            e for e in result
            if kw in e.get("topic", "").lower()
            or kw in e.get("summary", "").lower()
            or kw in e.get("outcome_detail", "").lower()
        ]

    if args.recent:
        result = result[-args.recent:]

    return result


def format_episode(ep: dict, verbose: bool = False) -> str:
    lines = []
    # 헤더
    session = ep.get("session", "?")
    idx = ep.get("episode_index", "?")
    topic = ep.get("topic", "")
    activity = ep.get("activity_type", "")
    lines.append(f"[{session}#{idx}] {activity} — {topic}")

    # 요약
    summary = ep.get("summary", "")
    if summary:
        lines.append(f"  {summary}")

    # 태그 라인
    tags = []
    if ep.get("project"):
        tags.append(f"프로젝트:{ep['project']}")
    if ep.get("emotion"):
        tags.append(f"감정:{ep['emotion']}")
    if ep.get("outcome"):
        outcome_str = ep["outcome"]
        if ep.get("outcome_detail"):
            outcome_str += f"({ep['outcome_detail']})"
        tags.append(f"결과:{outcome_str}")
    if ep.get("relationship_type"):
        tags.append(f"관계:{ep['relationship_type']}")
    if ep.get("milestone_key"):
        tags.append(f"마일스톤:{ep['milestone_key']}")
    if ep.get("scope"):
        tags.append(f"스코프:{ep['scope']}")
    if tags:
        lines.append(f"  [{' | '.join(tags)}]")

    # 상세 모드
    if verbose:
        if ep.get("decision_refs"):
            lines.append(f"  결정 참조: {', '.join(ep['decision_refs'])}")
        if ep.get("created_at"):
            lines.append(f"  생성: {ep['created_at']}")

    return "\n".join(lines)


def print_stats(episodes: list[dict]):
    if not episodes:
        print("에피소드 없음")
        return

    print(f"=== 기억 통계 ({len(episodes)}건) ===\n")

    # 프로젝트별
    projects = Counter(e.get("project", "미분류") for e in episodes)
    print("프로젝트별:")
    for proj, cnt in projects.most_common():
        print(f"  {proj}: {cnt}건")

    # 활동 유형별
    types = Counter(e.get("activity_type", "미분류") for e in episodes)
    print("\n활동 유형별:")
    for t, cnt in types.most_common():
        print(f"  {t}: {cnt}건")

    # 감정 분포
    emotions = Counter(e["emotion"] for e in episodes if e.get("emotion"))
    if emotions:
        print("\n감정 분포:")
        for em, cnt in emotions.most_common():
            print(f"  {em}: {cnt}건")

    # 결과 분포
    outcomes = Counter(e.get("outcome", "미분류") for e in episodes)
    print("\n결과 분포:")
    for o, cnt in outcomes.most_common():
        print(f"  {o}: {cnt}건")

    # 관계 유형
    rels = Counter(e["relationship_type"] for e in episodes if e.get("relationship_type"))
    if rels:
        print("\n관계 변화:")
        for r, cnt in rels.most_common():
            print(f"  {r}: {cnt}건")

    # 마일스톤
    milestones = [e for e in episodes if e.get("milestone_key")]
    if milestones:
        print(f"\n마일스톤 ({len(milestones)}건):")
        for m in milestones:
            print(f"  [{m['session']}] {m['milestone_key']} — {m.get('topic', '')}")

    # 세션별
    sessions = Counter(e.get("session", "?") for e in episodes)
    print(f"\n세션별 에피소드 수 ({len(sessions)}개 세션):")
    for s, cnt in sorted(sessions.items()):
        print(f"  {s}: {cnt}건")


def main():
    parser = argparse.ArgumentParser(description="기억 조회: 에피소드 필터링")
    parser.add_argument("--project", help="프로젝트 필터 (lighthouse, agentic-engineering, meta-agent, mirror-mind-ops)")
    parser.add_argument("--type", help="활동 유형 필터 (design, decision, review, ...)")
    parser.add_argument("--emotion", help="감정 필터 (excitement, frustration, ...)")
    parser.add_argument("--scope", help="스코프 필터 (permanent, project, task, archive)")
    parser.add_argument("--session", help="세션 필터 (부분 매칭)")
    parser.add_argument("--keyword", help="키워드 검색 (topic, summary, outcome_detail)")
    parser.add_argument("--recent", type=int, help="최근 N건만")
    parser.add_argument("--milestone", action="store_true", help="마일스톤만")
    parser.add_argument("--relationship", action="store_true", help="관계 변화 에피소드만")
    parser.add_argument("--stats", action="store_true", help="통계 요약")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    episodes = load_episodes()

    if args.stats:
        filtered = filter_episodes(episodes, args) if any([
            args.project, args.type, args.emotion, args.scope,
            args.session, args.keyword, args.milestone, args.relationship
        ]) else episodes
        print_stats(filtered)
        return

    # 필터 적용
    filtered = filter_episodes(episodes, args)

    # 필터 없으면 최근 10건
    if not any([args.project, args.type, args.emotion, args.scope,
                args.session, args.keyword, args.recent,
                args.milestone, args.relationship]):
        filtered = filtered[-10:]

    if not filtered:
        print("조건에 맞는 에피소드 없음")
        return

    if args.json:
        print(json.dumps(filtered, ensure_ascii=False, indent=2))
        return

    print(f"--- {len(filtered)}건 ---\n")
    for ep in filtered:
        print(format_episode(ep, verbose=args.verbose))
        print()


if __name__ == "__main__":
    main()
