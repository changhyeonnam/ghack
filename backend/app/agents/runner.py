"""Runs ADK agents with caching, cost accounting, budget guard and audit traces.

One function, `run_agent`, is used by every stage. It builds the LlmAgent, executes it in a fresh in-memory
session, collects the final text + token usage, validates the output against the agent's schema, and writes a
trace. A content-addressed cache (model + prompt version + inputs) makes demo re-runs free and deterministic.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel

from ..config import Settings
from ..llm import mock_llm  # noqa: F401  (registers the mock model with ADK)
from ..llm import image_ids
from ..llm.mock_llm import MOCK_CONTEXT
from ..llm.pricing import estimate_cost_usd
from ..schemas import AgentTrace, utcnow_iso
from ..storage import Repository

log = logging.getLogger("ledgerlens.agents")


from ..llm import budget
from ..llm.budget import BudgetExceeded  # noqa: F401  (re-exported for callers)


class CacheMiss(RuntimeError):
    pass


_spent_usd = 0.0
_spent_lock = asyncio.Lock()


def spent_usd() -> float:
    return _spent_usd


@dataclass
class AgentSpec:
    name: str                        # intake, extractor:bank_statement, analyst, challenger, explainer, baseline
    instruction: str
    prompt_version: str
    model: str
    output_schema: Optional[type[BaseModel]] = None
    tools: list[Callable[..., Any]] = field(default_factory=list)
    description: str = ""
    max_output_tokens: int = 65536


@dataclass
class AgentResult:
    text: str
    parsed: Optional[dict[str, Any]]
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    duration_ms: int = 0
    model: str = ""
    state: dict[str, Any] = field(default_factory=dict)


def _gen_config(settings: Settings, model: str, max_output_tokens: int) -> types.GenerateContentConfig:
    cfg = types.GenerateContentConfig(temperature=settings.temperature, max_output_tokens=max_output_tokens)
    if model.startswith("mock/"):
        return cfg
    cfg.media_resolution = {
        "low": types.MediaResolution.MEDIA_RESOLUTION_LOW,
        "medium": types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
        "high": types.MediaResolution.MEDIA_RESOLUTION_HIGH,
    }[settings.media_resolution]
    if model.startswith(("gemini-3", "gemini-4")):
        cfg.thinking_config = types.ThinkingConfig(thinking_level=getattr(types.ThinkingLevel, settings.thinking_level.upper()))
    elif "2.5" in model:
        cfg.thinking_config = types.ThinkingConfig(thinking_budget=1024)
    return cfg


def _instruction_provider(text: str) -> Callable[[Any], str]:
    """Wrap as an InstructionProvider so ADK does not treat {fig:...} braces as state templates."""
    def provider(_ctx: Any) -> str:
        return text
    return provider


def build_llm_agent(spec: AgentSpec, settings: Settings, mock: bool) -> LlmAgent:
    model = f"mock/{spec.name.split(':')[0]}" if mock else spec.model
    kwargs: dict[str, Any] = dict(
        name=spec.name.replace(":", "_").replace("-", "_"),
        model=model,
        description=spec.description or spec.name,
        instruction=_instruction_provider(spec.instruction),
        generate_content_config=_gen_config(settings, model, spec.max_output_tokens),
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )
    if spec.output_schema is not None:
        kwargs["output_schema"] = spec.output_schema
        kwargs["output_key"] = "output"
    if spec.tools:
        kwargs["tools"] = list(spec.tools)
    return LlmAgent(**kwargs)


def _cache_lookup(repo: Repository, settings: Settings, keys: list[str]) -> Optional[dict[str, Any]]:
    """Repository cache first (migrating legacy keys to keys[0]), then the read-only cache bundled with the repo."""
    for k in keys:
        hit = repo.cache_get(k)
        if hit:
            if k != keys[0]:
                repo.cache_put(keys[0], hit)
            return hit
    d = settings.bundled_cache_dir
    if d and d.is_dir():
        for k in keys:
            f = d / f"{k}.json"
            if f.is_file():
                return json.loads(f.read_text("utf-8"))
    return None


def cache_key(spec: AgentSpec, parts: list[types.Part], extra: Optional[dict[str, Any]] = None, portable: bool = True) -> str:
    """Content hash of the call. portable=True identifies rendered images by their source document and view (see
    llm/image_ids.py) so a cache built on one OS replays on another; portable=False is the original byte-hash key,
    still read as a fallback so caches built before this change keep working."""
    h = hashlib.sha256()
    if portable:
        h.update(b"v2")
    h.update(spec.model.encode())
    h.update(spec.prompt_version.encode())
    h.update(spec.instruction.encode())
    if spec.output_schema is not None:
        h.update(json.dumps(spec.output_schema.model_json_schema(), sort_keys=True).encode())
    for p in parts:
        if p.text:
            h.update(b"T" + p.text.encode())
        elif p.inline_data and p.inline_data.data:
            ident = image_ids.identity_of(p.inline_data.data) if portable else None
            h.update(b"I" + ident.encode() if ident else b"B" + hashlib.sha256(p.inline_data.data).digest())
    if extra:
        h.update(json.dumps(extra, sort_keys=True, default=str).encode())
    return h.hexdigest()[:40]


def _extract_json(text: str) -> Optional[dict[str, Any]]:
    if not text:
        return None
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        return json.loads(t)
    except Exception:
        pass
    start, end = t.find("{"), t.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(t[start:end + 1])
        except Exception:
            return None
    return None


async def _run_adk(agent: BaseAgent, parts: list[types.Part], app_name: str) -> tuple[dict[str, str], dict[str, Any], dict[str, int]]:
    """Run an ADK agent tree once. Returns (final text per author, session state, token totals)."""
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    session = await runner.session_service.create_session(app_name=app_name, user_id="ledgerlens")
    finals: dict[str, str] = {}
    usage = {"in": 0, "out": 0, "think": 0}
    try:
        async for ev in runner.run_async(user_id="ledgerlens", session_id=session.id,
                                         new_message=types.Content(role="user", parts=parts)):
            um = getattr(ev, "usage_metadata", None)
            if um is not None and not getattr(ev, "partial", False):
                usage["in"] += um.prompt_token_count or 0
                usage["out"] += um.candidates_token_count or 0
                usage["think"] += um.thoughts_token_count or 0
            if ev.error_code and not ev.get_function_calls():
                raise RuntimeError(f"{ev.author}: {ev.error_code} {ev.error_message or ''}")
            if ev.is_final_response() and ev.content and ev.content.parts:
                txt = "".join(p.text or "" for p in ev.content.parts if getattr(p, "text", None))
                if txt.strip():
                    finals[ev.author] = txt
        fresh = await runner.session_service.get_session(app_name=app_name, user_id="ledgerlens", session_id=session.id)
        state = dict(fresh.state) if fresh else {}
    finally:
        try:
            await runner.close()
        except Exception:  # pragma: no cover - best effort
            pass
    return finals, state, usage


async def run_agent(spec: AgentSpec, parts: list[types.Part], *, settings: Settings, repo: Repository, case_id: str,
                    mock_context: Optional[dict[str, Any]] = None, cache_extra: Optional[dict[str, Any]] = None,
                    use_cache: bool = True) -> AgentResult:
    """Execute one agent call with cache, budget and tracing."""
    global _spent_usd
    mode = settings.resolved_llm_mode
    mock = mode == "mock"
    key = cache_key(spec, parts, cache_extra)
    started = time.time()
    trace_id = uuid.uuid4().hex[:12]

    if use_cache and settings.llm_cache_enabled and not mock:
        hit = _cache_lookup(repo, settings, [key, cache_key(spec, parts, cache_extra, portable=False)])
        if hit:
            res = AgentResult(text=hit.get("text", ""), parsed=hit.get("parsed"), cached=True, model=spec.model,
                              input_tokens=hit.get("input_tokens", 0), output_tokens=hit.get("output_tokens", 0),
                              thinking_tokens=hit.get("thinking_tokens", 0), cost_usd=0.0, duration_ms=int((time.time() - started) * 1000),
                              state=hit.get("state", {}))
            repo.add_trace(AgentTrace(id=trace_id, case_id=case_id, agent=spec.name, model=spec.model, prompt_version=spec.prompt_version,
                                      started_at=utcnow_iso(), duration_ms=res.duration_ms, input_tokens=res.input_tokens,
                                      output_tokens=res.output_tokens, thinking_tokens=res.thinking_tokens, cost_usd=0.0, cached=True))
            return res
    live_ok = {a.strip() for a in settings.live_agents_in_cache_only.split(",") if a.strip()}
    if mode == "cache_only" and spec.name.split(":")[0] not in live_ok:
        raise CacheMiss(f"LLM cache miss for {spec.name} while running in cache_only mode")
    if mode == "cache_only" and not (settings.google_api_key or settings.use_vertexai):
        raise CacheMiss(f"{spec.name} needs a live Gemini call; set GOOGLE_API_KEY (this replay has no key)")
    if not mock:
        budget.check(repo, settings)

    agent = build_llm_agent(spec, settings, mock)
    token = MOCK_CONTEXT.set({**(mock_context or {}), "agent": spec.name}) if mock else None
    try:
        last_err: Optional[Exception] = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                finals, state, usage = await asyncio.wait_for(_run_adk(agent, parts, settings.app_name), timeout=settings.llm_timeout_seconds)
                break
            except Exception as e:  # retry transient failures
                last_err = e
                log.warning("agent %s attempt %d failed: %s", spec.name, attempt + 1, e)
                if not mock and budget.is_provider_limit_error(e):  # credits/quota gone: retrying cannot help
                    budget.record_provider_limit(repo, e)
                    budget.check(repo, settings)
                if attempt >= settings.llm_max_retries or mock:
                    raise
                msg = str(e)
                base = 8.0 if ("429" in msg or "RESOURCE_EXHAUSTED" in msg or "503" in msg or "UNAVAILABLE" in msg) else 2.0
                await asyncio.sleep(base * (2 ** attempt) + random.uniform(0, 1))
        else:  # pragma: no cover
            raise last_err or RuntimeError("agent failed")
    finally:
        if token is not None:
            MOCK_CONTEXT.reset(token)

    text = finals.get(agent.name) or (next(iter(finals.values())) if finals else "")
    parsed: Optional[dict[str, Any]] = None
    if spec.output_schema is not None:
        raw = state.get("output")
        if isinstance(raw, dict):
            parsed = raw
        else:
            parsed = _extract_json(text)
        if parsed is None:
            raise RuntimeError(f"{spec.name}: model returned no parseable JSON")
        parsed = spec.output_schema.model_validate(parsed).model_dump(mode="json")
    cost = 0.0 if mock else estimate_cost_usd(spec.model, usage["in"], usage["out"], usage["think"])
    async with _spent_lock:
        _spent_usd += cost
    if cost:
        repo.add_spend(cost)
    res = AgentResult(text=text, parsed=parsed, input_tokens=usage["in"], output_tokens=usage["out"], thinking_tokens=usage["think"],
                      cost_usd=cost, cached=False, duration_ms=int((time.time() - started) * 1000), model=agent.model if isinstance(agent.model, str) else spec.model,
                      state={k: v for k, v in state.items() if isinstance(v, (str, int, float, dict, list))})
    if settings.llm_cache_enabled and not mock:
        repo.cache_put(key, {"text": text, "parsed": parsed, "state": res.state, "input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                             "thinking_tokens": res.thinking_tokens, "model": spec.model, "prompt_version": spec.prompt_version, "agent": spec.name,
                             "cached_at": utcnow_iso()})
    repo.add_trace(AgentTrace(id=trace_id, case_id=case_id, agent=spec.name, model=res.model, prompt_version=spec.prompt_version, started_at=utcnow_iso(),
                              duration_ms=res.duration_ms, input_tokens=res.input_tokens, output_tokens=res.output_tokens, thinking_tokens=res.thinking_tokens,
                              cost_usd=cost, cached=False))
    return res


async def run_sequence(specs: list[AgentSpec], parts: list[types.Part], *, settings: Settings, repo: Repository, case_id: str,
                       mock_context: Optional[dict[str, Any]] = None, cache_extra: Optional[dict[str, Any]] = None) -> list[AgentResult]:
    """Run a SequentialAgent of several LlmAgents in one ADK invocation (shared session state).

    Used by the Challenger: investigator (tools, free text) -> writer (schema). Cached as one unit.
    """
    global _spent_usd
    mode = settings.resolved_llm_mode
    mock = mode == "mock"
    seq_spec = AgentSpec(name="+".join(s.name for s in specs), instruction="\n".join(s.instruction for s in specs),
                         prompt_version="+".join(s.prompt_version for s in specs), model="+".join(s.model for s in specs),
                         output_schema=specs[-1].output_schema)
    key = cache_key(seq_spec, parts, cache_extra)
    started = time.time()
    if settings.llm_cache_enabled and not mock:
        hit = _cache_lookup(repo, settings, [key, cache_key(seq_spec, parts, cache_extra, portable=False)])
        if hit:
            out = []
            for s, r in zip(specs, hit["results"]):
                out.append(AgentResult(text=r.get("text", ""), parsed=r.get("parsed"), cached=True, model=s.model))
                repo.add_trace(AgentTrace(id=uuid.uuid4().hex[:12], case_id=case_id, agent=s.name, model=s.model, prompt_version=s.prompt_version,
                                          started_at=utcnow_iso(), duration_ms=0, cached=True))
            return out
    if mode == "cache_only":
        raise CacheMiss(f"LLM cache miss for {specs[0].name} sequence while running in cache_only mode")
    if not mock:
        budget.check(repo, settings)

    agents = []
    for i, s in enumerate(specs):
        a = build_llm_agent(s, settings, mock)
        if i < len(specs) - 1:
            a.output_key = a.output_key or f"step_{i}"
        agents.append(a)
    seq = SequentialAgent(name="challenger", sub_agents=agents)
    results: list[AgentResult] = []
    token = MOCK_CONTEXT.set({**(mock_context or {}), "agent": specs[0].name}) if mock else None
    try:
        finals, state, usage = await asyncio.wait_for(_run_adk(seq, parts, settings.app_name), timeout=settings.llm_timeout_seconds * 2)
    except Exception as e:
        if not mock and budget.is_provider_limit_error(e):
            budget.record_provider_limit(repo, e)
            budget.check(repo, settings)
        raise
    finally:
        if token is not None:
            MOCK_CONTEXT.reset(token)
    cost = 0.0 if mock else estimate_cost_usd(specs[-1].model, usage["in"], usage["out"], usage["think"])
    async with _spent_lock:
        _spent_usd += cost
    if cost:
        repo.add_spend(cost)
    dur = int((time.time() - started) * 1000)
    for i, (s, a) in enumerate(zip(specs, agents)):
        text = finals.get(a.name, "")
        parsed = None
        if s.output_schema is not None:
            raw = state.get(a.output_key) if a.output_key else None
            parsed = raw if isinstance(raw, dict) else _extract_json(text)
            if parsed is None:
                raise RuntimeError(f"{s.name}: model returned no parseable JSON")
            parsed = s.output_schema.model_validate(parsed).model_dump(mode="json")
        elif not text and a.output_key and isinstance(state.get(a.output_key), str):
            text = state[a.output_key]
        results.append(AgentResult(text=text, parsed=parsed, model=s.model, cached=False, duration_ms=dur if i == len(specs) - 1 else 0,
                                   input_tokens=usage["in"] if i == 0 else 0, output_tokens=usage["out"] if i == 0 else 0,
                                   thinking_tokens=usage["think"] if i == 0 else 0, cost_usd=cost if i == 0 else 0.0))
        repo.add_trace(AgentTrace(id=uuid.uuid4().hex[:12], case_id=case_id, agent=s.name, model=s.model, prompt_version=s.prompt_version, started_at=utcnow_iso(),
                                  duration_ms=dur, input_tokens=results[-1].input_tokens, output_tokens=results[-1].output_tokens,
                                  thinking_tokens=results[-1].thinking_tokens, cost_usd=results[-1].cost_usd, cached=False))
    if settings.llm_cache_enabled and not mock:
        repo.cache_put(key, {"results": [{"text": r.text, "parsed": r.parsed} for r in results], "cached_at": utcnow_iso()})
    return results
