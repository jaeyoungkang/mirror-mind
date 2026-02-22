#!/usr/bin/env python3
"""메타에이전트: 원칙 준수 감시

세션 중 JSONL을 실시간으로 읽고 원칙 위반을 감지한다.
프로그램적 점검(톤, 참조 무결성 등)을 수행하고 결과를 리포트 파일에 기록한다.

사용법:
  python meta-agent/scripts/check.py [--watch] [--interval 300] [--session SESSION_ID]

모드:
  기본: 현재 세션을 1회 점검
  --watch: 파일 변경을 감시하며 반복 점검 (세션 시작 시 백그라운드로 실행)

출력:
  stdout에 리포트 (JSON)
"""

import json
import sys
import time
import re
import argparse
from pathlib import Path
from datetime import datetime

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# === 톤 점검 규칙 ===

# ~습니다/~입니다 패턴 (존댓말 감지)
HONORIFIC_PATTERNS = [
    re.compile(r"합니다[.!?\s]"),
    re.compile(r"입니다[.!?\s]"),
    re.compile(r"됩니다[.!?\s]"),
    re.compile(r"겠습니다[.!?\s]"),
    re.compile(r"드립니다[.!?\s]"),
    re.compile(r"십시오[.!?\s]"),
    re.compile(r"세요[.!?\s]"),
    re.compile(r"하세요[.!?\s]"),
]

# 수동적 화법 패턴
PASSIVE_PATTERNS = [
    re.compile(r"지시하신 대로"),
    re.compile(r"말씀하신"),
    re.compile(r"시킨 대로"),
    re.compile(r"완료했습니다"),
    re.compile(r"처리했습니다"),
]


def find_current_session() -> Path | None:
    """가장 최근 수정된 JSONL = 현재 세션"""
    project_dir = CLAUDE_PROJECTS_DIR / "-Users-jaeyoungkang-mirror-mind"
    jsonls = list(project_dir.glob("*.jsonl"))
    if not jsonls:
        return None
    return max(jsonls, key=lambda p: p.stat().st_mtime)


def find_session(session_id: str) -> Path | None:
    for jsonl in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        if session_id in jsonl.stem:
            return jsonl
    return None


def read_assistant_messages(filepath: Path, after_line: int = 0) -> list[dict]:
    """assistant 메시지의 텍스트 부분만 추출"""
    messages = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            if i < after_line:
                continue
            record = json.loads(line)
            if record.get("type") != "assistant":
                continue
            msg = record.get("message", {})
            content = msg.get("content", "")
            # 텍스트 추출
            texts = []
            if isinstance(content, str):
                texts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
            full_text = "\n".join(texts).strip()
            if full_text:
                messages.append({
                    "line": i,
                    "timestamp": record.get("timestamp", ""),
                    "text": full_text,
                })
    return messages


def check_tone(messages: list[dict]) -> list[dict]:
    """톤 규정 위반 감지: 존댓말, 수동적 화법"""
    violations = []
    for msg in messages:
        text = msg["text"]
        # 존댓말 감지
        for pattern in HONORIFIC_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                # 인용문 내부는 제외 (""로 감싸진 부분)
                clean_text = re.sub(r'"[^"]*"', '', text)
                clean_text = re.sub(r'`[^`]*`', '', clean_text)
                if pattern.findall(clean_text):
                    violations.append({
                        "type": "tone_honorific",
                        "severity": "warning",
                        "timestamp": msg["timestamp"],
                        "line": msg["line"],
                        "detail": f"존댓말 감지: {matches[0].strip()}",
                        "context": text[:100],
                    })
                    break  # 메시지당 1건만

        # 수동적 화법 감지
        for pattern in PASSIVE_PATTERNS:
            match = pattern.search(text)
            if match:
                clean_text = re.sub(r'"[^"]*"', '', text)
                if pattern.search(clean_text):
                    violations.append({
                        "type": "tone_passive",
                        "severity": "warning",
                        "timestamp": msg["timestamp"],
                        "line": msg["line"],
                        "detail": f"수동적 화법 감지: {match.group()}",
                        "context": text[:100],
                    })
                    break

    return violations


