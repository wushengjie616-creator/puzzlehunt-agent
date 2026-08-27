from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_complex_runtime_is_optional_and_base_stays_dependency_free(self):
        with (ROOT / "pyproject.toml").open("rb") as handle:
            project = tomllib.load(handle)["project"]

        self.assertEqual(project["dependencies"], [])
        complex_dependencies = project.get("optional-dependencies", {}).get("complex")
        self.assertIsInstance(complex_dependencies, list)
        if not isinstance(complex_dependencies, list):
            return
        self.assertTrue(any(item.startswith("langgraph>=") for item in complex_dependencies))
        self.assertTrue(any(item.startswith("langgraph-checkpoint-sqlite>=") for item in complex_dependencies))


if __name__ == "__main__":
    unittest.main()
