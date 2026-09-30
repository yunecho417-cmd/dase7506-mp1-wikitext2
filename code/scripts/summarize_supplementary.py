#!/usr/bin/env python3
"""Build the dated validation-only ablation summary from saved run metadata."""

from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path


CODE = Path(__file__).resolve().parents[1]
ROOT = CODE.parent
RUNS = CODE / "runs"
OUT_DIR = CODE / "results" / "2026-09-25"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def run(name: str):
    return read_json(RUNS / name / "metrics.json")


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def row(name: str):
    item = run(name)
    return {
        "run": name,
        "seed": item.get("seed"),
        "parameters": item.get("parameters"),
        "asset_mib": item.get("asset_mib"),
        "selected_targets": item.get("checkpoint_processed_targets", item.get("processed_targets")),
        "search_targets": item.get("processed_targets"),
        "validation_bpb": item["validation"]["bpb"],
        "checkpoint_sha256": item.get("checkpoint_sha256"),
    }


def main():
    groups = {
        "training_recipe": [
            "recipe_exact_baseline_s17", "recipe_norepl_s17",
            "recipe_norepl_beta095_s17", "recipe_full_student_s17",
        ],
        "norm_ffn_factorial": [
            "s0_lr1e3", "ablation_rms_gelu_s17",
            "ablation_ln_swiglu_s17", "s_lr1e3",
        ],
        "capacity": ["lr1e3_a", "capacity_w320d10_s17", "capacity_w384d8_s17"],
        "representation": [
            "lr1e3_a", "ablation_untied_s17", "ablation_rope_s17",
            "ablation_rope_s137", "ablation_rope_untied_s17",
            "ablation_rope_untied_s137",
        ],
        "training_only": [
            "ablation_rope_untied_s17", "ablation_rope_untied_ema099_s17",
            "ablation_rope_untied_mtp1_s17",
        ],
    }
    long_names = [
        "2026-09-25_rope_long_best_seed17",
        "2026-09-25_rope_long_best_seed137",
        "2026-09-25_rope_long_best_seed233",
    ]
    long_rows = []
    for name in long_names:
        if not (RUNS / name / "metrics.json").exists():
            continue
        item = run(name)
        cpu_path = OUT_DIR / f"{name}_validation_cpu_fp32.json"
        cpu_result = read_json(cpu_path) if cpu_path.exists() else None
        long_rows.append({
            **row(name),
            "selected_step": item["selected_step"],
            "final_validation_bpb_mps_bf16": item["curve"][-1]["bpb"],
            "validation_bpb_cpu_fp32": cpu_result["bpb"] if cpu_result else None,
            "validation_targets_cpu_fp32": cpu_result.get("targets") if cpu_result else None,
            "train_seconds": item["train_seconds"],
        })

    if len(long_rows) < 2:
        raise RuntimeError("At least two completed RoPE long-run seeds are required")

    selection_key = "validation_bpb_cpu_fp32"
    if any(item[selection_key] is None for item in long_rows):
        selection_key = "validation_bpb"
    selected = min(long_rows, key=lambda item: item[selection_key])
    selected_checkpoint = RUNS / selected["run"] / "checkpoint.pt"
    resource_path = OUT_DIR / "resources_validation_rope_candidate.json"
    resources = read_json(resource_path) if resource_path.exists() else None

    all_metrics = sorted(RUNS.glob("*/metrics.json"))
    total_search_targets = sum(read_json(path).get("processed_targets", 0) for path in all_metrics)
    all_bpbs = [item[selection_key] for item in long_rows]
    summary = {
        "protocol": "7506-mp1-wt2-post-freeze-validation-v1",
        "date": "2026-09-25",
        "status": "validation-only; frozen v1 test result is unchanged",
        "official_frozen_v1": {
            "validation_bpb": 1.6224410483804197,
            "test_bpb": 1.6461521330206645,
            "checkpoint_sha256": "ab9ba8b648513530c528ce00345ba1dd8749351c8cf5516dc5ace84f40ad6657",
            "implementation_sha256": "399ab947a7c9f74cef024a6d601f82914e2dd79c5d16a2c74d96c20ebeabf5c0",
        },
        "experiment_groups": {
            key: [row(name) for name in names]
            for key, names in groups.items()
        },
        "decisions": {
            "sampling": "Without-replacement sampling was neutral at the small baseline scale.",
            "optimizer_beta2": "beta2=0.95 hurt the small baseline; it does not explain architecture gains.",
            "norm_ffn": "SwiGLU provides most of the block gain; RMSNorm adds a small improvement.",
            "capacity": "w320 d8 remains best; d10 is worse and w384 d8 is worse while near the asset limit.",
            "representation": "RoPE improves both short-run seeds; untied output weights add less than the 0.01 BPB threshold.",
            "training_only": "EMA and one-step MTP do not justify their additional complexity or cost.",
            "checkpointing": "Select among predeclared validation points and report both search and selected-checkpoint targets.",
        },
        "rope_long_training": {
            "runs": long_rows,
            "selection_metric": selection_key,
            "mean_bpb": statistics.mean(all_bpbs),
            "sample_stdev_bpb": statistics.stdev(all_bpbs),
            "selected_run": selected["run"],
            "selected_seed": selected["seed"],
            "selected_bpb": selected[selection_key],
            "selected_checkpoint_sha256_verified": sha256(selected_checkpoint),
            "test_evaluated": False,
        },
        "validation_resource_measurement": resources,
        "search_accounting": {
            "metrics_files": len(all_metrics),
            "total_processed_targets_across_saved_runs": total_search_targets,
            "note": "This total includes frozen-v1 development and post-freeze diagnostics represented by metrics.json files.",
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUT_DIR / "supplementary_summary.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    candidate_manifest = {
        "status": "validation-only candidate; test not evaluated",
        "selected_by": "lowest complete-split CPU FP32 validation BPB among seeds 17, 137, and 233",
        "run": selected["run"],
        "seed": selected["seed"],
        "config": "configs/ours_a_rope.json",
        "checkpoint": f"runs/{selected['run']}/checkpoint.pt",
        "search_targets": selected["search_targets"],
        "checkpoint_processed_targets": selected["selected_targets"],
        "validation_bpb_cpu_fp32": selected[selection_key],
        "checkpoint_sha256": sha256(selected_checkpoint),
        "implementation_sha256": sha256(CODE / "student.py"),
        "evaluator_sha256": sha256(CODE / "evaluate.py"),
        "tokenizer_sha256": sha256(CODE / "data" / "tokenizer.json"),
        "config_sha256": sha256(CODE / "configs" / "ours_a_rope.json"),
        "resource_measurement": "results/2026-09-25/resources_validation_rope_candidate.json" if resources else None,
    }
    (OUT_DIR / "candidate_manifest.json").write_text(
        json.dumps(candidate_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