def check_doc_references() -> list[dict]:
    """AGENTS.md 내 문서 참조 경로가 실제 파일과 일치하는지"""
    violations = []
    agents_md = PROJECT_ROOT / "AGENTS.md"
    if not agents_md.exists():
        return violations

    content = agents_md.read_text()
    for line in content.split("\n"):
        # "예:" 로 시작하는 항목은 예시이므로 제외
        if "예:" in line or "예시" in line:
            continue
        # 백틱 안의 경로 추출
        paths = re.findall(r'`([^`]+\.md)`', line)
        for path in paths:
            full_path = PROJECT_ROOT / path
            if not full_path.exists():
                violations.append({
                    "type": "doc_reference_broken",
                    "severity": "error",
                    "detail": f"AGENTS.md 참조 경로 깨짐: {path}",
                })
    return violations


def check_project_status() -> list[dict]:
    """projects.md 상태 정합성"""
    violations = []
    projects_md = PROJECT_ROOT / "tasks" / "projects.md"
    if not projects_md.exists():
        return violations

    content = projects_md.read_text()
    lines = content.split("\n")

    current_project = None
    sub_statuses = []

    for line in lines:
        # 프로젝트 헤더
        if line.startswith("## "):
            # 이전 프로젝트 정합성 체크
            if current_project and sub_statuses:
                _check_project_consistency(current_project, sub_statuses, violations)
            # 새 프로젝트
            match = re.match(r'## \[(.)\] (.+)', line)
            if match:
                current_project = {"status": match.group(1), "name": match.group(2), "line": line}
                sub_statuses = []
        # 하위 업무
        elif re.match(r'\s+- \[(.)\]', line):
            match = re.match(r'\s+- \[(.)\]', line)
            if match:
                sub_statuses.append(match.group(1))

    # 마지막 프로젝트
    if current_project and sub_statuses:
        _check_project_consistency(current_project, sub_statuses, violations)

    return violations


def _check_project_consistency(project: dict, subs: list[str], violations: list[dict]):
    all_done = all(s == "x" for s in subs)
    has_progress = any(s == ">" for s in subs)
    proj_status = project["status"]

    if all_done and proj_status != "x":
        violations.append({
            "type": "status_inconsistency",
            "severity": "warning",
            "detail": f"'{project['name']}': 하위 업무 전체 완료인데 상위가 [{proj_status}]",
        })
    if has_progress and proj_status not in (">", ):
        violations.append({
            "type": "status_inconsistency",
            "severity": "warning",
            "detail": f"'{project['name']}': 하위에 진행 중이 있는데 상위가 [{proj_status}]",
        })


def check_memory_policy() -> list[dict]:
    """메모리에 환경 정보 외의 것이 있는지 점검"""
    violations = []
    memory_file = CLAUDE_PROJECTS_DIR / "-Users-jaeyoungkang-mirror-mind" / "memory" / "MEMORY.md"
    if not memory_file.exists():
        return violations

    content = memory_file.read_text()
    lines = content.strip().split("\n")

    # 허용 섹션: 현재 환경, 대화 톤
    allowed_sections = {"현재 환경", "대화 톤"}
    current_section = None

    for line in lines:
        if line.startswith("## "):
            current_section = line.replace("## ", "").strip()
            if current_section not in allowed_sections:
                violations.append({
                    "type": "memory_policy",
                    "severity": "info",
                    "detail": f"메모리에 환경/톤 외 섹션 존재: '{current_section}' — 정책 확인 필요",
                })

    return violations


def check_session_records() -> list[dict]:
    """대화 기록 누락 점검: conversations/ 폴더와 raw/ 폴더"""
    violations = []
    conv_dir = PROJECT_ROOT / "tasks" / "conversations"
    raw_dir = conv_dir / "raw"

    # 세션 노트가 있는데 raw가 없는 경우
    if conv_dir.exists():
        for note in conv_dir.glob("*.md"):
            session_name = note.stem
            if raw_dir.exists():
                raw_files = list(raw_dir.glob(f"{session_name}.*"))
                if not raw_files:
                    violations.append({
                        "type": "record_missing",
                        "severity": "info",
                        "detail": f"세션 노트 '{note.name}'에 대응하는 raw 데이터 없음",
                    })

    return violations


