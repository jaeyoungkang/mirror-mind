#!/usr/bin/env python3
"""세션 종료 자동화

AGENTS.md '작업 종료' 트리거 절차를 스크립트로 수행한다.

사용법:
  python3 scripts/close-session.py                     # 전체 (raw 저장 + 초안 생성)
  python3 scripts/close-session.py --raw-only           # raw 저장만
  python3 scripts/close-session.py --no-llm             # codex 없이 raw 저장 + 빈 템플릿
  python3 scripts/close-session.py --name 세션20        # 세션 이름 직접 지정
  python3 scripts/close-session.py --dry-run            # 파일 미수정, stdout 출력만
  python3 scripts/close-session.py --commit             # 완료 후 자동 커밋

절차:
  1. 현재 세션 JSONL → tasks/conversations/raw/ 경량 내보내기
  2. 대화 텍스트 추출
  3. codex exec로 세션 노트 / decisions / episodes 초안 생성
  4. 파일 작성
  5. (--commit) git add + commit

주의: projects.md 업데이트는 수동. 스크립트가 마지막에 알려준다.
"""

import json
import sys
import re
import subprocess
import tempfile
import argparse
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
PROJECT_KEY = "-Users-jaeyoungkang-mirror-mind"

CONV_DIR = PROJECT_ROOT / "tasks" / "conversations"
RAW_DIR = CONV_DIR / "raw"
DECISIONS_FILE = PROJECT_ROOT / "tasks" / "decisions.md"
EPISODES_FILE = PROJECT_ROOT / "memory" / "episodes.json"
SESSION_MAP_FILE = RAW_DIR / ".session-map.json"

TRUNCATE_INPUT = 300
TRUNCATE_RESULT = 200


# ── 세션 탐색 + 중복 방지 ──

def find_current_session() -> Path | None:
    """가장 최근 수정된 JSONL = 현재 세션"""
    project_dir = CLAUDE_PROJECTS_DIR / PROJECT_KEY
    jsonls = list(project_dir.glob("*.jsonl"))
    if not jsonls:
        return None
    return max(jsonls, key=lambda p: p.stat().st_mtime)


def load_session_map() -> dict:
    """UUID → 세션 이름 매핑 로드"""
    if SESSION_MAP_FILE.exists():
        return json.loads(SESSION_MAP_FILE.read_text())
    return {}


def save_session_map(mapping: dict):
    SESSION_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_MAP_FILE.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n"
    )


def get_session_uuid(session_jsonl: Path) -> str:
    """JSONL 파일명에서 UUID 추출"""
    return session_jsonl.stem


