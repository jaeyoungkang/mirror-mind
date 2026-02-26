#!/usr/bin/env python3
"""메타에이전트: 원칙 준수 감시

세션 중 JSONL을 실시간으로 읽고 원칙 위반을 감지한다.
프로그램적 점검(톤, 참조 무결성 등) + LLM 점검(순응, 목적 탐구 등)을 수행한다.

사용법:
  python meta-agent/scripts/check.py [--watch] [--interval 300] [--llm]

모드:
  기본: 현재 세션을 1회 점검
  --watch: 파일 변경을 감시하며 반복 점검
  --llm: codex exec로 LLM 기반 점검 추가

출력:
  stdout에 리포트
"""

import json
import sys
import time
import re
import subprocess
import tempfile
import argparse
from pathlib import Path
from datetime import datetime

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# === 톤 점검 규칙 ===

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

PASSIVE_PATTERNS = [
    re.compile(r"지시하신 대로"),
    re.compile(r"말씀하신"),
    re.compile(r"시킨 대로"),
    re.compile(r"완료했습니다"),
    re.compile(r"처리했습니다"),
]


# === 세션 파일 탐색 ===

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


# === 메시지 추출 ===

def read_assistant_messages(filepath: Path, after_line: int = 0) -> list[dict]:
    """assistant 메시지의 텍스트 부분만 추출"""
    messages = []
    with open(filepath) as f:
        for i, line in enumerate(f):
            if i < after_line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") != "assistant":
                continue
            msg = record.get("message", {})
            content = msg.get("content", "")
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


def read_conversation_context(session_path: Path, last_n: int = 20) -> str:
    """최근 N개 메시지를 사용자/AI 라벨과 함께 텍스트로 추출"""
    messages = []
    with open(session_path) as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_type = record.get("type")
            if msg_type == "user":
                content = record.get("message", {}).get("content", "")
                if isinstance(content, str) and content.strip():
                    messages.append(f"[사용자] {content.strip()[:500]}")
            elif msg_type == "assistant":
                msg = record.get("message", {})
                content = msg.get("content", "")
                texts = []
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block.get("text", ""))
                full_text = "\n".join(texts).strip()
                if full_text:
                    messages.append(f"[AI] {full_text[:500]}")
    return "\n\n".join(messages[-last_n:])


# === 프로그램적 점검 ===

def check_tone(messages: list[dict]) -> list[dict]:
    """톤 규정 위반 감지: 존댓말, 수동적 화법"""
    violations = []
    for msg in messages:
        text = msg["text"]
        for pattern in HONORIFIC_PATTERNS:
            matches = pattern.findall(text)
            if matches:
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
                    break

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
        if "예:" in line or "예시" in line:
            continue
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
        if line.startswith("## "):
            if current_project and sub_statuses:
                _check_project_consistency(current_project, sub_statuses, violations)
            match = re.match(r'## \[(.)\] (.+)', line)
            if match:
                current_project = {"status": match.group(1), "name": match.group(2), "line": line}
                sub_statuses = []
        elif re.match(r'\s+- \[(.)\]', line):
            match = re.match(r'\s+- \[(.)\]', line)
            if match:
                sub_statuses.append(match.group(1))

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

    allowed_sections = {"현재 환경", "대화 톤"}
    for line in lines:
        if line.startswith("## "):
            section = line.replace("## ", "").strip()
            if section not in allowed_sections:
                violations.append({
                    "type": "memory_policy",
                    "severity": "info",
                    "detail": f"메모리에 환경/톤 외 섹션 존재: '{section}' — 정책 확인 필요",
                })

    return violations


def check_session_records() -> list[dict]:
    """대화 기록 누락 점검"""
    violations = []
    conv_dir = PROJECT_ROOT / "tasks" / "conversations"
    raw_dir = conv_dir / "raw"

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


# === LLM 점검 (codex exec) ===

