import json
import unittest

from puzzle_agent.paper_puzzle.components.rule_based import (
    RulePuzzleError,
    replay_trace,
    solve_rule_puzzle,
    synthesize_program,
    validate_program,
    validate_source,
)


def source_fixture():
    return {
        "rules": [
            {"id": "r1", "text": "每行每列都使用 1 到 4，且不重复。"},
            {"id": "r2", "text": "小于号两侧数字满足左小右大。"},
        ],
        "symbols": [1, 2, 3, 4],
        "entities": [
            {
                "id": f"R{row}C{column}", "label": f"第{row}行第{column}列",
                "row": row - 1, "column": column - 1,
                "value": 1 if (row, column) == (1, 1) else None,
            }
            for row in range(1, 5) for column in range(1, 5)
        ],
        "clues": [{
            "id": "c1", "text": "R1C1 < R1C2", "entity_ids": ["R1C1", "R1C2"],
        }],
        "display": {"type": "grid", "rows": 4, "columns": 4},
    }


def program_fixture():
    rows = [{
        "id": f"row-{row}", "type": "all_different",
        "variables": [f"R{row}C{column}" for column in range(1, 5)],
        "complete_set": True, "source_rule_ids": ["r1"], "source_clue_ids": [],
    } for row in range(1, 5)]
    columns = [{
        "id": f"column-{column}", "type": "all_different",
        "variables": [f"R{row}C{column}" for row in range(1, 5)],
        "complete_set": True, "source_rule_ids": ["r1"], "source_clue_ids": [],
    } for column in range(1, 5)]
    return {
        "method_summary": "先传播行列不重复，再应用不等式支持剪枝。",
        "strategy_order": [
            "given_propagation", "all_different_elimination",
            "all_different_hidden_single", "less_than_support",
        ],
        "constraints": rows + columns + [{
            "id": "lt-c1", "type": "less_than", "variables": ["R1C1", "R1C2"],
            "source_rule_ids": ["r2"], "source_clue_ids": ["c1"],
        }],
        "coverage": {"rule_ids": ["r1", "r2"], "clue_ids": ["c1"]},
    }


class RuleBasedContractsTests(unittest.TestCase):
    def test_source_and_program_are_strict_bounded_and_provenance_complete(self):
        source = validate_source(source_fixture())
        program = validate_program(source, program_fixture())
        self.assertEqual(len(source["entities"]), 16)
        self.assertEqual(program["constraints"][-1]["type"], "less_than")

        injected = program_fixture()
        injected["python"] = "open('/tmp/pwned','w').write('x')"
        with self.assertRaisesRegex(RulePuzzleError, "unknown fields|arbitrary code"):
            validate_program(source, injected)

        missing_coverage = program_fixture()
        missing_coverage["coverage"]["clue_ids"] = []
        with self.assertRaisesRegex(RulePuzzleError, "coverage"):
            validate_program(source, missing_coverage)

        dangling = program_fixture()
        dangling["constraints"][-1]["variables"] = ["R1C1", "NOT_A_CELL"]
        with self.assertRaisesRegex(RulePuzzleError, "unknown entit"):
            validate_program(source, dangling)

    def test_method_synthesis_is_a_separate_fail_closed_call_without_answer_field(self):
        class Provider:
            def __init__(self, output):
                self.output = output
                self.messages = None

            def complete(self, messages):
                self.messages = messages
                return self.output

        provider = Provider(json.dumps(program_fixture(), ensure_ascii=False))
        result = synthesize_program(source_fixture(), provider)
        self.assertEqual(result["method_summary"], program_fixture()["method_summary"])
        prompt = json.dumps(provider.messages, ensure_ascii=False)
        self.assertIn("METHOD_SYNTHESIS", prompt)
        self.assertNotIn("expected-result", prompt)
        self.assertNotIn('"answer"', json.dumps(result))

        with self.assertRaisesRegex(RulePuzzleError, "valid JSON"):
            synthesize_program(source_fixture(), Provider("not-json"))


