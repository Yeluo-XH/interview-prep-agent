import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("store", Path(__file__).resolve().parents[1] / "scripts/interview_store.py")
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = store.init(self.tmp.name, "后端工程师")
        store.set_stage(self.state, "jd", {"items": [{"id":"R01", "requirement":"数据库", "evidence":"掌握 MySQL", "kind":"must"}]})
        store.set_stage(self.state, "questions", {"items": [{"id":"Q01", "question":"如何设计索引？", "requirement_ids":["R01"]}, {"id":"Q02", "question":"如何排查慢查询？", "requirement_ids":["R01"]}]})

    def answer(self, score=3):
        return {"question_id":"Q01", "answer":"先看访问模式，再通过执行计划验证。", "scores":{k:score for k in store.WEIGHTS}, "rationale":{k:"回答中的执行计划说明验证路径" for k in store.WEIGHTS}, "optimized_answer":"我会先确认查询模式，再用执行计划验证。"}

    def test_weighted_score(self):
        data = self.answer()
        data["scores"].update(correctness=4, depth=2)
        result = store.add_answer(self.state, data)
        self.assertEqual(result["total"], 78.75)

    def test_latest_attempt_and_skip_excluded(self):
        store.add_answer(self.state, self.answer(1))
        store.add_answer(self.state, self.answer(4))
        store.add_answer(self.state, {"question_id":"Q02", "status":"skipped"})
        summary = store.summarize(self.state)
        self.assertEqual((summary["average"], summary["scored_questions"], summary["skipped_questions"]), (100, 1, 1))
        self.assertEqual(len(self.state["answers"]), 3)
        self.assertEqual(self.state["answers"][1]["attempt"], 2)

    def test_no_score_for_no_answers(self):
        self.assertIsNone(store.summarize(self.state)["average"])
        self.assertEqual(store.summarize(self.state)["unanswered_ids"], ["Q01", "Q02"])

    def test_invalid_score_and_empty_answer_rejected(self):
        for value in (float("nan"), float("inf"), True, -1, 5):
            data = self.answer(); data["scores"]["correctness"] = value
            with self.assertRaises(ValueError): store.add_answer(self.state, data)
        data = self.answer(); data["answer"] = " "
        with self.assertRaises(ValueError): store.add_answer(self.state, data)
        self.assertEqual(self.state["answers"], [])

    def test_bad_question_and_requirement_rejected(self):
        data = self.answer(); data["question_id"] = "UNKNOWN"
        with self.assertRaises(ValueError): store.add_answer(self.state, data)
        with self.assertRaises(ValueError): store.set_stage(self.state, "questions", {"items":[{"id":"Q01", "question":"索引？", "requirement_ids":["R99"]}]})

    def test_path_traversal_rejected(self):
        for name in ("../outside", "a/b", "a\\b", "D:\\test"):
            with self.assertRaises(ValueError): store.session_path(self.tmp.name, name)

    def test_atomic_persistence_and_lock(self):
        path = store.session_path(self.tmp.name, self.state["id"])
        store.write_json(path, self.state)
        self.assertEqual(store.read_json(path), self.state)
        with store.locked(path):
            with self.assertRaises(ValueError):
                with store.locked(path): pass
        self.assertFalse((path.parent / ".write.lock").exists())

    def test_chinese_search_and_unknown(self):
        knowledge = Path(__file__).resolve().parents[1] / "knowledge"
        result = store.search("数据库 索引", [knowledge])
        self.assertEqual(result["results"][0]["card"]["id"], "db-index")
        self.assertEqual(store.search("不存在的专题xyz987", [knowledge])["matched"], 0)


if __name__ == "__main__":
    unittest.main()
