# Deck build kit

Regenerates `docs/LedgerLens_AI_Builder_Cup_Submission.pptx` from the official template.

```bash
pip install python-pptx matplotlib pillow
python diagrams.py && python diagrams2.py   # renders img/*.png (flow, architecture, problem chain, journey, lanes, pipeline, stack, roadmap)
python build_deck.py      # fills template_plus2.pptx (template + 2 extra content slides) -> LedgerLens_AI_Builder_Cup_Submission.pptx
```

- `shots/` holds prototype screenshots used on the "Wireframes" and "Snapshots" slides. Replace them with fresh captures (same file names) and rebuild.
- Benchmark numbers on slide 11 are typed in `build_deck.py` (search for "Planted traps caught"); update them from `benchmark/results/REPORT.md` after the live Gemini run.
- Convert to PDF for submission: `soffice --headless --convert-to pdf LedgerLens_AI_Builder_Cup_Submission.pptx`.