def latin_source(givens=None, clues=None):
    givens = givens or {}
    return {
        "rules": [
            {"id": "r1", "text": "每行每列恰好使用 1、2、3、4 且不重复。"},
            {"id": "r2", "text": "可见不等号满足尖端一侧较小；楼房提示表示从该方向可见的数量。"},
        ],
        "symbols": [1, 2, 3, 4],
        "entities": [
            {
                "id": f"R{row}C{column}", "label": f"R{row}C{column}",
                "row": row - 1, "column": column - 1,
                "value": givens.get(f"R{row}C{column}"),
            }
            for row in range(1, 5) for column in range(1, 5)
        ],
        "clues": clues or [{
            "id": "c1", "text": "R1C1 < R1C2", "entity_ids": ["R1C1", "R1C2"],
        }],
        "display": {"type": "grid", "rows": 4, "columns": 4},
    }


def latin_constraints():
    return ([{
        "id": f"row-{row}", "type": "all_different",
        "variables": [f"R{row}C{column}" for column in range(1, 5)],
        "complete_set": True, "source_rule_ids": ["r1"], "source_clue_ids": [],
    } for row in range(1, 5)] + [{
        "id": f"column-{column}", "type": "all_different",
        "variables": [f"R{row}C{column}" for row in range(1, 5)],
        "complete_set": True, "source_rule_ids": ["r1"], "source_clue_ids": [],
    } for column in range(1, 5)])