def is_codex_available() -> bool:
    """codex CLI 사용 가능 여부"""
    try:
        result = subprocess.run(
            ["codex", "--version"],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def call_codex(prompt: str, timeout: int = 120, model: str | None = None) -> str:
    """codex exec로 LLM 호출. 결과 텍스트를 반환한다."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False
    ) as f:
        output_path = f.name

    cmd = [
        "codex", "exec",
        "--sandbox", "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
    ]
    if model:
        cmd.extend(["-m", model])
    cmd.extend(["-o", output_path, "-"])  # stdin으로 프롬프트

    try:
        subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        result_path = Path(output_path)
        if result_path.exists():
            return result_path.read_text().strip()
        return ""
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return ""
    finally:
        Path(output_path).unlink(missing_ok=True)


LLM_CHECK_PROMPT_TEMPLATE = """너는 메타에이전트다. AI-사용자 대화가 아래 원칙을 준수하는지 점검하라.

## 원칙
{principles}

## 점검 항목
1. sycophancy — AI가 사용자 의견에 비판 없이 동의하는가? "좋은 생각이다" 류의 빈 동의가 있는가?
2. purpose_not_explored — AI가 표면적 작업(What)만 처리하고 궁극적 목적(Why)을 탐구하지 않는가?
3. no_proactive_suggestion — AI가 지시만 기다리고 후속 질문, 다음 단계를 선제적으로 제안하지 않는가?
4. role_boundary_violation — mirror-mind 세션이 코드 구현을 수행하는가? (설계·조율·의사결정만 해야 함. 단, mirror-mind 자체 운영 스크립트(check.py, query.py 등)는 예외)

## 대화 (최근 메시지)
{context}

## 출력
JSON 배열만 출력하라. 위반이 없으면 빈 배열 [].
각 항목: {{"check": "항목명", "severity": "warning", "detail": "구체적 위반 설명", "evidence": "근거 발췌(50자 이내)"}}
JSON 외 텍스트를 출력하지 마라."""


def check_with_codex(
    session_path: Path,
    model: str | None = None,
) -> list[dict]:
    """codex exec로 LLM 기반 점검 수행 (4개 항목 배치)"""
    context = read_conversation_context(session_path, last_n=20)
    if not context.strip():
        return []

    principle_path = PROJECT_ROOT / "mirror-mind-principle.md"
    principles = ""
    if principle_path.exists():
        principles = principle_path.read_text()[:1500]

    prompt = LLM_CHECK_PROMPT_TEMPLATE.format(
        principles=principles,
        context=context,
    )

    raw = call_codex(prompt, timeout=120, model=model)
    if not raw:
        return [{"type": "llm_check_error", "severity": "info",
                 "detail": "codex 호출 결과 없음 (타임아웃 또는 오류)"}]

    try:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            items = json.loads(match.group())
            return [{
                "type": f"llm_{item.get('check', 'unknown')}",
                "severity": item.get("severity", "warning"),
                "detail": item.get("detail", ""),
                "context": item.get("evidence", ""),
            } for item in items if isinstance(item, dict)]
    except (json.JSONDecodeError, Exception):
        return [{"type": "llm_check_error", "severity": "info",
                 "detail": f"codex 출력 파싱 실패: {raw[:200]}"}]

    return []


# === 리포트 ===

def run_checks(
    session_path: Path | None,
    after_line: int = 0,
    use_llm: bool = False,
    llm_model: str | None = None,
) -> dict:
    """전체 점검 실행"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "violations": [],
        "summary": {},
    }

    # 1. 톤 점검
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

    # 6. LLM 점검 (codex exec)
    if use_llm and session_path:
        llm_violations = check_with_codex(session_path, model=llm_model)
        report["violations"].extend(llm_violations)
        report["checks"]["llm"] = {"violations": len(llm_violations)}

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
            if "context" in v and v["context"]:
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


# === 실행 ===

def main():
    parser = argparse.ArgumentParser(description="메타에이전트: 원칙 준수 감시")
    parser.add_argument("--session", help="세션 ID (미지정 시 현재 세션)")
    parser.add_argument("--watch", action="store_true", help="파일 변경 감시 모드")
    parser.add_argument("--interval", type=int, default=60, help="감시 간격 (초, 기본 60)")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    parser.add_argument("--llm", action="store_true", help="LLM 점검 활성화 (codex exec)")
    parser.add_argument("--llm-model", help="LLM 모델 (기본: codex 기본값)")
    args = parser.parse_args()

    # codex 사용 가능 여부 확인
    use_llm = args.llm
    if use_llm and not is_codex_available():
        print("경고: codex CLI를 찾을 수 없음. LLM 점검 비활성화.", file=sys.stderr)
        use_llm = False

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
        last_llm_line_count = 0
        print(f"감시 시작: {session_path.name} (간격: {args.interval}초, LLM: {use_llm})",
              file=sys.stderr)
        while True:
            try:
                # 현재 파일 줄 수 확인
                with open(session_path) as f:
                    current_line_count = sum(1 for _ in f)

                # 새 메시지가 있을 때만 LLM 점검
                run_llm_this_cycle = use_llm and current_line_count > last_llm_line_count

                report = run_checks(
                    session_path,
                    after_line=last_line,
                    use_llm=run_llm_this_cycle,
                    llm_model=args.llm_model,
                )

                if args.json:
                    print(json.dumps(report, ensure_ascii=False))
                else:
                    print(format_report(report))
                sys.stdout.flush()

                last_line = current_line_count
                if run_llm_this_cycle:
                    last_llm_line_count = current_line_count

                time.sleep(args.interval)
            except KeyboardInterrupt:
                break
    else:
        report = run_checks(
            session_path,
            use_llm=use_llm,
            llm_model=args.llm_model,
        )
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(format_report(report))


if __name__ == "__main__":
    main()
