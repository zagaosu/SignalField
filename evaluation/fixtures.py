"""Deterministic synthetic replay corpus.

The corpus is deliberately synthetic. It tests retrieval policy and evidence
handling, not live model quality. Every URL uses the reserved .invalid TLD.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def _date(now: datetime, offset: int | None) -> str | None:
    if offset is None:
        return None
    return (now.date() + timedelta(days=offset)).isoformat()


def _doc(
    *,
    key: str,
    title: str,
    url: str,
    domain: str,
    published_offset: int,
    event_date_offset: int | None,
    facts: list[dict],
    fail_read: bool = False,
) -> dict:
    content = "\n\n".join(fact["quote"] for fact in facts)
    return {
        "key": key,
        "title": title,
        "url": url,
        "domain": domain,
        "published_offset": published_offset,
        "event_date_offset": event_date_offset,
        "facts": facts,
        "content": content,
        "fail_read": fail_read,
    }


def _event(
    *,
    key: str,
    title: str,
    project: str,
    topic: str,
    base_summary: str,
    resolved_summary: str,
    initial_unresolved: list[str],
    resolved_unresolved: list[str],
    reference_facts: list[str],
    reference_date_offset: int | None,
    expected_change: str | None,
    reference_conditions: dict | None = None,
    gap_reason: str | None = None,
    gap_query: str | None = None,
    gap_purpose: str | None = None,
) -> dict:
    return {
        "event_key": key,
        "title": title,
        "project": project,
        "topic": topic,
        "event_type": "release",
        "base_summary": base_summary,
        "resolved_summary": resolved_summary,
        "initial_unresolved": initial_unresolved,
        "resolved_unresolved": resolved_unresolved,
        "reference_facts": reference_facts,
        "reference_date_offset": reference_date_offset,
        "reference_conditions": reference_conditions or {},
        "expected_change": expected_change,
        "gap_reason": gap_reason,
        "gap_query": gap_query,
        "gap_purpose": gap_purpose,
    }


def build_scenarios(now: datetime) -> list[dict]:
    scenarios: list[dict] = []

    # 1. Normal release: an official page with date and complete conditions.
    d1 = _doc(
        key="d1",
        title="Nova Agent 1.2 发布说明",
        url="https://nova.invalid/releases/1-2",
        domain="nova.invalid",
        published_offset=-2,
        event_date_offset=-2,
        facts=[
            {
                "statement": "Nova Agent 1.2 新增可审计的工具调用日志。",
                "category": "release",
                "conditions": "",
                "quote": f"Nova Agent 1.2 于 {_date(now, -2)} 发布，新增可审计的工具调用日志。",
            },
            {
                "statement": "Nova Agent 1.2 要求 Python 3.11 及以上，并保持 v1 编排 API 兼容。",
                "category": "compatibility",
                "conditions": "Python 3.11+",
                "quote": "该版本要求 Python 3.11 及以上，并保持 v1 编排 API 兼容。",
            },
        ],
    )
    scenarios.append(
        {
            "id": "normal_release",
            "case_type": "normal_release",
            "name": "正常发布",
            "topic": "Agent",
            "queries": {
                "single": ["Nova Agent 1.2 release notes"],
                "fixed": ["Nova Agent 1.2 release notes", "Nova Agent official changelog"],
                "agent": ["Nova Agent 1.2 最新发布", "Nova Agent 1.2 official release notes"],
            },
            "initial_docs": [d1],
            "gap_docs": [],
            "event": _event(
                key="nova-agent-1-2",
                title="Nova Agent 1.2 新增可审计工具日志",
                project="Nova Agent",
                topic="Agent",
                base_summary="Nova Agent 1.2 新增工具调用审计日志，并要求 Python 3.11 及以上。",
                resolved_summary="Nova Agent 1.2 新增工具调用审计日志，并要求 Python 3.11 及以上。",
                initial_unresolved=[],
                resolved_unresolved=[],
                reference_facts=[
                    "Nova Agent 1.2 新增可审计的工具调用日志。",
                    "Nova Agent 1.2 要求 Python 3.11 及以上，并保持 v1 编排 API 兼容。",
                ],
                reference_date_offset=-2,
                expected_change="new",
            ),
            "prior": False,
            "notes": "官方 release notes 同时给出日期与兼容条件。",
        }
    )

    # 2. Repost syndication: three pages, one event, and a prior identical fact set.
    original_quote = f"Orbit Agent 2.0 于 {_date(now, -3)} 发布，加入跨会话记忆压缩。"
    budget_quote = "Orbit Agent 2.0 默认限制单次工具调用预算，并保留调用明细。"
    repost_facts = [
        {
            "statement": "Orbit Agent 2.0 加入跨会话记忆压缩。",
            "category": "release",
            "conditions": "",
            "quote": original_quote,
        },
        {
            "statement": "Orbit Agent 2.0 默认限制单次工具调用预算并保留调用明细。",
            "category": "api",
            "conditions": "",
            "quote": budget_quote,
        },
    ]
    docs = [
        _doc(
            key="d1",
            title="Orbit Agent 2.0 官方发布",
            url="https://orbit.invalid/release-2-0",
            domain="orbit.invalid",
            published_offset=-3,
            event_date_offset=-3,
            facts=repost_facts,
        ),
        _doc(
            key="d2",
            title="Orbit Agent 2.0 发布（转载）",
            url="https://repost-a.invalid/orbit-2-0",
            domain="repost-a.invalid",
            published_offset=-3,
            event_date_offset=-3,
            facts=repost_facts,
        ),
        _doc(
            key="d3",
            title="Orbit Agent 2.0 更新速览（转载）",
            url="https://repost-b.invalid/orbit-update",
            domain="repost-b.invalid",
            published_offset=-2,
            event_date_offset=-3,
            facts=repost_facts,
        ),
    ]
    scenarios.append(
        {
            "id": "repost_duplicate",
            "case_type": "duplicate_repost",
            "name": "重复转载",
            "topic": "Agent",
            "queries": {
                "single": ["Orbit Agent 2.0 release"],
                "fixed": ["Orbit Agent 2.0 release", "Orbit Agent 2.0 changelog"],
                "agent": ["Orbit Agent 2.0 最新发布", "Orbit Agent 2.0 official release"],
            },
            "initial_docs": docs,
            "gap_docs": [],
            "event": _event(
                key="orbit-agent-2-0",
                title="Orbit Agent 2.0 加入跨会话记忆压缩",
                project="Orbit Agent",
                topic="Agent",
                base_summary="Orbit Agent 2.0 加入跨会话记忆压缩，并默认限制单次工具调用预算。",
                resolved_summary="Orbit Agent 2.0 加入跨会话记忆压缩，并默认限制单次工具调用预算。",
                initial_unresolved=[],
                resolved_unresolved=[],
                reference_facts=[
                    "Orbit Agent 2.0 加入跨会话记忆压缩。",
                    "Orbit Agent 2.0 默认限制单次工具调用预算并保留调用明细。",
                ],
                reference_date_offset=-3,
                expected_change="unchanged",
            ),
            "prior": True,
            "notes": "三篇内容相同；历史事实相同，应判为无实质更新且不重复提醒。",
        }
    )

    # 3. Old article republished: recent publication date, old event date.
    old_doc = _doc(
        key="d1",
        title="Aurora Inference 1.0 旧文重发",
        url="https://aurora-watch.invalid/repost-old-1-0",
        domain="aurora-watch.invalid",
        published_offset=-1,
        event_date_offset=-400,
        facts=[
            {
                "statement": "Aurora Inference 1.0 于去年发布，新增动态批处理。",
                "category": "release",
                "conditions": "",
                "quote": f"Aurora Inference 1.0 于 {_date(now, -400)} 发布，新增动态批处理；本文为旧文重发。",
            }
        ],
    )
    scenarios.append(
        {
            "id": "old_article_reissue",
            "case_type": "old_reissue",
            "name": "旧文重发",
            "topic": "推理部署",
            "queries": {
                "single": ["Aurora Inference 1.0 动态批处理"],
                "fixed": ["Aurora Inference 1.0 动态批处理", "Aurora Inference 最新发布"],
                "agent": ["Aurora Inference 最新动态", "Aurora Inference 1.0 官方发布"],
            },
            "initial_docs": [old_doc],
            "gap_docs": [],
            "event": _event(
                key="aurora-inference-1-0",
                title="Aurora Inference 1.0 新增动态批处理",
                project="Aurora Inference",
                topic="推理部署",
                base_summary="Aurora Inference 1.0 新增动态批处理。",
                resolved_summary="Aurora Inference 1.0 新增动态批处理。",
                initial_unresolved=[],
                resolved_unresolved=[],
                reference_facts=["Aurora Inference 1.0 于去年发布，新增动态批处理。"],
                reference_date_offset=-400,
                expected_change=None,
            ),
            "prior": False,
            "notes": "文章发布时间在窗内，但事件日期在窗外；不得包装成近期新事件。",
        }
    )

    # 4. Ambiguous event date, resolved by a targeted official query.
    ambig_initial = _doc(
        key="d1",
        title="Cipher Agent 3.0 预印本摘要",
        url="https://cipher-blog.invalid/preprint-3-0",
        domain="cipher-blog.invalid",
        published_offset=-2,
        event_date_offset=None,
        facts=[
            {
                "statement": "Cipher Agent 3.0 引入基于证据的记忆回放。",
                "category": "release",
                "conditions": "",
                "quote": "Cipher Agent 3.0 引入基于证据的记忆回放，预印本页面未标注正式发布日期。",
            }
        ],
    )
    ambig_gap = _doc(
        key="d2",
        title="Cipher Agent 3.0 正式发布公告",
        url="https://cipher.invalid/releases/3-0",
        domain="cipher.invalid",
        published_offset=-2,
        event_date_offset=-2,
        facts=[
            {
                "statement": "Cipher Agent 3.0 引入基于证据的记忆回放。",
                "category": "release",
                "conditions": "",
                "quote": f"{_date(now, -2)}，Cipher Agent 3.0 正式发布，引入基于证据的记忆回放。",
            },
            {
                "statement": "Cipher Agent 3.0 支持 Python 3.12。",
                "category": "compatibility",
                "conditions": "Python 3.12",
                "quote": "官方版本同时说明，Cipher Agent 3.0 支持 Python 3.12。",
            },
        ],
    )
    scenarios.append(
        {
            "id": "ambiguous_date",
            "case_type": "ambiguous_date",
            "name": "日期模糊",
            "topic": "Agent",
            "queries": {
                "single": ["Cipher Agent 3.0 记忆回放"],
                "fixed": ["Cipher Agent 3.0 记忆回放", "Cipher Agent 3.0 release"],
                "agent": ["Cipher Agent 3.0 最新发布", "Cipher Agent 3.0 记忆评测"],
            },
            "initial_docs": [ambig_initial],
            "gap_docs": [ambig_gap],
            "event": _event(
                key="cipher-agent-3-0",
                title="Cipher Agent 3.0 引入基于证据的记忆回放",
                project="Cipher Agent",
                topic="Agent",
                base_summary="Cipher Agent 3.0 引入基于证据的记忆回放，但预印本未给出正式发布日期。",
                resolved_summary="Cipher Agent 3.0 正式发布，引入基于证据的记忆回放，并支持 Python 3.12。",
                initial_unresolved=["Cipher Agent 3.0 的正式发布日期不明确。"],
                resolved_unresolved=["Cipher Agent 3.0 的正式发布日期不明确。"],
                reference_facts=[
                    "Cipher Agent 3.0 引入基于证据的记忆回放。",
                    "Cipher Agent 3.0 支持 Python 3.12。",
                ],
                reference_date_offset=-2,
                expected_change="new",
                gap_reason="ambiguous_date",
                gap_query="Cipher Agent 3.0 正式发布日期 官方公告",
                gap_purpose="确认事件实际发布日期，区分文章发布时间",
            ),
            "prior": False,
            "notes": "初始资料日期未知；补搜官方公告后日期明确。",
        }
    )

    # 5. Performance claim without conditions, resolved by official benchmark.
    perf_initial = _doc(
        key="d1",
        title="TempoServe 1.8 社区实测",
        url="https://perf-blog.invalid/temposerve-1-8",
        domain="perf-blog.invalid",
        published_offset=-3,
        event_date_offset=-3,
        facts=[
            {
                "statement": "TempoServe 1.8 的吞吐提升 40%。",
                "category": "performance",
                "conditions": "",
                "quote": "独立测试显示，TempoServe 1.8 的吞吐提升 40%，但页面没有给出硬件、基线或负载条件。",
            }
        ],
    )
    perf_gap = _doc(
        key="d2",
        title="TempoServe 1.8 官方基准说明",
        url="https://temposerve.invalid/benchmarks/1-8",
        domain="temposerve.invalid",
        published_offset=-3,
        event_date_offset=-3,
        facts=[
            {
                "statement": "TempoServe 1.8 的吞吐提升 40%。",
                "category": "performance",
                "conditions": "A100 80GB、batch size 8、FP16 基线",
                "quote": "官方基准显示，在 A100 80GB、batch size 8、FP16 基线下，TempoServe 1.8 的吞吐提升 40%。",
            },
            {
                "statement": "TempoServe 1.8 要求 CUDA 12.3 以上。",
                "category": "compatibility",
                "conditions": "CUDA 12.3+",
                "quote": "该版本要求 CUDA 12.3 以上。",
            },
        ],
    )
    scenarios.append(
        {
            "id": "performance_missing_conditions",
            "case_type": "missing_conditions",
            "name": "性能缺条件",
            "topic": "推理部署",
            "queries": {
                "single": ["TempoServe 1.8 吞吐 提升"],
                "fixed": ["TempoServe 1.8 吞吐 提升", "TempoServe 1.8 benchmark"],
                "agent": ["TempoServe 1.8 最新更新", "TempoServe 1.8 性能 测试"],
            },
            "initial_docs": [perf_initial],
            "gap_docs": [perf_gap],
            "event": _event(
                key="temposerve-1-8",
                title="TempoServe 1.8 宣称吞吐提升 40%",
                project="TempoServe",
                topic="推理部署",
                base_summary="第三方测试称 TempoServe 1.8 吞吐提升 40%，但没有给出硬件与基线条件。",
                resolved_summary="官方基准补充了硬件、batch size 与 FP16 基线；TempoServe 1.8 要求 CUDA 12.3 以上。",
                initial_unresolved=["性能结论缺少硬件、基线与负载条件。"],
                resolved_unresolved=["性能结论缺少硬件、基线与负载条件。"],
                reference_facts=[
                    "TempoServe 1.8 的吞吐提升 40%。",
                    "TempoServe 1.8 要求 CUDA 12.3 以上。",
                ],
                reference_date_offset=-3,
                reference_conditions={
                    "TempoServe 1.8 的吞吐提升 40%。": "A100 80GB、batch size 8、FP16 基线"
                },
                expected_change="new",
                gap_reason="missing_conditions",
                gap_query="TempoServe 1.8 benchmark A100 batch baseline",
                gap_purpose="补齐性能结论的硬件、基线或负载条件",
            ),
            "prior": False,
            "notes": "性能数字必须与适用条件一起保留。",
        }
    )

    # 6. Conflicting compatibility claims, resolved by original docs.
    conflict_a = _doc(
        key="d1",
        title="Harbor SDK 4.1 发布公告",
        url="https://harbor.invalid/release-4-1",
        domain="harbor.invalid",
        published_offset=-2,
        event_date_offset=-2,
        facts=[
            {
                "statement": "Harbor SDK 4.1 支持 8GB 显存设备。",
                "category": "compatibility",
                "conditions": "8GB 显存",
                "quote": "Harbor SDK 4.1 支持 8GB 显存设备，并默认启用 INT4 推理。",
            }
        ],
    )
    conflict_b = _doc(
        key="d2",
        title="Harbor SDK 4.1 社区测试",
        url="https://harbor-community.invalid/int4-8gb",
        domain="harbor-community.invalid",
        published_offset=-2,
        event_date_offset=-2,
        facts=[
            {
                "statement": "Harbor SDK 4.1 在 8GB 设备上无法启用 INT4。",
                "category": "compatibility",
                "conditions": "8GB 显存、INT4",
                "quote": "社区测试发现，Harbor SDK 4.1 在 8GB 设备上无法启用 INT4，实际回退到 FP16。",
            }
        ],
    )
    conflict_gap = _doc(
        key="d3",
        title="Harbor SDK 4.1 兼容性说明",
        url="https://harbor.invalid/docs/4-1-compatibility",
        domain="harbor.invalid",
        published_offset=-1,
        event_date_offset=-2,
        facts=[
            {
                "statement": "Harbor SDK 4.1 的 INT4 需要 16GB 及以上显存，8GB 设备会自动回退到 FP16。",
                "category": "compatibility",
                "conditions": "INT4 需 16GB+；8GB 回退 FP16",
                "quote": "兼容性说明澄清：Harbor SDK 4.1 的 INT4 需要 16GB 及以上显存，8GB 设备会自动回退到 FP16。",
            }
        ],
    )
    scenarios.append(
        {
            "id": "conflicting_sources",
            "case_type": "conflict",
            "name": "来源冲突",
            "topic": "推理部署",
            "queries": {
                "single": ["Harbor SDK 4.1 8GB INT4"],
                "fixed": ["Harbor SDK 4.1 8GB INT4", "Harbor SDK 4.1 兼容性"],
                "agent": ["Harbor SDK 4.1 最新发布", "Harbor SDK 4.1 8GB 支持"],
            },
            "initial_docs": [conflict_a, conflict_b],
            "gap_docs": [conflict_gap],
            "event": _event(
                key="harbor-sdk-4-1",
                title="Harbor SDK 4.1 的 8GB 显存支持存在冲突",
                project="Harbor SDK",
                topic="推理部署",
                base_summary="官方公告称 Harbor SDK 4.1 支持 8GB 设备，但社区测试观察到 INT4 回退与失败。",
                resolved_summary="原始兼容性说明澄清：INT4 需要 16GB 及以上显存，8GB 设备会回退到 FP16。",
                initial_unresolved=["8GB 显存支持结论存在冲突。"],
                resolved_unresolved=["8GB 显存支持结论存在冲突。"],
                reference_facts=[
                    "Harbor SDK 4.1 支持 8GB 显存设备。",
                    "Harbor SDK 4.1 在 8GB 设备上无法启用 INT4。",
                    "Harbor SDK 4.1 的 INT4 需要 16GB 及以上显存，8GB 设备会自动回退到 FP16。",
                ],
                reference_date_offset=-2,
                expected_change="new",
                gap_reason="conflict",
                gap_query="Harbor SDK 4.1 兼容性 官方说明 文档",
                gap_purpose="寻找原始文档，解决 8GB 支持结论冲突",
            ),
            "prior": False,
            "notes": "保留冲突，直到原始兼容性文档解释差异。",
        }
    )

    # 7. No results at all.
    scenarios.append(
        {
            "id": "no_results",
            "case_type": "no_results",
            "name": "无结果",
            "topic": "模型工具",
            "queries": {
                "single": ["Quasar ModelKit 最新发布"],
                "fixed": ["Quasar ModelKit 最新发布", "Quasar ModelKit release"],
                "agent": ["Quasar ModelKit 最新发布", "Quasar ModelKit SDK 更新"],
            },
            "initial_docs": [],
            "gap_docs": [],
            "event": None,
            "prior": False,
            "notes": "搜索为空，不得用模板内容填充。",
        }
    )

    # 8. Unreadable initial pages, recovered by a targeted alternate source.
    fail_a = _doc(
        key="d1",
        title="Lumen Agent 1.0 发布（需登录）",
        url="https://lumen.invalid/release",
        domain="lumen.invalid",
        published_offset=-2,
        event_date_offset=-2,
        fail_read=True,
        facts=[
            {
                "statement": "Lumen Agent 1.0 发布。",
                "category": "release",
                "conditions": "",
                "quote": "Lumen Agent 1.0 发布。",
            }
        ],
    )
    fail_b = _doc(
        key="d2",
        title="Lumen Agent 1.0 镜像页",
        url="https://mirror.invalid/lumen-1-0",
        domain="mirror.invalid",
        published_offset=-2,
        event_date_offset=-2,
        fail_read=True,
        facts=[
            {
                "statement": "Lumen Agent 1.0 发布。",
                "category": "release",
                "conditions": "",
                "quote": "Lumen Agent 1.0 发布。",
            }
        ],
    )
    recovery = _doc(
        key="d3",
        title="Lumen Agent 1.0 可读的官方镜像说明",
        url="https://lumen-docs.invalid/1-0",
        domain="lumen-docs.invalid",
        published_offset=-2,
        event_date_offset=-2,
        facts=[
            {
                "statement": "Lumen Agent 1.0 新增工具调用回放，并要求 Node.js 22 及以上。",
                "category": "release",
                "conditions": "Node.js 22+",
                "quote": f"Lumen Agent 1.0 于 {_date(now, -2)} 发布，新增工具调用回放，并要求 Node.js 22 及以上。",
            }
        ],
    )
    scenarios.append(
        {
            "id": "read_failure",
            "case_type": "read_failure",
            "name": "正文读取失败",
            "topic": "Agent",
            "queries": {
                "single": ["Lumen Agent 1.0 release"],
                "fixed": ["Lumen Agent 1.0 release", "Lumen Agent 1.0 changelog"],
                "agent": ["Lumen Agent 1.0 最新发布", "Lumen Agent 1.0 工具回放"],
            },
            "initial_docs": [fail_a, fail_b],
            "gap_docs": [recovery],
            "event": _event(
                key="lumen-agent-1-0",
                title="Lumen Agent 1.0 新增工具调用回放",
                project="Lumen Agent",
                topic="Agent",
                base_summary="Lumen Agent 1.0 新增工具调用回放，并要求 Node.js 22 及以上。",
                resolved_summary="Lumen Agent 1.0 新增工具调用回放，并要求 Node.js 22 及以上。",
                initial_unresolved=[],
                resolved_unresolved=[],
                reference_facts=["Lumen Agent 1.0 新增工具调用回放，并要求 Node.js 22 及以上。"],
                reference_date_offset=-2,
                expected_change="new",
            ),
            "prior": False,
            "notes": "首轮来源读取失败；Agent 应寻找可读替代来源，而不是从摘要生成事实。",
        }
    )
    return scenarios