def determine_session_name() -> str:
    """전체 raw 파일에서 가장 큰 세션 번호를 찾아 +1"""
    all_sessions = list(RAW_DIR.glob("*-세션*.jsonl"))
    max_num = 0
    for f in all_sessions:
        m = re.search(r'세션(\d+)', f.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"세션{max_num + 1}"


def check_already_closed(session_jsonl: Path) -> str | None:
    """이 JSONL이 이미 종료 처리됐으면 세션 이름을 반환, 아니면 None"""
    uuid = get_session_uuid(session_jsonl)
    mapping = load_session_map()
    return mapping.get(uuid)


def session_exists_in_episodes(session_key: str) -> bool:
    """episodes.json에 해당 세션의 에피소드가 이미 있는지"""
    if not EPISODES_FILE.exists():
        return False
    episodes = json.loads(EPISODES_FILE.read_text())
    return any(e.get("session") == session_key for e in episodes)


def session_exists_in_decisions(session_key: str) -> bool:
    """decisions.md에 해당 세션 참조가 이미 있는지"""
    if not DECISIONS_FILE.exists():
        return False
    text = DECISIONS_FILE.read_text()
    return session_key in text


# ── 경량 내보내기 (export-session.py 로직 재사용) ──

def _truncate(v, limit):
    s = str(v)
    return s[:limit] + "...[truncated]" if len(s) > limit else v


def _compact_input(inp):
    if not isinstance(inp, dict):
        return _truncate(inp, TRUNCATE_INPUT)
    return {k: _truncate(v, TRUNCATE_INPUT) for k, v in inp.items()}


def _compact_content(content):
    if not isinstance(content, list):
        return content
    compacted = []
    for block in content:
        if not isinstance(block, dict):
            compacted.append(block)
            continue
        t = block.get("type")
        if t == "text":
            compacted.append(block)
        elif t == "tool_use":
            compacted.append({
                "type": "tool_use",
                "name": block.get("name"),
                "input": _compact_input(block.get("input", {})),
            })
        elif t == "tool_result":
            raw = block.get("content", "")
            if isinstance(raw, list):
                raw = " ".join(
                    str(c.get("text", "")) for c in raw if isinstance(c, dict)
                )
            preview = str(raw)[:TRUNCATE_RESULT]
            if len(str(raw)) > TRUNCATE_RESULT:
                preview += "...[truncated]"
            compacted.append({
                "type": "tool_result",
                "tool_use_id": block.get("tool_use_id"),
                "content_preview": preview,
            })
        else:
            compacted.append(block)
    return compacted


def export_raw(session_jsonl: Path, session_name: str) -> tuple[Path, int]:
    """세션 JSONL → 경량 JSONL로 내보내기"""
    today = date.today().isoformat()
    dest = RAW_DIR / f"{today}-{session_name}.jsonl"
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(session_jsonl) as fin, open(dest, "w") as fout:
        for line in fin:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") not in ("user", "assistant", "system"):
                continue
            msg = record.get("message", {})
            compacted = {
                "timestamp": record.get("timestamp"),
                "type": record.get("type"),
                "role": msg.get("role", record.get("type")),
                "content": _compact_content(msg.get("content", "")),
            }
            fout.write(json.dumps(compacted, ensure_ascii=False) + "\n")
            count += 1

    return dest, count


# ── 대화 추출 ──

def extract_conversation(filepath: Path, max_chars: int = 15000) -> str:
    """JSONL에서 사람이 읽을 수 있는 대화 텍스트 추출"""
    lines = []
    total_chars = 0

    with open(filepath, encoding="utf-8") as f:
        for raw_line in f:
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            msg_type = record.get("type")

            if msg_type == "user":
                content = record.get("message", {}).get("content", "")
                if isinstance(content, str) and content.strip():
                    block = f"\n[사용자] {content.strip()}"
                    lines.append(block)
                    total_chars += len(block)

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
                full_text = "\n".join(t for t in texts if t.strip())
                if full_text:
                    if len(full_text) > 1500:
                        full_text = full_text[:1500] + "\n... (생략)"
                    block = f"\n[AI] {full_text}"
                    lines.append(block)
                    total_chars += len(block)

            if max_chars > 0 and total_chars >= max_chars:
                break

    return "\n".join(lines)


# ── codex 호출 ──

def call_codex(prompt: str, timeout: int = 180) -> str:
    """codex exec (read-only)로 LLM 호출"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_path = f.name

    cmd = [
        "codex", "exec",
        "--sandbox", "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
        "-o", output_path,
        "-",
    ]
    try:
        subprocess.run(
            cmd, input=prompt,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        result_path = Path(output_path)
        if result_path.exists():
            return result_path.read_text().strip()
        return ""
    except subprocess.TimeoutExpired:
        print("codex 타임아웃", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"codex 호출 실패: {e}", file=sys.stderr)
        return ""
    finally:
        Path(output_path).unlink(missing_ok=True)


# ── 포맷 참고용 기존 데이터 추출 ──

def get_decisions_example() -> str:
    """decisions.md 마지막 결정 1건을 포맷 참고용으로 추출"""
    if not DECISIONS_FILE.exists():
        return "(없음)"
    text = DECISIONS_FILE.read_text()
    sections = text.split("\n## ")
    if len(sections) >= 2:
        return "## " + sections[-1][:1500]
    return text[-1500:]


def get_episodes_example() -> str:
    """episodes.json 마지막 에피소드 1건을 포맷 참고용으로 추출"""
    if not EPISODES_FILE.exists():
        return "(없음)"
    episodes = json.loads(EPISODES_FILE.read_text())
    if episodes:
        return json.dumps(episodes[-1], ensure_ascii=False, indent=2)
    return "(없음)"


def get_last_episode_id() -> str:
    if not EPISODES_FILE.exists():
        return "s00-00"
    episodes = json.loads(EPISODES_FILE.read_text())
    return episodes[-1].get("id", "s00-00") if episodes else "s00-00"


# ── 초안 생성 ──

GENERATE_PROMPT = """너는 mirror-mind 프로젝트의 세션 종료 기록 담당이다.
아래 대화를 읽고 3가지 산출물을 생성하라.

## 세션 정보
- 세션: {date_session}
- 날짜: {today}

## 대화 내용
{conversation}

## 산출물 1: 세션 노트 (마크다운)
- 제목: # {date_session}
- 주요 논의 주제, 결정 사항, 다음 단계를 간결하게 정리
- ~다 체 사용

## 산출물 2: decisions.md 추가분
기존 포맷 참고:
```
{decisions_example}
```
- 이번 세션에서 내린 의사결정만 추출
- 결정이 없으면 "없음"
- 각 결정: ## 날짜 | 제목, > 원본 참조, ### 결정 사항 (번호 리스트), ### 근거 (번호 리스트)

## 산출물 3: episodes.json 추가분
기존 포맷 참고:
```json
{episodes_example}
```
- 마지막 ID: {last_episode_id} → 다음은 {next_prefix}-01부터
- session 값: "{date_session}"
- 에피소드 3~5건. 주요 활동 단위로 분할
- 필드: id, session, episode_index, activity_type, project, topic, summary, emotion, outcome, outcome_detail, relationship_type, milestone_key, scope, decision_refs, created_at

## 출력 형식
정확히 아래 구분자를 사용하라. 구분자 외의 텍스트는 없어야 한다.

===NOTES_START===
(세션 노트 마크다운)
===NOTES_END===

===DECISIONS_START===
(decisions.md 추가분 또는 "없음")
===DECISIONS_END===

===EPISODES_START===
(JSON 배열)
===EPISODES_END==="""


def generate_drafts(conversation: str, session_name: str) -> dict:
    today = date.today().isoformat()
    date_session = f"{today}-{session_name}"

    m = re.search(r'(\d+)', session_name)
    session_num = int(m.group(1)) if m else 1
    next_prefix = f"s{session_num:02d}"

    prompt = GENERATE_PROMPT.format(
        date_session=date_session,
        today=today,
        conversation=conversation,
        decisions_example=get_decisions_example(),
        episodes_example=get_episodes_example(),
        last_episode_id=get_last_episode_id(),
        next_prefix=next_prefix,
    )

    raw = call_codex(prompt, timeout=180)
    if not raw:
        return {"notes": "", "decisions": "", "episodes": []}

    result = {}

    notes_match = re.search(
        r'===NOTES_START===\n?(.*?)\n?===NOTES_END===', raw, re.DOTALL
    )
    result["notes"] = notes_match.group(1).strip() if notes_match else ""

    dec_match = re.search(
        r'===DECISIONS_START===\n?(.*?)\n?===DECISIONS_END===', raw, re.DOTALL
    )
    dec_text = dec_match.group(1).strip() if dec_match else ""
    result["decisions"] = "" if dec_text == "없음" else dec_text

    ep_match = re.search(
        r'===EPISODES_START===\n?(.*?)\n?===EPISODES_END===', raw, re.DOTALL
    )
    if ep_match:
        try:
            ep_text = ep_match.group(1).strip()
            arr_match = re.search(r'\[.*\]', ep_text, re.DOTALL)
            result["episodes"] = json.loads(arr_match.group()) if arr_match else []
        except (json.JSONDecodeError, Exception):
            result["episodes"] = []
    else:
        result["episodes"] = []

    return result


# ── 파일 쓰기 ──

def write_notes(notes: str, session_name: str) -> Path:
    today = date.today().isoformat()
    dest = CONV_DIR / f"{today}-{session_name}.md"
    dest.write_text(notes, encoding="utf-8")
    return dest


def append_decisions(decisions: str):
    if not decisions:
        return
    current = DECISIONS_FILE.read_text(encoding="utf-8")
    if not current.endswith("\n"):
        current += "\n"
    current += "\n" + decisions + "\n"
    DECISIONS_FILE.write_text(current, encoding="utf-8")


def append_episodes(new_episodes: list[dict]):
    if not new_episodes:
        return
    episodes = json.loads(EPISODES_FILE.read_text(encoding="utf-8"))
    episodes.extend(new_episodes)
    EPISODES_FILE.write_text(
        json.dumps(episodes, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def git_commit(session_name: str):
    today = date.today().isoformat()
    candidates = [
        f"tasks/conversations/raw/{today}-{session_name}.jsonl",
        f"tasks/conversations/{today}-{session_name}.md",
        "tasks/decisions.md",
        "memory/episodes.json",
    ]
    existing = [f for f in candidates if (PROJECT_ROOT / f).exists()]
    if not existing:
        return

    subprocess.run(["git", "add"] + existing, cwd=str(PROJECT_ROOT))
    msg = (
        f"docs: {session_name} — 세션 종료 기록\n\n"
        "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=str(PROJECT_ROOT))


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="세션 종료 자동화")
    parser.add_argument("--name", help="세션 이름 (예: 세션20). 미지정 시 자동 결정")
    parser.add_argument("--raw-only", action="store_true", help="raw 저장만")
    parser.add_argument("--no-llm", action="store_true", help="codex 없이 raw 저장 + 빈 템플릿")
    parser.add_argument("--commit", action="store_true", help="완료 후 자동 커밋")
    parser.add_argument("--dry-run", action="store_true", help="파일 미수정, stdout 출력만")
    parser.add_argument("--force", action="store_true", help="이미 종료된 세션도 강제 재실행")
    args = parser.parse_args()

    # 1. 세션 찾기
    session_jsonl = find_current_session()
    if not session_jsonl:
        print("현재 세션 JSONL을 찾을 수 없다", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    print(f"원본: {session_jsonl.name} ({session_jsonl.stat().st_size / 1024:.0f}KB)")

    # 2. 중복 체크
    already_closed_as = check_already_closed(session_jsonl)
    if already_closed_as and not args.force:
        print(f"\n이 세션은 이미 '{already_closed_as}'로 종료 처리됐다.", file=sys.stderr)
        print(f"  raw: tasks/conversations/raw/{already_closed_as}.jsonl", file=sys.stderr)
        print(f"재실행하려면 --force를 사용하라.", file=sys.stderr)
        sys.exit(1)

    if already_closed_as and args.force:
        # --force: 같은 세션 이름으로 재실행 (raw 덮어쓰기)
        session_name = args.name or already_closed_as.split("-")[-1]  # "세션19" 부분 추출
        # 날짜 부분도 기존 것에서 가져온다
        print(f"[force] 이미 종료된 세션 '{already_closed_as}'을 재실행한다")
    else:
        session_name = args.name or determine_session_name()

    date_session = f"{today}-{session_name}"
    print(f"세션: {date_session}")

    # 3. raw 경량 내보내기
    if not args.dry_run:
        raw_dest, count = export_raw(session_jsonl, session_name)
        size_kb = raw_dest.stat().st_size / 1024
        print(f"[완료] raw 저장 → {raw_dest.relative_to(PROJECT_ROOT)} ({count}건, {size_kb:.0f}KB)")

        # 세션 맵 업데이트
        mapping = load_session_map()
        mapping[get_session_uuid(session_jsonl)] = date_session
        save_session_map(mapping)
    else:
        print(f"[dry-run] raw 저장 → tasks/conversations/raw/{date_session}.jsonl")

    if args.raw_only:
        print("raw-only 모드 종료.")
        return

    # 4. 대화 추출
    print("\n대화 추출 중...")
    conversation = extract_conversation(session_jsonl, max_chars=15000)
    if not conversation.strip():
        print("대화 내용이 비어있다", file=sys.stderr)
        sys.exit(1)
    print(f"  추출: {len(conversation)}자")

    # 5. 초안 생성
    if args.no_llm:
        print("no-llm 모드. 빈 템플릿 생성.")
        drafts = {
            "notes": f"# {date_session}\n\n(TODO: 세션 노트 작성)\n",
            "decisions": "",
            "episodes": [],
        }
    else:
        print("codex로 초안 생성 중... (최대 3분)")
        drafts = generate_drafts(conversation, session_name)

    # 6. 결과 출력
    sep = "=" * 50
    print(f"\n{sep}")
    print("=== 세션 노트 ===")
    print(drafts["notes"] or "(없음)")

    print(f"\n=== decisions.md 추가분 ===")
    print(drafts["decisions"] or "(결정 없음)")

    print(f"\n=== episodes.json 추가분 ({len(drafts['episodes'])}건) ===")
    if drafts["episodes"]:
        print(json.dumps(drafts["episodes"], ensure_ascii=False, indent=2))
    else:
        print("(에피소드 없음)")
    print(sep)

    # 7. 파일 쓰기 (중복 체크 포함)
    if args.dry_run:
        print("\n[dry-run] 파일 미수정. 위 내용을 확인 후 --dry-run 없이 재실행.")
        return

    if drafts["notes"]:
        notes_dest = write_notes(drafts["notes"], session_name)
        print(f"\n[완료] 세션 노트 → {notes_dest.relative_to(PROJECT_ROOT)}")

    if drafts["decisions"]:
        if session_exists_in_decisions(date_session) and not args.force:
            print("[건너뜀] decisions.md에 이 세션 기록이 이미 존재한다")
        else:
            append_decisions(drafts["decisions"])
            print("[완료] decisions.md 업데이트")

    if drafts["episodes"]:
        if session_exists_in_episodes(date_session) and not args.force:
            print("[건너뜀] episodes.json에 이 세션 에피소드가 이미 존재한다")
        else:
            append_episodes(drafts["episodes"])
            print(f"[완료] episodes.json에 {len(drafts['episodes'])}건 추가")

    # 8. 알림
    print("\n[수동] projects.md 업데이트 필요 여부 확인하라")

    # 9. 커밋
    if args.commit:
        git_commit(session_name)
        print("[완료] git commit")
    else:
        print("[알림] --commit 플래그로 자동 커밋 가능")


if __name__ == "__main__":
    main()
