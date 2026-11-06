"""Exercise the real CLI with synthetic fixtures; no model, account or network required."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[1]


def run_demo(output):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    def cli(*arguments):
        result = subprocess.run(
            [sys.executable, str(REPO / "scripts/interview_store.py"), "--root", str(output), *arguments],
            check=True, capture_output=True, text=True, encoding="utf-8",
            env={**__import__("os").environ, "PYTHONUTF8": "1"},
        )
        return json.loads(result.stdout)

    session = cli("init", "--title", "Synthetic backend interview demo")["id"]
    for stage, filename in [("jd", "jd.json"), ("gaps", "gaps.json"), ("questions", "questions.json")]:
        cli("set", "--session", session, "--stage", stage, "--file", str(REPO / "examples" / filename))
    cli("answer", "--session", session, "--file", str(REPO / "examples/evaluation.json"))
    saved = cli("pause", "--session", session)
    if saved["status"] != "paused":
        raise RuntimeError("Pause state was not persisted")
    # This is a skipped example, not a zero-scored answer.
    skip_file = output / (session + "-skip.json")
    try:
        skip_file.write_text(json.dumps({"question_id": "Q02", "status": "skipped"}), encoding="utf-8")
        cli("answer", "--session", session, "--file", str(skip_file))
    finally:
        skip_file.unlink(missing_ok=True)
    final = cli("finish", "--session", session)
    summary = final["summary"]
    if summary["average"] != 78.75 or summary["scored_questions"] != 1 or summary["skipped_questions"] != 1:
        raise RuntimeError("Demo scoring did not match the fixture")
    if cli("show", "--session", session)["status"] != "finished":
        raise RuntimeError("Final state was not persisted")
    print("PASS: JD -> gaps -> questions -> answer -> pause -> skip -> finish")
    print("Score: 78.75 / 100; scored: 1; skipped: 1")
    print("Synthetic fixtures and manual example ratings only. No model or microphone was used.")
    return session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Optional directory in which to keep demo state")
    args = parser.parse_args()
    if args.output:
        session = run_demo(args.output)
        print("Saved:", Path(args.output).resolve() / session / "state.json")
    else:
        with tempfile.TemporaryDirectory(prefix="interview-demo-") as directory:
            run_demo(directory)


if __name__ == "__main__":
    main()
