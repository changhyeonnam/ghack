#!/usr/bin/env python
"""LedgerLens benchmark: trap recall, false positives, unsourced numbers, extraction + evidence-link accuracy,
time and cost, for the full agent team AND the single-prompt baseline.

Usage (from repo root):
  backend/.venv/bin/python benchmark/run_benchmark.py                 # uses .env (live if GOOGLE_API_KEY, else mock)
  backend/.venv/bin/python benchmark/run_benchmark.py --no-baseline --cases A,B
Writes benchmark/results/latest.json and benchmark/results/REPORT.md.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.agents.baseline import run_baseline  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.llm.groundtruth import GroundTruth, load_traps  # noqa: E402
from app.pipeline import Pipeline  # noqa: E402
from app.schemas import ChallengeResult, DocumentExtraction, Memo  # noqa: E402
from app.storage import build_repository  # noqa: E402
from app.tools.checks import NUMERAL, DATEISH  # noqa: E402

QID = re.compile(r"\bQ(1[0-2]|[1-9])\b")


def fmt_amounts(a: float) -> list[str]:
    i = int(round(a))
    out = [f"{i:,}", str(i), f"{i:,}".replace(",", "."), f"{i:,.2f}"]
    if i >= 1_000_000:  # "24M", "24.5M"; never for small amounts ("0M" would match any "50M")
        out.append(f"{i/1e6:.1f}M".replace(".0M", "M"))
    return out


def _has_amount(text: str, a: float) -> bool:
    # whole-number match: "3,000" must not hit "13,000" or "3,000,000"
    return any(re.search(rf"(?<![\d.,]){re.escape(s)}(?![\d]|[.,]\d)", text) for s in fmt_amounts(a))


def trap_matches(trap: dict, text: str, question_id: str | None, evidence_docs: set[str], fn_to_doc: dict[str, str],
                 strict: bool = True) -> bool:
    """strict (default, reported): the trap's identifying evidence must appear. A trap defined by amounts needs an
    amount; one defined by files needs the document; only traps with neither fall back to keywords. lenient = the
    original any-of rule, kept for comparison with earlier reports."""
    t = text.lower()
    m = trap["match"]
    kw = any(k.lower() in t for k in m.get("any_keywords", [])) and all(k.lower() in t for k in m.get("all_keywords", []))
    amounts = m.get("amounts") or []
    files = m.get("filenames_any") or []
    amt = any(_has_amount(text, a) for a in amounts)
    docs = {fn_to_doc.get(f) for f in files} - {None}
    doc_hit = bool(docs & evidence_docs) or any(f.lower() in t for f in files)
    q_ok = question_id is None or question_id == "CUSTOM" or question_id in trap["expected_question_ids"]
    if not strict:
        return (kw or amt or doc_hit) if question_id is None else q_ok and (kw or amt or doc_hit)
    if amounts:
        ident = amt
    elif files:
        ident = doc_hit
    else:
        ident = kw
    return q_ok and ident


def assign_hits(traps: list[dict], items: list[tuple[str, str, str | None, set[str]]], fn_to_doc: dict[str, str],
                strict: bool = True) -> dict[str, list[str]]:
    """Each objection/concern counts for at most one trap (strict); traps with fewer candidates pick first."""
    cands = {tr["id"]: [i for i, txt, q, ev in items if trap_matches(tr, txt, q, ev, fn_to_doc, strict)] for tr in traps}
    if not strict:
        return cands
    used: set[str] = set()
    hits: dict[str, list[str]] = {}
    for tid in sorted(cands, key=lambda k: (len(cands[k]) or 99, k)):
        free = [i for i in cands[tid] if i not in used]
        hits[tid] = free[:1]
        used.update(free[:1])
    return {tr["id"]: hits[tr["id"]] for tr in traps}


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return [round(c - h, 2), round(c + h, 2)]


def count_unsourced_baseline(out: dict) -> int:
    n = sum(1 for f in out.get("figures", []) if not f.get("source_refs"))
    for s in out.get("sections", []):
        for p in s.get("paragraphs", []):
            for mm in NUMERAL.finditer(p):
                tok = mm.group(0).rstrip(".,")
                if not DATEISH.match(tok):
                    n += 1
    return n


def extraction_accuracy(exs: list[DocumentExtraction], case, gt: GroundTruth, manifest: dict) -> dict:
    fn = {d.doc_id: d.filename for d in case.documents}
    rows_gt = rows_ok = bbox_ok = 0
    for ex in exs:
        if not ex.bank_statement:
            continue
        _, rec = gt.ground_truth_for(manifest, fn[ex.doc_id])
        if not rec:
            continue
        gt_rows = rec["transactions"]
        rows_gt += len(gt_rows)
        key = lambda d, deb, cr: (d, round(float(deb or 0)), round(float(cr or 0)))  # noqa: E731
        extracted = {}
        for t in ex.bank_statement.transactions:
            extracted.setdefault(key(t.date, t.debit, t.credit), []).append(t)
        for g in gt_rows:
            cands = extracted.get(key(g["date"], g.get("debit"), g.get("credit")))
            if not cands:
                continue
            t = cands.pop(0)
            rows_ok += 1
            gb, tb = g.get("bbox"), t.source.bbox
            if gb and tb and t.source.page == g.get("page", 1):
                cy = (tb.ymin + tb.ymax) / 2
                if gb[0] - 8 <= cy <= gb[2] + 8:
                    bbox_ok += 1
    return {"gt_rows": rows_gt, "rows_matched": rows_ok, "row_accuracy": round(rows_ok / rows_gt, 4) if rows_gt else None,
            "evidence_link_accuracy": round(bbox_ok / rows_ok, 4) if rows_ok else None}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="A,B,C")
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--data-dir", default=str(ROOT / "data" / "runtime_benchmark"))
    args = ap.parse_args()
    os.environ.setdefault("LEDGERLENS_LOCAL_DATA_DIR", args.data_dir)
    os.environ["LEDGERLENS_DEMO_SEED_ON_STARTUP"] = "false"
    get_settings.cache_clear()
    settings = get_settings()
    repo = build_repository(settings)
    pipe = Pipeline(repo, settings)
    gt = GroundTruth(str(settings.synth_dir))
    traps = load_traps(str(settings.synth_dir))
    wanted = set(args.cases.split(","))
    print(f"mode={settings.resolved_llm_mode} models flash={settings.model_flash} pro={settings.model_pro}")

    ids = pipe.seed_demo_cases(force=True)
    results = []
    for cid in ids:
        case = repo.get_case(cid)
        sid = next(t.split(":")[1] for t in case.tags if t.startswith("synthetic:"))
        if sid not in wanted:
            continue
        manifest = gt.manifests[sid]
        fn_to_doc = {d.filename: d.doc_id for d in case.documents}
        print(f"\n=== Case {sid} {case.name} ({len(case.documents)} docs) ===")
        t0 = time.time()
        case = await pipe.run_all(cid)
        elapsed = round(time.time() - t0, 1)
        memo = Memo.model_validate(repo.get_artifact(cid, "memo"))
        ch = ChallengeResult.model_validate(repo.get_artifact(cid, "challenge"))
        exs = [DocumentExtraction.model_validate(x) for x in repo.get_artifact(cid, "extractions")["items"]]
        case_traps = [t for t in traps if t["case_id"] == sid]
        items = [(o.id, f"{o.title} {o.claim} {o.tool_evidence or ''}", o.question_id, {r.doc_id for r in o.evidence_refs}) for o in ch.objections]
        hits = assign_hits(case_traps, items, fn_to_doc)
        lenient_hits = assign_hits(case_traps, items, fn_to_doc, strict=False)
        unsourced = len(memo.unsourced_numerals) + len(memo.unresolved_figure_ids) + sum(1 for f in memo.figures if not f.is_sourced())
        acc = extraction_accuracy(exs, case, gt, manifest)
        row = {"case": sid, "name": case.name, "expected_outcome": manifest.get("expected_outcome"), "recommendation": memo.draft.recommendation,
               "n_documents": len(case.documents), "seconds": elapsed, "cost_usd": case.stats.total_cost_usd, "tokens": case.stats.total_tokens,
               "llm_calls": case.stats.n_llm_calls, "cached_calls": case.stats.n_cached_calls, "n_figures": len(memo.figures), "unsourced_numbers": unsourced,
               "n_objections": len(ch.objections), "objections": [{"id": o.id, "q": o.question_id, "severity": o.severity.value, "title": o.title} for o in ch.objections],
               "traps_total": len(case_traps), "traps_caught": sum(1 for v in hits.values() if v), "trap_hits": hits,
               "traps_caught_lenient": sum(1 for v in lenient_hits.values() if v), "extraction": acc}
        print(f"  recommendation={memo.draft.recommendation} objections={len(ch.objections)} traps {row['traps_caught']}/{len(case_traps)} unsourced={unsourced} "
              f"cost=${case.stats.total_cost_usd:.3f} time={elapsed}s extraction={acc}")
        if not args.no_baseline:
            t1 = time.time()
            base = await run_baseline(case, repo=repo, settings=settings, mock_context=pipe.mock_context(case))
            bitems = [(c["title"], f"{c['title']} {c['claim']}", None, set()) for c in base.get("concerns", [])]
            bhits = assign_hits(case_traps, bitems, fn_to_doc)
            row["baseline"] = {"recommendation": base.get("recommendation"), "traps_caught": sum(1 for v in bhits.values() if v), "trap_hits": bhits,
                               "n_concerns": len(base.get("concerns", [])), "unsourced_numbers": count_unsourced_baseline(base), "n_figures": len(base.get("figures", [])),
                               "seconds": round(time.time() - t1, 1), "cost_usd": base["_usage"]["cost_usd"], "tokens": base["_usage"]["input_tokens"] + base["_usage"]["output_tokens"] + base["_usage"]["thinking_tokens"]}
            repo.save_artifact(cid, "baseline", base)
            print(f"  baseline: recommendation={base.get('recommendation')} traps {row['baseline']['traps_caught']}/{len(case_traps)} unsourced={row['baseline']['unsourced_numbers']} cost=${base['_usage']['cost_usd']:.3f}")
        results.append(row)

    trap_rows = [r for r in results if r["traps_total"]]
    clean = [r for r in results if not r["traps_total"]]
    total_traps = sum(r["traps_total"] for r in trap_rows)
    caught = sum(r["traps_caught"] for r in trap_rows)
    b_caught = sum(r.get("baseline", {}).get("traps_caught", 0) for r in trap_rows)
    all_obj = sum(r["n_objections"] for r in results) or 1
    summary = {"mode": settings.resolved_llm_mode, "model_flash": settings.model_flash, "model_pro": settings.model_pro, "traps_total": total_traps, "traps_caught": caught,
               "trap_recall": round(caught / total_traps, 3) if total_traps else None,
               "trap_recall_ci95": wilson(caught, total_traps), "traps_caught_lenient": sum(r.get("traps_caught_lenient", 0) for r in trap_rows),
               "baseline_traps_caught": b_caught if not args.no_baseline else None, "baseline_trap_recall": round(b_caught / total_traps, 3) if total_traps and not args.no_baseline else None,
               "clean_case_objections": sum(r["n_objections"] for r in clean), "false_positive_share": round(sum(r["n_objections"] for r in clean) / all_obj, 3),
               "unsourced_numbers": sum(r["unsourced_numbers"] for r in results), "baseline_unsourced_numbers": sum(r.get("baseline", {}).get("unsourced_numbers", 0) for r in results) if not args.no_baseline else None,
               "avg_seconds": round(sum(r["seconds"] for r in results) / max(1, len(results)), 1), "avg_cost_usd": round(sum(r["cost_usd"] for r in results) / max(1, len(results)), 4),
               "extraction_row_accuracy": None, "evidence_link_accuracy": None}
    accs = [r["extraction"] for r in results if r["extraction"]["gt_rows"]]
    if accs:
        summary["extraction_row_accuracy"] = round(sum(a["rows_matched"] for a in accs) / sum(a["gt_rows"] for a in accs), 4)
        matched = sum(a["rows_matched"] for a in accs)
        summary["evidence_link_accuracy"] = round(sum((a["evidence_link_accuracy"] or 0) * a["rows_matched"] for a in accs) / matched, 4) if matched else None
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "summary": summary, "cases": results}
    res_dir = ROOT / "benchmark" / "results"
    res_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "latest.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), "utf-8")
    repo.save_global("benchmark_latest", out)
    note = ("> **Mock mode**: no Gemini calls were made. Extraction comes from the synthetic answer key and the Challenger is the deterministic "
            "battery only, so this measures the pipeline and the tools, not the model. The baseline row is a stub in this mode. Re-run with "
            "GOOGLE_API_KEY set for the real numbers.") if summary["mode"] == "mock" else ""
    md = [f"# LedgerLens benchmark ({summary['mode']}, {summary['model_pro']})", "", f"Generated {out['generated_at']}", "", note, "",
          "Scoring is strict: an objection counts for a trap only if it carries the trap's identifying evidence (amount or "
          "document; keywords only for traps defined by neither) under an expected checklist question, and each objection "
          f"counts for at most one trap. The earlier any-keyword rule would give {summary['traps_caught_lenient']}/{total_traps}. "
          f"95% Wilson interval for recall: {summary['trap_recall_ci95']}. Synthetic data, n = 3 businesses.", "",
          "| Metric | LedgerLens | Single-prompt baseline | Target |", "|---|---|---|---|",
          f"| Trap recall | {caught}/{total_traps} ({summary['trap_recall']}) | {summary['baseline_traps_caught']}/{total_traps} ({summary['baseline_trap_recall']}) | >= 16/20 |",
          f"| Unsourced numbers | {summary['unsourced_numbers']} | {summary['baseline_unsourced_numbers']} | 0 |",
          f"| Objections on clean case A | {summary['clean_case_objections']} (share {summary['false_positive_share']}) | - | <= 20% |",
          f"| Extraction row accuracy | {summary['extraction_row_accuracy']} | - | >= 97% |",
          f"| Evidence-link accuracy | {summary['evidence_link_accuracy']} | - | >= 95% |",
          f"| Avg time per case | {summary['avg_seconds']} s | - | <= 180 s |",
          f"| Avg cost per case | ${summary['avg_cost_usd']} | - | <= $0.50 |", "", "## Per case", ""]
    for r in results:
        md.append(f"### Case {r['case']} - {r['name']}: expected {r['expected_outcome']}, got {r['recommendation']}")
        md.append(f"traps {r['traps_caught']}/{r['traps_total']}, objections {r['n_objections']}, unsourced {r['unsourced_numbers']}, {r['seconds']} s, ${r['cost_usd']}, tokens {r['tokens']}")
        for tid, h in r["trap_hits"].items():
            tr = next(t for t in traps if t["id"] == tid)
            md.append(f"- {tid} {tr['title']}: {'caught by ' + ','.join(h) if h else 'MISSED'}" + (f" | baseline: {'caught' if r.get('baseline', {}).get('trap_hits', {}).get(tid) else 'missed'}" if r.get("baseline") else ""))
        md.append("")
    (res_dir / "REPORT.md").write_text("\n".join(md), "utf-8")
    print("\n" + "\n".join(md[:14]))


if __name__ == "__main__":
    asyncio.run(main())
