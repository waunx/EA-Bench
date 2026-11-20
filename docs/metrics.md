# Evaluation outputs and metric scope

The solver receives the selected public packet. Evaluator reference worlds and
private facts are not part of that observation. A first terminal submission is
scored without returning grading feedback to the solver.

- `task_pass` / `success`: task outcome. Infrastructure errors use `null`, never
  a synthetic incorrect-answer value.
- `tool_calls` / `total_tool_calls`: recorded operations, including user calls.
- `requested_facts`: distinct requested fact identifiers within each turn,
  summed across turns. Repeated facts across turns count again.
- `delivered_facts`: actual returned fact occurrences. Requested and delivered
  quantities are separate; an unanswered request is not acquired knowledge.
- `user_interactions`: `ask_user` invocations, independently of fact count.
- `Et`, `Ei`: signed actual-minus-reference gaps where a validated reference
  and complete accounting are available. Early termination can yield negative
  gaps. Read these with task correctness, not as a standalone leaderboard.

Closed-state grounding compares the set of compatible checked policy worlds
with the actual world after returned facts are accounted for. A correct answer
can remain unsupported by those facts. Expanded tasks preserve their original
state/artifact evidence and finite-world certificates. Finite-world information
support alone does not establish that all relevant public files were inspected,
nor does it replace rubric-level grounding review for open-ended artifacts.

All fresh runs write to new directories. This code release does not include
private hosted-service credentials or historical raw API conversations, and it
does not launch paid experiments during installation or tests.