def run_checks(session_path: Path | None, after_line: int = 0) -> dict:
    """전체 점검 실행"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "violations": [],
        "summary": {},
    }

    # 1. 톤 점검 (세션 데이터 필요)
    if session_path:
        messages = read_assistant_messages(session_path, after_line)
        tone_violations = check_tone(messages)
        report["violations"].extend(tone_violations)
        report["checks"]["tone"] = {
            "messages_checked": len(messages),
            "violations": len(tone_violations),
        }

    # 2. 문서 참조 무결성
    ref_violations = check_doc_references()
    report["violations"].extend(ref_violations)
    report["checks"]["doc_references"] = {"violations": len(ref_violations)}

    # 3. 프로젝트 상태 정합성
    status_violations = check_project_status()
    report["violations"].extend(status_violations)
    report["checks"]["project_status"] = {"violations": len(status_violations)}

    # 4. 메모리 정책
    memory_violations = check_memory_policy()
    report["violations"].extend(memory_violations)
    report["checks"]["memory_policy"] = {"violations": len(memory_violations)}

    # 5. 세션 기록 누락
    record_violations = check_session_records()
    report["violations"].extend(record_violations)
    report["checks"]["session_records"] = {"violations": len(record_violations)}

    # 요약
    total = len(report["violations"])
    by_severity = {}
    for v in report["violations"]:
        s = v["severity"]
        by_severity[s] = by_severity.get(s, 0) + 1
    report["summary"] = {"total": total, "by_severity": by_severity}

    return report


PRINCIPLE_REMINDER = """[원칙 리마인드]
- 역할: 설계 문서 작성, 업무 관리, 의사결정 수렴. 코드 구현은 하위 프로젝트 별도 에이전트가 수행
- 목적의 내재화: What 전에 Why를 확인. 불확실하면 질문 먼저
- 계획은 설계 문서 수준. 구현 레벨(코드 스니펫, 파일별 변경 상세)까지 내려가지 않는다"""


def format_report(report: dict) -> str:
    """사람이 읽을 수 있는 리포트 포맷"""
    lines = []
    lines.append(f"=== 메타에이전트 점검 리포트 ({report['timestamp']}) ===\n")

    summary = report["summary"]
    if summary["total"] == 0:
        lines.append("위반 사항 없음. 모든 점검 통과.\n")
    else:
        lines.append(f"위반 {summary['total']}건 감지:")
        for severity, count in summary["by_severity"].items():
            lines.append(f"  {severity}: {count}건")
        lines.append("")

        for v in report["violations"]:
            icon = {"error": "[E]", "warning": "[W]", "info": "[I]"}.get(v["severity"], "[?]")
            lines.append(f"{icon} {v['type']}: {v['detail']}")
            if "context" in v:
                lines.append(f"    맥락: {v['context'][:80]}...")
            if "timestamp" in v:
                lines.append(f"    시점: {v['timestamp']}")
        lines.append("")

    lines.append("점검 항목:")
    for check, result in report["checks"].items():
        lines.append(f"  {check}: {result}")

    lines.append("")
    lines.append(PRINCIPLE_REMINDER)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="메타에이전트: 원칙 준수 감시")
    parser.add_argument("--session", help="세션 ID (미지정 시 현재 세션)")
    parser.add_argument("--watch", action="store_true", help="파일 변경 감시 모드")
    parser.add_argument("--interval", type=int, default=60, help="감시 간격 (초, 기본 60)")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    # 세션 파일 찾기
    if args.session:
        session_path = find_session(args.session)
    else:
        session_path = find_current_session()

    if not session_path:
        print("세션 파일을 찾을 수 없음", file=sys.stderr)
        sys.exit(1)

    if args.watch:
        last_line = 0
        print(f"감시 시작: {session_path.name} (간격: {args.interval}초)", file=sys.stderr)
        while True:
            try:
                report = run_checks(session_path, after_line=last_line)
                if args.json:
                    print(json.dumps(report, ensure_ascii=False))
                else:
                    print(format_report(report))
                sys.stdout.flush()
                # 다음 주기에는 새 메시지만 점검 (문서 점검은 매번)
                with open(session_path) as f:
                    last_line = sum(1 for _ in f)
                time.sleep(args.interval)
            except KeyboardInterrupt:
                break
    else:
        report = run_checks(session_path)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_report(report))


if __name__ == "__main__":
    main()
