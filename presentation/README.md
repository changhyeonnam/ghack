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
- Benchmark numbers (slide 12) are typed in `build_deck.py` from the live run in `benchmark/results/LIVE_RUN_2026-10-15.md` and `REPORT.md`.
- Video and app links: set `VIDEO_URL` and `APP_URL` at the top of `build_deck.py` and rebuild.
