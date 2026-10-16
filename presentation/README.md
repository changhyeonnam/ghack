# Presentation

`LedgerLens_AI_Builder_Cup_Submission.pptx` is the submission deck built on the official AI Builder Cup template
(`build/template_plus2.pptx` = template + two extra content slides). `.pdf` is the export for submission.

## Rebuild

```bash
cd presentation/build
pip install python-pptx matplotlib pillow
python diagrams.py && python diagrams2.py      # renders img/*.png (problem chain, journey, lanes, pipeline, swimlane flow, architecture, stack, roadmap, checks map)
python build_deck.py                          # fills template_plus2.pptx -> ../LedgerLens_AI_Builder_Cup_Submission.pptx
soffice --headless --convert-to pdf ../LedgerLens_AI_Builder_Cup_Submission.pptx
```

- `build/shots/v2_*.jpg` are prototype screenshots (light theme). Replace with fresh captures under the same names and rebuild.
- Benchmark and cost numbers (slides 4, 10, 11, 13) are typed in `build_deck.py` and come from the live Gemini run of 2026-10-15 (`benchmark/results/REPORT.md`, `LIVE_RUN_2026-10-15.md`).
- Links slide (14) and team slide (1) are filled in at submission.
