from __future__ import annotations

import argparse
from pathlib import Path

from .harness import PROFILES, run_all


def main() -> None:
    parser = argparse.ArgumentParser(
        description="运行 SignalField A/B/C 固定材料回放评测（不调用任何远程服务）"
    )
    parser.add_argument(
        "--profiles",
        default="A,B,C",
        help="逗号分隔的策略，默认 A,B,C",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "results"),
        help="结果输出目录",
    )
    args = parser.parse_args()
    profiles = [item.strip().upper() for item in args.profiles.split(",") if item.strip()]
    unknown = [item for item in profiles if item not in PROFILES]
    if unknown:
        parser.error(f"未知策略：{', '.join(unknown)}")
    result = run_all(Path(args.output_dir), profiles)
    aggregates = result["aggregates"]
    print("SignalField replay evaluation")
    print("mode=replay synthetic=true remote_calls=0")
    print("")
    print(f"{'profile':<8}{'coverage':>10}{'fact_cov':>10}{'citation':>10}{'dup_rate':>10}{'avg_s/r/m':>14}")
    for agg in aggregates:
        def pct(value):
            return "—" if value is None else f"{value * 100:.1f}%"

        print(
            f"{agg['profile']:<8}{pct(agg['reference_event_coverage']):>10}"
            f"{pct(agg['reference_fact_coverage']):>10}"
            f"{pct(agg['citation_support_rate']):>10}"
            f"{pct(agg['duplicate_rate']):>10}  "
            f"{agg['avg_searches']:.1f}/{agg['avg_reads']:.1f}/{agg['avg_model_calls']:.1f}"
        )
    print("")
    print(f"Report: {result['json_path'].with_suffix('.md')}")
    print(f"JSON:   {result['json_path']}")
    print(f"Manual: {result['annotation_path']}")
    print("")
    print("Caveat: deterministic synthetic replay; not a live-model or live-search claim.")


if __name__ == "__main__":
    main()
