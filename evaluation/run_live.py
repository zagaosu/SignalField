from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(
        description="对运行中的 SignalField 发起一次真实检索，并保存实时评测记录。"
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8790")
    parser.add_argument("--topic", action="append", dest="topics", help="可重复，最多 3 个")
    parser.add_argument("--window", choices=["day", "week"], default="week")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "results"))
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="明确确认会消耗 Tavily 与模型服务额度",
    )
    args = parser.parse_args()

    topics = args.topics or ["Agent"]
    if len(topics) > 3:
        parser.error("最多三个话题")
    base = args.base_url.rstrip("/")
    try:
        config = httpx.get(base + "/api/config", timeout=10).json()
    except Exception as exc:
        print(f"无法连接本地服务 {base}: {exc}")
        raise SystemExit(2)
    if not config.get("modes", {}).get("live", {}).get("available"):
        missing = config.get("modes", {}).get("live", {}).get("missing", [])
        print("真实检索未配置，未发起任何远程调用。")
        print("缺少服务端变量：" + ("、".join(missing) if missing else "未知"))
        print("请先按 README 配置 .env 并重启服务。")
        raise SystemExit(2)
    if not args.confirm_live:
        limits = config["limits"]
        print("这是实时评测：会真实消耗 Tavily / 模型额度，且结果受当日线上内容影响。")
        print(
            f"单任务上限：搜索 {limits['searches']}，正文读取 {limits['reads']}，"
            f"模型 {limits['model_calls']}，{limits['seconds']} 秒。"
        )
        print("确认后请加 --confirm-live 重新运行。")
        raise SystemExit(2)

    print(f"创建真实任务：topics={topics} window={args.window}")
    response = httpx.post(
        base + "/api/runs",
        json={"topics": topics, "window": args.window, "mode": "live"},
        timeout=20,
    )
    if response.status_code >= 400:
        print("创建任务失败：", response.text[:500])
        raise SystemExit(1)
    run = response.json()
    run_id = run["id"]
    print(f"run_id={run_id}，等待完成（最多 150 秒）…")
    deadline = time.time() + 150
    detail = run
    while time.time() < deadline:
        time.sleep(2)
        detail = httpx.get(f"{base}/api/runs/{run_id}", timeout=20).json()
        progress = detail.get("progress", {})
        print(f"  {progress.get('percent', 0):>3}% {progress.get('message', '')}")
        if detail.get("status") not in {"queued", "running", "cancelling"}:
            break
    if detail.get("status") in {"queued", "running", "cancelling"}:
        print("任务未在等待时间内结束；可用取消接口停止，或稍后查询。")
        raise SystemExit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {
        "mode": "live",
        "run_id": run_id,
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "base_url": base,
        "requested_topics": topics,
        "window": args.window,
        "run": detail,
        "caveats": [
            "实时网页内容会变化，本记录只能代表该时刻的一次运行。",
            "真实评测结果未提供人工标准答案；请使用 annotation_template.csv 补标。",
            "不要把本记录与固定材料回放结果合并计算。",
            "搜索摘要不作为正文证据；引用支持率仍是片段匹配，不是独立验证。",
        ],
    }
    path = output_dir / f"live_{stamp}_{run_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("")
    print(f"状态：{detail.get('status')} / {detail.get('stop_reason')}")
    print(f"事件：{len(detail.get('events', []))}")
    print(f"调用：{detail.get('usage')}")
    print(f"已保存：{path}")
    print("真实效果尚未经过人工标注，不能据此宣称线上质量。")


if __name__ == "__main__":
    main()
