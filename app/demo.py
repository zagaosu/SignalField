from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .tools.base import (
    LLMClient,
    PageReader,
    QuerySpec,
    ReadResult,
    SearchHit,
    SearchTool,
)

# Demo documents deliberately use reserved .invalid domains. They are never
# presented as real evidence links.

DEMO_NOTICE = (
    "以下内容为虚构演示样例：未执行实时搜索，不消耗远程服务额度；"
    "项目、来源与日期均为样例，不代表真实事件。"
)
CONFLICT_NOTE = (
    "官方称支持 Jetson Orin，但社区测试在 8GB 设备上观察到 INT4 回退，"
    "支持边界尚不明确（来源结论冲突）。"
)
DATE_UNKNOWN_NOTE = "LongTrace 的正式发布日期不明确。"


def _cn_date(value: date) -> str:
    return f"{value.year} 年 {value.month} 月 {value.day} 日"


class DemoCorpus:
    def __init__(self, now: datetime):
        today = now.date()
        self.aster_date = today - timedelta(days=1)
        self.lattice_date = today - timedelta(days=2)
        self.longtrace_article_date = today - timedelta(days=2)
        self.longtrace_release_date = today - timedelta(days=3)
        self.modelforge_date = today - timedelta(days=3)
        self.compat_date = today - timedelta(days=1)

        aster_quote_1 = (
            f"Northstar Labs 于 {_cn_date(self.aster_date)} 发布 Aster Agent Kit 0.8。"
            "该版本把工具权限网关设为默认开启，未在清单中声明的外部工具调用会被拒绝。"
        )
        aster_quote_2 = (
            "团队同时加入确定性回放：每次会话记录模型输入、工具参数与返回结果，"
            "开发者可以在本地复现失败步骤。"
        )
        aster_quote_3 = "该版本不改变现有 Agent 编排 API，升级需要 Node.js 20 或更高版本。"
        self.lattice_quote_1 = (
            f"Lattice Systems 于 {_cn_date(self.lattice_date)} 发布 Lattice Inference 2.4，"
            "新增 INT4 KV Cache 与端侧运行时。"
        )
        self.lattice_quote_2 = (
            "官方基准显示，在 24GB RTX 4090、batch size 1、2K 上下文条件下，"
            "首 token 延迟降低 31%，吞吐提升 18%。"
        )
        self.lattice_quote_3 = (
            "该版本要求 CUDA 12.4 及以上，并支持 Jetson Orin 系列的端侧部署。"
        )
        self.edge_quote_1 = (
            "社区测试在 Jetson Orin 8GB 上发现，Lattice Inference 2.4 的 INT4 KV Cache 会回退到 FP16。"
        )
        self.edge_quote_2 = (
            "测试使用 2K 上下文和单并发；在 8GB 显存下，启用 INT4 后实际显存占用并未下降。"
        )
        self.compat_quote_1 = (
            f"{_cn_date(self.compat_date)}更新的 Lattice Inference 2.4 兼容性说明指出："
            "INT4 KV Cache 仅在 Jetson Orin 16GB 及以上配置启用；8GB 配置会自动回退到 FP16。"
        )
        self.compat_quote_2 = (
            "官方同时说明，24GB RTX 4090 的基准使用 batch size 1、2K 上下文和 FP16 基线。"
        )
        self.longtrace_quote_1 = (
            "研究团队发布 LongTrace，一个面向长任务的 Agent 记忆评测集。"
        )
        self.longtrace_quote_2 = (
            "该评测集包含 120 个多轮任务，覆盖跨会话检索、冲突记忆更新与延迟回忆。"
        )
        self.longtrace_quote_3 = (
            "预印本页面未标注正式发布日期，页面发布时间与事件日期需要分开判断。"
        )
        self.longtrace_release_quote_1 = (
            f"{_cn_date(self.longtrace_release_date)}，研究团队正式发布 LongTrace 评测集 1.0。"
        )
        self.longtrace_release_quote_2 = (
            "正式版本包含 120 个多轮任务，并新增 20 个冲突记忆更新用例。"
        )
        self.modelforge_quote_1 = (
            f"ModelForge 于 {_cn_date(self.modelforge_date)} 发布 SDK 1.3，"
            "新增工具调用事件的流式返回。"
        )
        self.modelforge_quote_2 = (
            "开发者可以在工具参数生成过程中接收增量事件，同时在工具执行完成后获得结构化结果。"
        )
        self.modelforge_quote_3 = "该版本保持 v1 API 兼容，但要求 Python 3.10 及以上。"
        self.aster_quote = [aster_quote_1, aster_quote_2, aster_quote_3]
        self.lattice_quotes = {
            "d3": [self.lattice_quote_1, self.lattice_quote_2, self.lattice_quote_3],
            "d4": [self.edge_quote_1, self.edge_quote_2],
            "d7": [self.compat_quote_1, self.compat_quote_2],
        }
        self.longtrace_quotes = {
            "d5": [self.longtrace_quote_1, self.longtrace_quote_2, self.longtrace_quote_3],
            "d8": [self.longtrace_release_quote_1, self.longtrace_release_quote_2],
        }
        self.modelforge_quote = [
            self.modelforge_quote_1,
            self.modelforge_quote_2,
            self.modelforge_quote_3,
        ]
        self.docs: dict[str, dict[str, Any]] = {
            "d1": {
                "title": "Aster Agent Kit 0.8：工具权限网关与确定性回放（虚构样例）",
                "url": "https://northstar.invalid/aster-agent-kit-0-8",
                "domain": "northstar.invalid",
                "published_at": self.aster_date.isoformat(),
                "topic": "Agent",
                "content": "\n\n".join(self.aster_quote),
            },
            "d2": {
                "title": "Aster Agent Kit 0.8 发布：权限网关成为默认配置（转载）",
                "url": "https://agentweekly.invalid/aster-kit-repost",
                "domain": "agentweekly.invalid",
                "published_at": self.aster_date.isoformat(),
                "topic": "Agent",
                "content": "本文转载自 Northstar Labs 官方公告。\n\n"
                + "\n\n".join(self.aster_quote),
            },
            "d3": {
                "title": "Lattice Inference 2.4 将 INT4 KV Cache 带到端侧（虚构样例）",
                "url": "https://lattice.invalid/releases/2-4",
                "domain": "lattice.invalid",
                "published_at": self.lattice_date.isoformat(),
                "topic": "推理部署",
                "content": "\n\n".join(self.lattice_quotes["d3"]),
            },
            "d4": {
                "title": "社区实测：Jetson 8GB 上的 Lattice INT4 回退（虚构样例）",
                "url": "https://edgebench.invalid/lattice-int4-jetson-8gb",
                "domain": "edgebench.invalid",
                "published_at": (self.lattice_date - timedelta(days=1)).isoformat(),
                "topic": "推理部署",
                "content": "\n\n".join(self.lattice_quotes["d4"]),
            },
            "d5": {
                "title": "LongTrace：面向长任务的 Agent 记忆评测集（虚构样例）",
                "url": "https://longtrace.invalid/preprint/summary",
                "domain": "longtrace.invalid",
                "published_at": self.longtrace_article_date.isoformat(),
                "topic": "Agent",
                "content": "\n\n".join(self.longtrace_quotes["d5"]),
            },
            "d6": {
                "title": "ModelForge SDK 1.3 支持工具调用事件流（虚构样例）",
                "url": "https://modelforge.invalid/changelog/1-3",
                "domain": "modelforge.invalid",
                "published_at": self.modelforge_date.isoformat(),
                "topic": "模型工具",
                "content": "\n\n".join(self.modelforge_quote),
            },
            "d7": {
                "title": "Lattice Inference 2.4 兼容性说明（虚构样例，补搜资料）",
                "url": "https://lattice.invalid/docs/2-4-compatibility",
                "domain": "lattice.invalid",
                "published_at": self.compat_date.isoformat(),
                "topic": "推理部署",
                "content": "\n\n".join(self.lattice_quotes["d7"]),
            },
            "d8": {
                "title": "LongTrace 评测集 1.0 正式发布（虚构样例，补搜资料）",
                "url": "https://longtrace.invalid/releases/1-0",
                "domain": "longtrace.invalid",
                "published_at": self.longtrace_release_date.isoformat(),
                "topic": "Agent",
                "content": "\n\n".join(self.longtrace_quotes["d8"]),
            },
        }

    def events_for_docs(self, doc_ids: set[str]) -> list[dict]:
        events: list[dict] = []
        if "d1" in doc_ids or "d2" in doc_ids:
            events.append(
                {
                    "event_key": "aster-agent-kit:0.8",
                    "title": "Aster Agent Kit 0.8：权限网关默认开启，加入确定性回放",
                    "project": "Aster Agent Kit",
                    "topic": "Agent",
                    "event_type": "release",
                    "event_date": self.aster_date.isoformat(),
                    "date_confidence": "confirmed",
                    "summary": "Aster Agent Kit 0.8 默认启用工具权限网关，并加入可复现失败步骤的确定性回放；现有编排 API 不变。",
                    "why_it_matters": "工具权限与回放能力直接影响 Agent 的可控性和线上排障成本，适合关注工具调用治理的团队。",
                    "confidence": "high",
                    "facts": [
                        {
                            "statement": "Aster Agent Kit 0.8 默认启用工具权限网关，未声明的外部工具调用会被拒绝。",
                            "category": "api",
                            "conditions": "",
                            "evidence": [{"document_id": "d1", "quote": self.aster_quote[0]}],
                        },
                        {
                            "statement": "该版本加入确定性回放，可记录模型输入、工具参数和返回结果以复现失败步骤。",
                            "category": "release",
                            "conditions": "",
                            "evidence": [{"document_id": "d1", "quote": self.aster_quote[1]}],
                        },
                        {
                            "statement": "升级需要 Node.js 20 或更高版本，现有 Agent 编排 API 不变。",
                            "category": "compatibility",
                            "conditions": "Node.js 20+",
                            "evidence": [{"document_id": "d1", "quote": self.aster_quote[2]}],
                        },
                    ],
                    "unresolved": [],
                    "resolved_unresolved": [],
                    "primary_document_id": "d1",
                }
            )
        lattice_ids = {"d3", "d4", "d7"} & doc_ids
        if lattice_ids:
            facts = []
            unresolved = []
            resolved = []
            if "d3" in doc_ids:
                facts.extend(
                    [
                        {
                            "statement": "Lattice Inference 2.4 新增 INT4 KV Cache 与端侧运行时。",
                            "category": "release",
                            "conditions": "",
                            "evidence": [{"document_id": "d3", "quote": self.lattice_quote_1}],
                        },
                        {
                            "statement": "官方基准称首 token 延迟降低 31%，吞吐提升 18%。",
                            "category": "performance",
                            "conditions": "24GB RTX 4090、batch size 1、2K 上下文、FP16 基线",
                            "evidence": [{"document_id": "d3", "quote": self.lattice_quote_2}],
                        },
                        {
                            "statement": "该版本要求 CUDA 12.4 及以上，并支持 Jetson Orin 端侧部署。",
                            "category": "compatibility",
                            "conditions": "CUDA 12.4+；Jetson Orin 系列",
                            "evidence": [{"document_id": "d3", "quote": self.lattice_quote_3}],
                        },
                    ]
                )
            if "d4" in doc_ids:
                facts.append(
                    {
                        "statement": "社区测试在 Jetson Orin 8GB 上观察到 INT4 KV Cache 回退到 FP16。",
                        "category": "compatibility",
                        "conditions": "Jetson Orin 8GB、2K 上下文、单并发",
                        "evidence": [{"document_id": "d4", "quote": self.edge_quote_1}],
                    }
                )
                unresolved.append(CONFLICT_NOTE)
            if "d7" in doc_ids:
                facts.extend(
                    [
                        {
                            "statement": "官方兼容性说明确认 INT4 仅在 Jetson Orin 16GB 及以上启用，8GB 会自动回退到 FP16。",
                            "category": "compatibility",
                            "conditions": "Jetson Orin 16GB+ 启用 INT4；8GB 回退 FP16",
                            "evidence": [{"document_id": "d7", "quote": self.compat_quote_1}],
                        },
                        {
                            "statement": "24GB RTX 4090 的基准使用 batch size 1、2K 上下文和 FP16 基线。",
                            "category": "performance",
                            "conditions": "24GB RTX 4090、batch size 1、2K 上下文、FP16 基线",
                            "evidence": [{"document_id": "d7", "quote": self.compat_quote_2}],
                        },
                    ]
                )
                resolved.extend([CONFLICT_NOTE, "支持边界尚不明确。"])
            events.append(
                {
                    "event_key": "lattice-inference:2.4",
                    "title": "Lattice Inference 2.4：INT4 KV Cache 进入端侧，8GB 设备会回退",
                    "project": "Lattice Inference",
                    "topic": "推理部署",
                    "event_type": "release",
                    "event_date": self.lattice_date.isoformat(),
                    "date_confidence": "confirmed",
                    "summary": (
                        "Lattice Inference 2.4 新增 INT4 KV Cache 和端侧运行时；官方兼容性说明确认 8GB Jetson 设备会回退到 FP16，性能提升只在给定基线条件下成立。"
                        if "d7" in doc_ids
                        else "Lattice Inference 2.4 新增 INT4 KV Cache 和端侧运行时；官方称支持 Jetson Orin，但第三方实测在 8GB 设备观察到 INT4 回退，支持边界仍待确认。"
                    ),
                    "why_it_matters": "量化与端侧兼容边界会直接影响部署选型；31% 的延迟收益需要和显存条件、硬件基线一起阅读。",
                    "confidence": "high",
                    "facts": facts,
                    "unresolved": unresolved,
                    "resolved_unresolved": resolved if "d7" in doc_ids else [],
                    "primary_document_id": "d3" if "d3" in doc_ids else "d7",
                }
            )
        longtrace_ids = {"d5", "d8"} & doc_ids
        if longtrace_ids:
            facts = []
            if "d5" in doc_ids:
                facts.extend(
                    [
                        {
                            "statement": "LongTrace 是面向长任务的 Agent 记忆评测集。",
                            "category": "research",
                            "conditions": "",
                            "evidence": [{"document_id": "d5", "quote": self.longtrace_quote_1}],
                        },
                        {
                            "statement": "LongTrace 包含 120 个多轮任务，覆盖跨会话检索、冲突记忆更新与延迟回忆。",
                            "category": "research",
                            "conditions": "",
                            "evidence": [{"document_id": "d5", "quote": self.longtrace_quote_2}],
                        },
                    ]
                )
            if "d8" in doc_ids:
                facts.extend(
                    [
                        {
                            "statement": "LongTrace 评测集 1.0 正式发布日期已由官方公告确认。",
                            "category": "release",
                            "conditions": "",
                            "evidence": [{"document_id": "d8", "quote": self.longtrace_release_quote_1}],
                        },
                        {
                            "statement": "正式版本在 120 个多轮任务之外新增 20 个冲突记忆更新用例。",
                            "category": "research",
                            "conditions": "",
                            "evidence": [{"document_id": "d8", "quote": self.longtrace_release_quote_2}],
                        },
                    ]
                )
            events.append(
                {
                    "event_key": "longtrace:1.0",
                    "title": "LongTrace 发布 Agent 记忆评测集，覆盖冲突记忆更新",
                    "project": "LongTrace",
                    "topic": "Agent",
                    "event_type": "research",
                    "event_date": (
                        self.longtrace_release_date.isoformat() if "d8" in doc_ids else None
                    ),
                    "date_confidence": "confirmed" if "d8" in doc_ids else "unknown",
                    "summary": (
                        "LongTrace 1.0 正式发布，用 120 个多轮任务和 20 个冲突记忆用例评测 Agent 的跨会话检索与延迟回忆。"
                        if "d8" in doc_ids
                        else "LongTrace 用 120 个多轮任务评测 Agent 的跨会话检索、冲突记忆更新和延迟回忆；正式版本日期尚待确认。"
                    ),
                    "why_it_matters": "记忆评测从单轮召回转向跨会话与冲突更新，更接近长期运行 Agent 的失效模式。",
                    "confidence": "medium",
                    "facts": facts,
                    "unresolved": [] if "d8" in doc_ids else [DATE_UNKNOWN_NOTE],
                    "resolved_unresolved": [DATE_UNKNOWN_NOTE] if "d8" in doc_ids else [],
                    "primary_document_id": "d8" if "d8" in doc_ids else "d5",
                }
            )
        if "d6" in doc_ids:
            events.append(
                {
                    "event_key": "modelforge-sdk:1.3",
                    "title": "ModelForge SDK 1.3 支持工具调用事件流",
                    "project": "ModelForge SDK",
                    "topic": "模型工具",
                    "event_type": "release",
                    "event_date": self.modelforge_date.isoformat(),
                    "date_confidence": "confirmed",
                    "summary": "ModelForge SDK 1.3 增加工具调用事件的流式返回，并保持 v1 API 兼容；运行时要求 Python 3.10 以上。",
                    "why_it_matters": "工具参数生成过程可流式观测，有利于降低长工具调用的等待感并改进调试体验。",
                    "confidence": "high",
                    "facts": [
                        {
                            "statement": "ModelForge SDK 1.3 新增工具调用事件的流式返回。",
                            "category": "api",
                            "conditions": "",
                            "evidence": [{"document_id": "d6", "quote": self.modelforge_quote[0]}],
                        },
                        {
                            "statement": "开发者可在工具参数生成过程中接收增量事件，并在工具完成后获得结构化结果。",
                            "category": "api",
                            "conditions": "",
                            "evidence": [{"document_id": "d6", "quote": self.modelforge_quote[1]}],
                        },
                        {
                            "statement": "该版本保持 v1 API 兼容，要求 Python 3.10 及以上。",
                            "category": "compatibility",
                            "conditions": "Python 3.10+",
                            "evidence": [{"document_id": "d6", "quote": self.modelforge_quote[2]}],
                        },
                    ],
                    "unresolved": [],
                    "resolved_unresolved": [],
                    "primary_document_id": "d6",
                }
            )
        return events


