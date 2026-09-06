"""Run the complete tools suite with/without the new correction, without editing fixtures."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "analysis/successor258-unit-baseline-comparison.json"
EXPECTED_FAILURES = {
    "test_name_token_help.NameTokenHelpTests.test_exact_approved_replacements_and_layout",
    "test_name_token_help.NameTokenHelpTests.test_user_saved_edits_untouched",
    "test_narration_editor_status.NarrationEditorStatusTests.test_accepted_line_reports_actual_width_and_safe_limit",
    "test_narration_editor_status.NarrationEditorStatusTests.test_dynamic_name_width_comes_from_the_same_core_model",
    "test_narration_editor_status.NarrationEditorStatusTests.test_first_line_indent_is_checked_before_encoding",
    "test_native_name_widths.NativeNameWidths.test_first_line_cannot_use_the_indentation_cell_for_text",
    "test_scenario_number_centering.NumberTests.test_final_population_and_preservation",
    "test_scenario_number_centering.NumberTests.test_literal_and_padded_dictionary_have_same_center",
}
EXPECTED_ERRORS = {"test_reference_glyph_repairs.RepairsTests.test_exact_seventeen_changes_and_no_other_fields"}


def child(variant):
    sys.path[:0] = [str(ROOT / "dialogue_editor"), str(ROOT / "tools")]
    import dialogue_core as core
    loader = core.load_json

    def baseline(path):
        value = loader(path)
        if Path(path).name == "dialogue_user_corrections.json":
            return {**value, "corrections": {}}
        return value

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tools"), pattern="test_*.py")
    # The new before/after test intentionally exercises both versions itself;
    # keep its real loader even in the baseline run.
    def flatten(group):
        for item in group:
            if isinstance(item, unittest.TestSuite):
                yield from flatten(item)
            else:
                yield item
    tests = list(flatten(suite))
    old_tests = unittest.TestSuite(t for t in tests if not t.id().startswith("test_leard_user_correction."))
    new_tests = unittest.TestSuite(t for t in tests if t.id().startswith("test_leard_user_correction."))
    output = io.StringIO()
    runner = unittest.TextTestRunner(stream=output, verbosity=1)
    with patch.object(core, "load_json", side_effect=baseline if variant == "baseline" else loader):
        result = runner.run(old_tests)
    addition = runner.run(new_tests)
    def details(name):
        return [{"test": t.id(), "traceback": tb}
                for r in (result, addition) for t, tb in getattr(r, name)]
    print(json.dumps({"variant": variant, "tests": result.testsRun + addition.testsRun,
                      "failures": details("failures"), "errors": details("errors"),
                      "skipped": len(result.skipped) + len(addition.skipped)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("baseline", "current"))
    args = parser.parse_args()
    if args.variant:
        child(args.variant)
        return
    if REPORT.exists():
        raise FileExistsError(REPORT)
    runs = []
    for variant in ("baseline", "current"):
        process = subprocess.run([sys.executable, "-X", "utf8", str(Path(__file__).resolve()),
                                  "--variant", variant], cwd=ROOT, capture_output=True,
                                 encoding="utf-8", check=True)
        run = json.loads(process.stdout)
        runs.append(run)
        print(f"{variant}: {run['tests']} tests, {len(run['failures'])} failures, "
              f"{len(run['errors'])} errors", flush=True)
    for run in runs:
        assert {r["test"] for r in run["failures"]} == EXPECTED_FAILURES
        assert {r["test"] for r in run["errors"]} == EXPECTED_ERRORS
        assert run["skipped"] == 0
    assert runs[0]["tests"] == runs[1]["tests"]
    for kind in ("failures", "errors"):
        # Ignore traceback line numbers; the last exception must also match.
        errors = [{row["test"]: row["traceback"].strip().splitlines()[-1]
                   for row in run[kind]} for run in runs]
        assert errors[0] == errors[1]
    report = {"status": "NO_NEW_UNIT_FAILURES", "all_tests_pass": False,
              "new_correction_and_menu_tests_pass": True,
              "baseline_scope": "Current workspace with the new three-row correction disabled in memory; no user files changed",
              "known_failures": "Historical narration-width/centering/source-text/saved-editor-file expectations; retained without rewriting user data or tests",
              "runs": runs}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(str(REPORT), flush=True)


if __name__ == "__main__":
    main()
