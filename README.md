# EA-Bench

**Measuring information and action efficiency under imperfect instructions.**

Xu Wan*, Wenyue Xu*, Shenjie Zhao (*equal contribution).

EA-Bench evaluates task completion, grounded outcomes, tool calls, and user
information requests under controlled Missing, Redundant, Conflict, and Mixed
instruction conditions.

| Track | Base tasks | Full | Missing | Redundant | Conflict | Mixed | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| Easy | 33 | 33 | 45 | 14 | 41 | 14 | 147 |
| Hard | 30 | 30 | 10 | 31 | 9 | 5 | 85 |
| Total | 63 | 63 | 55 | 45 | 50 | 19 | 232 |

The release contains the actual closed-state business evaluators, application
state engines, artifact adapters, knowledge-bounded user simulator, and task
inputs used by the selected English benchmark. Server-specific credentials and
run orchestration have been replaced with explicit local configuration.

## Install

Python 3.11+ is required. Use an editable installation from this checkout so the
code, registry, and downloaded data share one project root.

```bash
git clone https://github.com/waunx/EA-Bench.git
cd EA-Bench
python -m venv .venv
source .venv/bin/activate
pip install -e '.[artifacts]'
python scripts/download_data.py
python -m ea_bench verify
python -m ea_bench check-references
```

The data download is checksum-verified. The last command replays **68 closed-state
conditions across 262 finite reference worlds** without making model API calls.

## Model configuration

Copy `config.example.json` to `config.local.json`. Set your model names and API
base URLs independently for `solver`, `user`, and `judge`. API keys are read only
from the environment variables named in each configuration; do not put keys in
JSON files or commit generated runs.

```bash
export EA_SOLVER_API_KEY='your-key'
export EA_USER_API_KEY='your-key'
export EA_JUDGE_API_KEY='your-key'
python -m ea_bench list
python -m ea_bench run \
  --episode legacy:procurement:M2 \
  --config config.local.json \
  --output outputs/procurement-M2 \
  --max-actions 100
```

`wire_api` supports `chat` (Chat Completions-compatible) and `responses` for the
solver and simulated user. Artifact judging uses the upstream JobBench judge
and requires a Chat Completions-compatible judge endpoint. The published
configuration used GPT-5.5 at medium effort for user simulation and artifact
judging; select the matching model and `reasoning_effort` explicitly when your
provider supports it. No API keys or internal provider endpoints are bundled.

Each invocation creates a new output directory. Failures and infrastructure
errors are retained as separate outcomes; a transport error is not a scored
incorrect answer. Transport retries do not select the best task attempt.

## Application and artifact tasks

The 15 application cases use their case-specific state engines. Native AppWorld
replay additionally requires the upstream AppWorld environment and data. Set
`APPWORLD_ROOT` to that installation and `EA_APPWORLD_PYTHON` to its interpreter.
WorkBench reference templates and the required public JobBench references are
included in the data bundle. See [third-party attribution](THIRD_PARTY.md).

The 30 JobBench cases use their original task/rubric bindings and case-specific
artifact checks. **Linux, bubblewrap, LibreOffice, and Poppler** are required for
isolated artifact execution and rendering. `Dockerfile` supplies the general
analysis environment. Native AppWorld must still be installed separately.
The optional historical pinned Calc runtime can be configured separately; the
release does not claim bit-identical rendering across LibreOffice versions.

```bash
python -m ea_bench run \
  --episode expanded:WB12:R1 \
  --config config.local.json \
  --output outputs/WB12-R1

python -m ea_bench run \
  --episode expanded:JB17:M1 \
  --config config.local.json \
  --output outputs/JB17-M1

python -m ea_bench grade \
  --episode expanded:JB17:full \
  --config config.local.json \
  --artifacts path/to/submitted/files \
  --output outputs/JB17-grade
```

Missing native or grading dependencies are reported as infrastructure errors;
these cases are not silently evaluated at a weaker validation layer. `grade`
expects the associated private user records alongside the checker directory
when grading artifacts from imperfect-information runs. A new Full-condition
artifact can be graded without clarification records.

## Information boundaries and outputs

Only the selected episode's public prompt, input files, and allowed tools are
provided to the solver. Evaluator facts, reference worlds, graders, and sibling
variants stay outside the agent interface. Artifact shell commands run in a
network-isolated namespace with a cleared environment and bounded public mounts.
Never expose the entire data bundle or repository as an agent workspace.

Runs save the public dialogue, actual action counts, private user records, and
checker outcomes. Closed-state runs also report exact finite-reference grounding
and signed `Et`/`Ei` gaps. Application and artifact runs preserve their original
case-specific acceptance and evidence records; rubric-level grounding must be
interpreted with that evidence rather than inferred from task success alone.
A negative gap can indicate unfinished execution or missing information, and is
not by itself an efficiency ranking. Hard tasks have no validated global action
reference.

## Tests and verification scope

```bash
python -m unittest discover -s tests -v
```

The offline release checks cover:

- hashes for all **232 public condition packets**;
- **262** closed-state reference-world replays, including rejection of missing
  prerequisite steps;
- initialization and public observation boundaries for **79 application
  conditions**;
- imports and public-reference availability for all **30 artifact adapters**;
- incorrect user-value rejection, suppression of unrequested facts, separation
  of infrastructure errors from task failures, and ungrounded correct outputs.

Integration tests require the downloaded data. CI runs the available tests and
skips data-dependent checks when the bundle is absent. Release validation does
not rerun the paid model benchmark or assert human–simulator agreement.

## Project layout

```text
ea_bench/                  CLI, configuration, transports, closed-state runtime
integrations/              application engines, artifact graders, user simulator
benchmark/manifest.json    selected 63-task / 232-condition registry
data/                      downloaded evaluator data (gitignored)
vendor/jobbench/            upstream evaluator and its license
tests/                     offline protocol and integration checks
```

## License and citation

EA-Bench-owned code is licensed under **MIT**. Third-party code and source
materials retain their original licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).
Citation metadata is provided in `CITATION.cff`.