class DemoSearchTool(SearchTool):
    def __init__(self, corpus: DemoCorpus, delay_seconds: float = 0.0):
        self.corpus = corpus
        self.delay_seconds = delay_seconds

    def search(self, spec: QuerySpec, *, window: str, limit: int) -> list[SearchHit]:
        text = spec.text.casefold()
        candidates: list[str] = []
        if spec.round > 0:
            if "longtrace" in text or "记忆" in text:
                candidates = ["d8"]
            elif "lattice" in text or "推理" in text:
                candidates = ["d7"]
            elif "agent" in text or "工具" in text:
                candidates = ["d1", "d2"]
            elif "sdk" in text or "modelforge" in text or "模型" in text:
                candidates = ["d6"]
        else:
            if "longtrace" in text or "记忆" in text or "memory" in text:
                candidates = ["d5"]
            elif "aster" in text or "agent kit" in text:
                candidates = ["d1", "d2"]
            elif "推理" in text or "lattice" in text or "inference" in text or "量化" in text:
                candidates = ["d3", "d4"]
            elif "modelforge" in text or "sdk" in text or "模型" in text:
                candidates = ["d6"]
            elif "工具调用" in text or "agent" in text:
                candidates = ["d1", "d2"]
            else:
                # Custom demo topics intentionally have no fabricated relevance.
                candidates = []
        hits = []
        for index, doc_id in enumerate(candidates[:limit]):
            doc = self.corpus.docs[doc_id]
            hits.append(
                SearchHit(
                    title=doc["title"],
                    url=doc["url"],
                    snippet=doc["content"][:220],
                    score=max(0.55, 0.95 - 0.1 * index),
                    published_date=doc["published_at"],
                    domain=doc["domain"],
                )
            )
        return hits


