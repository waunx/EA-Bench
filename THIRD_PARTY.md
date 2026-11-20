# Sources and licenses

EA-Bench is an independent research benchmark. Adaptations and their reported
results are not official upstream benchmark results or endorsements.

- **JobBench data**: https://huggingface.co/datasets/JobBench/job-bench, revision
  `d43a66575635da0d3f6cb9a20976dc1a60f3ffc9`. The pinned dataset card declares MIT.
  Source task IDs, task instructions, rubrics, and applicable attachment notices
  are retained in the evaluation data bundle.
- **JobBench evaluator**: https://github.com/Job-Bench/job-bench-eval, revision
  `e0267c6d2413a5df3448be1c45449aa36843e73d`. Vendored evaluation support is under
  Apache-2.0; see `vendor/jobbench/LICENSE`. Runtime configuration and EA-Bench
  adapters are separate from this upstream component.
- **WorkBench**: https://github.com/olly-styles/WorkBench, revision
  `49c7dfd00c03d384ec59ea57374f50b766aa5613`. The source templates retain the
  upstream MIT license in the data bundle under `data/source_refs/workbench/`.
- **AppWorld-UL**: https://arxiv.org/abs/2607.20536. Task adaptations and the
  knowledge-bounded user-simulation design are described in the paper. The
  source article is CC-BY-4.0. Native AppWorld replay requires the upstream
  environment and data, installed separately under their respective licenses.
- Public reference documents retain their original notices and source URLs.
  The EA-Bench MIT license does not supersede third-party terms.

The 63 constructed base-task instances include known source-related tasks.
Variants within a base task share business records and should not be treated as
independent source tasks in statistical analyses.
