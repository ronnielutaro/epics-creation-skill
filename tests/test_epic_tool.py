import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("epic_tool", ROOT / "scripts" / "epic_tool.py")
assert SPEC and SPEC.loader
epic_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(epic_tool)


class EpicToolTests(unittest.TestCase):
    def load_example(self):
        return json.loads((ROOT / "references" / "epic-plan.example.json").read_text(encoding="utf-8"))

    def test_example_is_valid_and_has_expected_graph(self):
        summary = epic_tool.validate_plan(self.load_example())
        self.assertEqual(summary["issue_count"], 3)
        self.assertEqual(summary["internal_dependency_count"], 2)

    def test_cycle_is_rejected(self):
        plan = self.load_example()
        plan["phases"][0]["issues"][0]["blocked_by"] = ["certification"]
        with self.assertRaisesRegex(epic_tool.PlanError, "later-phase|Dependency cycle"):
            epic_tool.validate_plan(plan)

    def test_unknown_blocker_is_rejected(self):
        plan = self.load_example()
        plan["phases"][1]["issues"][0]["blocked_by"] = ["missing-contract"]
        with self.assertRaisesRegex(epic_tool.PlanError, "unknown blocker key"):
            epic_tool.validate_plan(plan)

    def test_render_contains_parent_children_and_dependencies(self):
        plan = self.load_example()
        state = {
            "epic": {"number": 10, "url": "https://github.com/acme/storefront/issues/10"},
            "issues": {
                "contract": {"number": 11, "url": "https://github.com/acme/storefront/issues/11"},
                "implementation": {"number": 12, "url": "https://github.com/acme/storefront/issues/12"},
                "certification": {"number": 13, "url": "https://github.com/acme/storefront/issues/13"},
            },
        }
        rendered = epic_tool.render_all(plan, state)
        self.assertIn("#11", rendered["epic.md"])
        child = rendered["children/phase-1--implementation.md"]
        self.assertIn("Parent: #10", child)
        self.assertIn("Blocked by: #11", child)

    def test_render_command_writes_manifest(self):
        plan = self.load_example()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            epic_tool.write_rendered(plan, output)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["plan_key"], "checkout-reliability")
            self.assertTrue((output / "epic.md").exists())
            self.assertEqual(len(manifest["files"]), 4)

    def test_apply_requires_exact_repository_confirmation_before_preflight(self):
        plan = self.load_example()
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaisesRegex(epic_tool.PlanError, "confirm-repository"):
                epic_tool.apply_plan(
                    plan_path,
                    plan,
                    Path(directory) / "state.json",
                    "wrong/repository",
                )


if __name__ == "__main__":
    unittest.main()