class DemoPageReader(PageReader):
    def __init__(self, corpus: DemoCorpus):
        self.corpus = corpus

    def read(self, url: str, *, timeout_seconds: float | None = None) -> ReadResult:
        for doc in self.corpus.docs.values():
            if doc["url"] == url:
                return ReadResult(
                    ok=True,
                    url=url,
                    final_url=url,
                    title=doc["title"],
                    content=doc["content"],
                    published_at=doc["published_at"],
                    language="zh",
                    content_type="text/html",
                    byte_size=len(doc["content"].encode("utf-8")),
                )
        return ReadResult(ok=False, url=url, error="演示语料中没有这个页面")


class DemoLLM(LLMClient):
    """Deterministic, local scripted responses. No model or network is called."""

    def __init__(self, corpus: DemoCorpus):
        self.corpus = corpus

    @staticmethod
    def _usage() -> dict:
        return {"tokens_in": 0, "tokens_out": 0}

    def plan_queries(self, context: dict[str, Any]) -> tuple[dict, dict]:
        queries = []
        topics = context.get("topics", [])
        focus_keywords = list(context.get("focus_keywords") or [])
        focus_note = f"；细分兴趣：{'、'.join(focus_keywords)}" if focus_keywords else ""
        for topic in topics:
            if topic == "Agent":
                queries.extend(
                    [
                        {
                            "text": "Aster Agent Kit 0.8 release notes official",
                            "purpose": "寻找 Aster Agent Kit 官方发布说明，验证权限网关与回放能力",
                            "strategy": "official",
                            "topic": topic,
                            "language": "en",
                            "domains": [],
                        },
                        {
                            "text": "LongTrace Agent 记忆 评测集 最新进展",
                            "purpose": "发现 Agent 记忆评测方向的近期新事件",
                            "strategy": "open",
                            "topic": topic,
                            "language": "zh",
                            "domains": [],
                        },
                    ]
                )
            elif topic == "推理部署":
                queries.append(
                    {
                        "text": "推理引擎 量化 KV Cache 端侧 最新发布",
                        "purpose": "发现推理引擎在量化与端侧部署上的更新和兼容性约束",
                        "strategy": "open",
                        "topic": topic,
                        "language": "zh",
                        "domains": [],
                    }
                )
            elif topic == "模型工具":
                queries.append(
                    {
                        "text": "ModelForge SDK 工具调用 流式 更新",
                        "purpose": "发现模型开发工具与 SDK 的近期变化",
                        "strategy": "official",
                        "topic": topic,
                        "language": "zh",
                        "domains": [],
                    }
                )
            else:
                queries.append(
                    {
                        "text": f"{topic} 最新发布 更新",
                        "purpose": f"尝试发现“{topic}”的近期变化（演示语料可能不覆盖）",
                        "strategy": "open",
                        "topic": topic,
                        "language": "zh",
                        "domains": [],
                    }
                )
        queries = queries[: context.get("limit", 5)]
        return {
            "queries": queries,
            "notes": "演示模式使用固定虚构语料，展示中英文查询、正文读取与补搜闭环；查询顺序不消耗远程额度。"
            + focus_note,
        }, self._usage()

    def extract_events(self, context: dict[str, Any]) -> tuple[dict, dict]:
        url_to_key = {doc["url"]: key for key, doc in self.corpus.docs.items()}
        id_for_key = {
            url_to_key[doc["url"]]: doc["id"]
            for doc in context.get("documents", [])
            if doc.get("url") in url_to_key
        }
        events = self.corpus.events_for_docs(set(id_for_key))
        # The orchestrator assigns sequential document IDs by discovery order, so
        # remap the demo corpus' stable internal IDs to the IDs seen by this run.
        for event in events:
            for fact in event.get("facts", []):
                for evidence in fact.get("evidence", []):
                    evidence["document_id"] = id_for_key.get(
                        evidence["document_id"], evidence["document_id"]
                    )
            event["primary_document_id"] = id_for_key.get(
                event.get("primary_document_id", ""), event.get("primary_document_id", "")
            )
        return {"events": events, "notes": "演示模式固定样例抽取。"}, self._usage()

    def analyze_gaps(self, context: dict[str, Any]) -> tuple[dict, dict]:
        gaps = []
        for event in context.get("events", []):
            unresolved = event.get("unresolved", [])
            if event.get("topic") == "推理部署" and any("冲突" in item for item in unresolved):
                gaps.append(
                    {
                        "reason_code": "conflict",
                        "description": "Lattice Inference 2.4 在 Jetson 8GB 上的官方支持边界存在冲突，需要原始兼容性说明。",
                        "topic": "推理部署",
                        "priority": "high",
                        "query": {
                            "text": "Lattice Inference 2.4 Jetson INT4 兼容性 官方说明",
                            "purpose": "寻找原始兼容性文档，解释 8GB 设备的 INT4 回退差异",
                            "strategy": "official",
                            "domains": [],
                        },
                    }
                )
            if event.get("topic") == "Agent" and not event.get("event_date"):
                gaps.append(
                    {
                        "reason_code": "ambiguous_date",
                        "description": "LongTrace 只找到预印本摘要，正式事件日期不明确。",
                        "topic": "Agent",
                        "priority": "medium",
                        "query": {
                            "text": "LongTrace 评测集 正式发布日期 官方公告",
                            "purpose": "确认正式发布时间，避免把文章发布时间当作事件日期",
                            "strategy": "official",
                            "domains": [],
                        },
                    }
                )
        return {"gaps": gaps[:3], "notes": "演示模式固定缺口分析。"}, self._usage()


def build_demo_bundle(now: datetime):
    corpus = DemoCorpus(now)
    return DemoSearchTool(corpus), DemoPageReader(corpus), DemoLLM(corpus), corpus
