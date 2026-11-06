"""Local interview persistence, scoring and retrieval. Standard library only."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid

WEIGHTS = {"correctness": 35, "relevance": 20, "depth": 20, "evidence": 15, "structure": 10}
ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".interview-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def required_text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} 必须是非空文字")
    return value.strip()


def identifier(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("ID 只允许字母、数字、下划线和连字符，最长 80 字符")
    return value


def session_path(root, session):
    root = Path(root).resolve()
    target = root / identifier(session)
    if target.is_symlink() or target.resolve().parent != root:
        raise ValueError("会话目录不能通过链接跳出数据目录")
    return target / "state.json"


@contextmanager
def locked(path):
    lock = path.parent / ".write.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError("会话正被写入；请稍后重试。若前次进程异常退出，请确认无写入后手动删除 .write.lock") from None
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def init(root, title):
    session = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    path = session_path(root, session)
    state = {"version": 1, "id": session, "title": required_text(title, "title"),
             "created_at": now(), "updated_at": now(), "stage": "intake", "status": "active",
             "jd": None, "gaps": None, "questions": None, "answers": [], "summary": None}
    with locked(path):
        write_json(path, state)
    return state


def validate_items(stage, data):
    if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not data["items"]:
        raise ValueError("阶段数据必须为含非空 items 数组的 JSON 对象")
    seen = set()
    for item in data["items"]:
        if not isinstance(item, dict):
            raise ValueError("items 每项必须是对象")
        key = identifier(item.get("id"))
        if key in seen:
            raise ValueError(f"重复 ID: {key}")
        seen.add(key)
        if stage == "jd":
            required_text(item.get("requirement"), "requirement")
            required_text(item.get("evidence"), "evidence")
            if item.get("kind") not in ("must", "preferred", "inferred"):
                raise ValueError("JD kind 仅允许 must/preferred/inferred")
        elif stage == "gaps":
            required_text(item.get("requirement_id"), "requirement_id")
            if item.get("status") not in ("supported", "insufficient", "unmentioned", "confirmed-gap"):
                raise ValueError("gap status 仅允许 supported/insufficient/unmentioned/confirmed-gap")
        else:
            required_text(item.get("question"), "question")
            if not isinstance(item.get("requirement_ids"), list):
                raise ValueError("题目必须有 requirement_ids 数组（通用题允许为空）")
    return data


def set_stage(state, stage, data):
    validate_items(stage, data)
    requirements = {item["id"] for item in (state.get("jd") or {}).get("items", [])}
    if stage in ("gaps", "questions"):
        for item in data["items"]:
            refs = [item["requirement_id"]] if stage == "gaps" else item["requirement_ids"]
            if any(not isinstance(ref, str) or ref not in requirements for ref in refs):
                raise ValueError("需求引用不存在；请先保存 JD 或让通用题 requirement_ids 为空")
    if stage in ("jd", "gaps") and state.get("questions"):
        raise ValueError("题库已建立；修改岗位/差距请创建新会话，以保留题目与需求映射")
    if stage == "questions" and state["answers"]:
        raise ValueError("已有作答，不能替换题库；请创建新会话")
    state[stage] = data
    state["stage"] = stage
    state["status"] = "active"
    return state


def add_answer(state, data):
    if not isinstance(data, dict):
        raise ValueError("回答必须为 JSON 对象")
    qid = identifier(data.get("question_id"))
    if not any(q["id"] == qid for q in (state.get("questions") or {}).get("items", [])):
        raise ValueError("question_id 不在当前题库")
    status = data.get("status", "answered")
    if status not in ("answered", "skipped"):
        raise ValueError("status 仅允许 answered/skipped")
    record = {"question_id": qid, "status": status, "at": now(),
              "attempt": 1 + sum(a["question_id"] == qid for a in state["answers"])}
    if status == "answered":
        record["answer"] = required_text(data.get("answer"), "answer")
        scores, rationale = data.get("scores"), data.get("rationale")
        if not isinstance(scores, dict) or set(scores) != set(WEIGHTS):
            raise ValueError("scores 必须包含且仅包含五个评分维度")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 or v > 4 for v in scores.values()):
            raise ValueError("每个维度须为 0 到 4 的有限数值")
        if not isinstance(rationale, dict) or any(not isinstance(rationale.get(k), str) or not rationale[k].strip() for k in WEIGHTS):
            raise ValueError("每个评分维度必须有证据和原因")
        record.update({"scores": dict(scores), "rationale": dict(rationale),
                       "total": round(sum(scores[k] * w / 4 for k, w in WEIGHTS.items()), 2),
                       "improvements": data.get("improvements", []),
                       "optimized_answer": required_text(data.get("optimized_answer"), "optimized_answer"),
                       "followup": data.get("followup", "")})
        if not isinstance(record["improvements"], list) or any(not isinstance(x, str) for x in record["improvements"]):
            raise ValueError("improvements 必须为文字数组")
    state["answers"].append(record)
    state.update(stage="mock", status="active", summary=None)
    return record


def summarize(state):
    latest = {a["question_id"]: a for a in state["answers"]}
    scored = [a for a in latest.values() if a["status"] == "answered"]
    questions = (state.get("questions") or {}).get("items", [])
    return {"scored_questions": len(scored), "skipped_questions": sum(a["status"] == "skipped" for a in latest.values()),
            "unanswered_ids": [q["id"] for q in questions if q["id"] not in latest],
            "average": round(sum(a["total"] for a in scored) / len(scored), 2) if scored else None,
            "weights": WEIGHTS, "basis": "每题最新回答；跳过和未答题不计入均分", "finished_at": now()}


def search(query, directories, limit=8):
    # Latin terms are whole words; Chinese bigrams support multi-word queries.
    tokens = set(re.findall(r"[a-z0-9+#.]+", query.lower()))
    for phrase in re.findall(r"[\u4e00-\u9fff]+", query):
        tokens.update(phrase[i:i+2] for i in range(len(phrase)-1))
        if len(phrase) == 1:
            tokens.add(phrase)
    if not tokens:
        raise ValueError("请输入有效知识关键词")
    results = []
    for directory in directories:
        directory = Path(directory).resolve(strict=True)
        for file in sorted(directory.glob("*.json")):
            if file.resolve().parent != directory:
                raise ValueError("知识文件不能通过链接跳出指定目录")
            data = read_json(file)
            if not isinstance(data, list):
                raise ValueError(f"知识文件必须是数组: {file.name}")
            for card in data:
                tags = " ".join(card.get("tags", [])).lower()
                # Match topic labels, not incidental words in caveats or URLs.
                score = sum(1 for t in tokens if t in tags)
                if score:
                    results.append({"score": score, "file": str(file), "card": card})
    results.sort(key=lambda r: (-r["score"], r["card"].get("id", "")))
    return {"query": query, "matched": len(results), "results": results[:limit], "source_status": "本地学习摘要，未重新联网验证"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="interview-data", help="本地会话数据目录")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("--title", required=True)
    for name in ("show", "set", "answer", "finish", "pause"):
        p = sub.add_parser(name); p.add_argument("--session", required=True)
        if name == "set":
            p.add_argument("--stage", choices=["jd", "gaps", "questions"], required=True)
        if name in ("set", "answer"):
            p.add_argument("--file", required=True, help="UTF-8 JSON 输入文件")
    sub.add_parser("list")
    p = sub.add_parser("search"); p.add_argument("--query", required=True)
    p.add_argument("--knowledge", action="append", default=None)
    p.add_argument("--limit", type=int, choices=range(1, 21), default=8)
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = init(args.root, args.title)
        elif args.command == "search":
            result = search(args.query, args.knowledge or [Path(__file__).resolve().parents[1] / "knowledge"], args.limit)
        elif args.command == "list":
            result = [{k: state[k] for k in ("id", "title", "stage", "status", "updated_at")} for state in
                      (read_json(p) for p in sorted(Path(args.root).glob("*/state.json"))) ]
        else:
            path = session_path(args.root, args.session)
            if args.command == "show":
                result = read_json(path)
            else:
                with locked(path):
                    state = read_json(path)
                    if args.command == "set":
                        set_stage(state, args.stage, read_json(args.file))
                    elif args.command == "answer":
                        add_answer(state, read_json(args.file))
                    elif args.command == "pause":
                        state["status"] = "paused"
                    else:
                        state["summary"] = summarize(state)
                        state.update(status="finished", stage="review")
                    state["updated_at"] = now()
                    write_json(path, state)
                    result = state
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(1, f"【需要你操作】本地数据操作未完成：{exc}\n")


if __name__ == "__main__":
    main()