class RuleBasedEngineTests(unittest.TestCase):
    def test_one_engine_solves_futoshiki_kakuro_and_skyscrapers_without_search(self):
        futoshiki_source = latin_source({
            "R1C1": 1, "R1C3": 3, "R1C4": 4,
            "R2C1": 3, "R2C2": 4, "R2C3": 1,
            "R3C2": 1, "R3C3": 4, "R3C4": 3,
            "R4C1": 4, "R4C2": 3, "R4C4": 1,
        })
        futoshiki_program = {
            "method_summary": "交替应用行列唯一性与不等式支持。",
            "strategy_order": [
                "given_propagation", "all_different_elimination",
                "all_different_hidden_single", "less_than_support",
            ],
            "constraints": latin_constraints() + [{
                "id": "lt-c1", "type": "less_than", "variables": ["R1C1", "R1C2"],
                "source_rule_ids": ["r2"], "source_clue_ids": ["c1"],
            }],
            "coverage": {"rule_ids": ["r1", "r2"], "clue_ids": ["c1"]},
        }
        futoshiki = solve_rule_puzzle(futoshiki_source, futoshiki_program)
        self.assertEqual(futoshiki["status"], "SOLVED")
        self.assertTrue(any(step["technique"].startswith("all_different") for step in futoshiki["steps"]))

        kakuro_source = {
            "rules": [{"id": "r1", "text": "每个连续白格组使用 1 到 4 的互异数字，并等于提示和。"}],
            "symbols": [1, 2, 3, 4],
            "entities": [
                {"id": item, "label": item, "value": None}
                for item in ("A", "B", "C", "D")
            ],
            "clues": [
                {"id": "c1", "text": "A+B=4", "entity_ids": ["A", "B"]},
                {"id": "c2", "text": "A+C=3", "entity_ids": ["A", "C"]},
                {"id": "c3", "text": "B+D=7", "entity_ids": ["B", "D"]},
            ],
        }
        kakuro_program = {
            "method_summary": "按交叉和值约束反复保留有支持的候选。",
            "strategy_order": ["given_propagation", "sum_support"],
            "constraints": [
                {"id": "sum-c1", "type": "sum_equals", "variables": ["A", "B"], "target": 4, "distinct": True, "source_rule_ids": ["r1"], "source_clue_ids": ["c1"]},
                {"id": "sum-c2", "type": "sum_equals", "variables": ["A", "C"], "target": 3, "distinct": True, "source_rule_ids": ["r1"], "source_clue_ids": ["c2"]},
                {"id": "sum-c3", "type": "sum_equals", "variables": ["B", "D"], "target": 7, "distinct": True, "source_rule_ids": ["r1"], "source_clue_ids": ["c3"]},
            ],
            "coverage": {"rule_ids": ["r1"], "clue_ids": ["c1", "c2", "c3"]},
        }
        kakuro = solve_rule_puzzle(kakuro_source, kakuro_program)
        self.assertEqual(kakuro["status"], "SOLVED")
        self.assertEqual(kakuro["values"], {"A": 1, "B": 3, "C": 2, "D": 4})
        self.assertTrue(all(step["technique"] == "sum_support" for step in kakuro["steps"]))

        solution = [
            [1, 2, 3, 4], [2, 3, 4, 1], [3, 4, 1, 2], [4, 1, 2, 3],
        ]
        def visible(line):
            highest = count = 0
            for value in line:
                if value > highest:
                    highest, count = value, count + 1
            return count
        clues = []
        visibility_constraints = []
        for axis in ("row", "column"):
            for index in range(4):
                line = solution[index] if axis == "row" else [solution[row][index] for row in range(4)]
                variables = (
                    [f"R{index + 1}C{column}" for column in range(1, 5)]
                    if axis == "row" else [f"R{row}C{index + 1}" for row in range(1, 5)]
                )
                for side, ordered in (("forward", variables), ("reverse", list(reversed(variables)))):
                    clue_id = f"{axis}-{index + 1}-{side}"
                    target = visible(line if side == "forward" else list(reversed(line)))
                    clues.append({"id": clue_id, "text": f"{clue_id}={target}", "entity_ids": ordered})
                    visibility_constraints.append({
                        "id": f"vis-{clue_id}", "type": "visibility", "variables": ordered,
                        "target": target, "source_rule_ids": ["r2"], "source_clue_ids": [clue_id],
                    })
        skyscraper_source = latin_source(clues=clues)
        skyscraper_program = {
            "method_summary": "先按每侧可见数量过滤整行候选，再传播行列唯一性。",
            "strategy_order": [
                "given_propagation", "visibility_support",
                "all_different_elimination", "all_different_hidden_single",
            ],
            "constraints": latin_constraints() + visibility_constraints,
            "coverage": {"rule_ids": ["r1", "r2"], "clue_ids": [item["id"] for item in clues]},
        }
        skyscraper = solve_rule_puzzle(skyscraper_source, skyscraper_program)
        self.assertEqual(skyscraper["status"], "SOLVED")
        self.assertEqual(skyscraper["grid"], solution)
        self.assertTrue(any(step["technique"] == "visibility_support" for step in skyscraper["steps"]))

    def test_next_step_trace_replays_and_constraint_budget_fails_closed(self):
        source = latin_source({
            "R1C1": 1, "R1C3": 3, "R1C4": 4,
            "R2C1": 3, "R2C2": 4, "R2C3": 1,
            "R3C2": 1, "R3C3": 4, "R3C4": 3,
            "R4C1": 4, "R4C2": 3, "R4C4": 1,
        })
        program = program_fixture()
        step = solve_rule_puzzle(source, program, max_steps=1)
        self.assertEqual(step["status"], "STEP_LIMIT")
        self.assertEqual(len(step["steps"]), 1)
        self.assertIn("before_fingerprint", step["steps"][0])
        self.assertIn("after_fingerprint", step["steps"][0])
        self.assertTrue(step["steps"][0]["rule_ids"])
        replayed = replay_trace(source, program, step["steps"])
        self.assertEqual(replayed["state_fingerprint"], step["state_fingerprint"])

        explosive_source = {
            "rules": [{"id": "r", "text": "十个变量的总和为 50。"}],
            "symbols": list(range(1, 11)),
            "entities": [{"id": f"X{i}", "label": f"X{i}", "value": None} for i in range(10)],
            "clues": [{"id": "c", "text": "总和 50", "entity_ids": [f"X{i}" for i in range(10)]}],
        }
        explosive_program = {
            "method_summary": "检查总和支持。", "strategy_order": ["sum_support"],
            "constraints": [{
                "id": "sum", "type": "sum_equals", "variables": [f"X{i}" for i in range(10)],
                "target": 50, "distinct": False, "source_rule_ids": ["r"], "source_clue_ids": ["c"],
            }],
            "coverage": {"rule_ids": ["r"], "clue_ids": ["c"]},
        }
        with self.assertRaisesRegex(RulePuzzleError, "candidate budget"):
            solve_rule_puzzle(explosive_source, explosive_program)


if __name__ == "__main__":
    unittest.main()
