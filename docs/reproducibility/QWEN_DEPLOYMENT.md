# Qwen deployment evidence

Source: author-designated immutable remote export `m3a_qwen3_2wiki_remote_final_20260930T062205Z`, metadata directory `tmp/m3a_qwen3_export_20260930T062205Z/metadata/`.

- One NVIDIA A10 GPU; driver 570.195.03; driver-reported CUDA compatibility 12.8.
- vLLM API server 0.10.2; Qwen3ForCausalLM; bfloat16; model context 8192; server seed 20260921; `generation_config=vllm`.
- Served alias `qwen3-8b-m1`; source model `Qwen/Qwen3-8B`.
- Exported source commit `6c2eb4279ca2b612632893908c55ae8df47b9fb6`.
- The service settings are not a full historical environment lock or a substitute for request-specific decoding settings.
- Machine-specific paths, host identifiers and service configuration secrets are not needed in this summary and are not reproduced.

Recorded model reference(s) in the selected chain observations:

- `vllm_openai_compatible:qwen3-8b-m1@26028140be3ee69b82b1d1450179ab71bb1121b9`

The checkpoint availability CSV reconciles the 40 selected chain checkpoint paths with this export. It does not relabel records, rescan judgments or rerun statistical estimators.

- MATCH: 40
- HASH_MISMATCH: 0
- NOT_FOUND: 0
