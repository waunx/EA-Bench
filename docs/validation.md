# Release validation

Validated on 2026-11-20 with Python 3.12. The CPU-only suite makes no model API calls.

| Check | Result |
|---|---|
| Selected public input hashes | 232 conditions verified |
| Closed-state reference replay | 68 conditions, 262 checked worlds passed |
| Dependency enforcement | Missing-prerequisite terminal submissions rejected |
| Application state initialization | 79 condition packets passed |
| Artifact adapter imports and public reference files | All 30 cases passed |
| Public reference isolation | All 85 Hard conditions passed |
| User-value validation | Incorrect authoritative values rejected |
| Unrequested facts | Excluded from the solver-facing reply |
| Task outcome versus infrastructure status | Provider failure remains unscored |
| Grounding | Correct unqueried outputs can remain ungrounded |
| Native WorkBench smoke replay | Empty action sequence rejected as expected |
| Unit/integration test suite | 10 tests passed |

The release check covers packaging and deterministic evaluator behavior. It does
not rerun the full paid model experiment, validate subjective user experience,
or execute every native AppWorld/LibreOffice grading path. Those paths require
the upstream environment and system dependencies documented in the README.
