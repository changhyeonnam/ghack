"""Generate Korean versions of the four diagrams used in the deck (img_ko/).
Reads diagrams2.py, swaps every label for its Korean text, and renders with Noto Sans CJK KR."""
import os, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

KO = [
    # process flow
    ('("Loan officer", 2.85, 0.72), ("LedgerLens agents", 1.6, 1.15), ("Underwriter", 0.2, 1.3)', '("대출 담당자", 2.85, 0.72), ("LedgerLens\\n에이전트", 1.6, 1.15), ("심사역", 0.2, 1.3)'),
    ('"Create case, upload", "PDFs, screenshots, photos"', '"케이스 생성, 업로드", "PDF, 캡처, 사진"'),
    ('"Decision + letter", "in the applicant\'s language"', '"결정 + 안내문", "신청자의 언어로"'),
    ('("2", "Intake", "classify, quality flags"', '("2", "접수", "분류, 품질 표시"'),
    ('("3", "Extract", "Gemini, source on every value"', '("3", "추출", "Gemini, 모든 값에 출처"'),
    ('("4", "Cash flow", "Python, deterministic"', '("4", "현금흐름", "Python, 결정론적"'),
    ('("5", "Analyst memo", "cites catalog figures only"', '("5", "분석 메모", "카탈로그 숫자만 인용"'),
    ('("6", "Challenger", "battery + 12 checks"', '("6", "챌린저", "결정론적 검사 + 12개 질문"'),
    ('"about 2 minutes, about USD 0.28 (cold; cached re-run USD 0), every figure carries doc id · page · bbox"', '"약 2분, 약 USD 0.28 (최초 실행, 캐시 재실행은 USD 0), 모든 숫자에 문서 · 페이지 · 좌표"'),
    ('"Review memo", "click any number to its line"', '"메모 검토", "숫자를 누르면 원본 줄로"'),
    ('"Each objection"', '"이의마다"'),
    ('"accept or dismiss"', '"수용 또는 기각"'),
    ('"Sign decision", "conditions, rationale"', '"결정 서명", "조건, 사유"'),
    ('"objections, severity-ranked, with evidence"', '"심각도순 이의, 근거 포함"'),
    ('"Explainer agent writes the letter"', '"설명 에이전트가 안내문 작성"'),
    ('"decisions re-weight the checks"', '"결정이 검사 가중치에 반영"'),
    ('"One pass through LedgerLens: documents in, a signed and explained decision out"', '"서류가 들어가면, 서명되고 설명된 결정이 나옵니다"'),
    # architecture
    ('"Frontend  ·  Firebase Hosting (React + Vite)"', '"프론트엔드  ·  Firebase Hosting (React + Vite)"'),
    ('"Portfolio · New case"', '"포트폴리오 · 새 케이스"'),
    ('"Workbench: memo · evidence viewer with bbox highlight · objections · decision · audit · print export"', '"워크벤치: 메모 · 근거 위치를 강조하는 문서 뷰어 · 이의 · 결정 · 감사 · 인쇄"'),
    ('"Backend  ·  Cloud Run (Python FastAPI + ADK)  ·  scales to zero  ·  cache_only mode for the public demo"', '"백엔드  ·  Cloud Run (Python FastAPI + ADK)  ·  0까지 자동 축소  ·  공개 데모는 cache_only 모드"'),
    ('"ADK Orchestrator"', '"ADK 오케스트레이터"'),
    ('("Intake", "Gemini 3.8 Flash", False)', '("접수", "Gemini 3.8 Flash", False)'),
    ('("Extractor x5", "Flash · Pro optional", False)', '("추출기 x5", "Flash · Pro 선택", False)'),
    ('("Analyst", "Flash · Pro optional", False)', '("분석", "Flash · Pro 선택", False)'),
    ('("Challenger", "investigator → writer", True)', '("챌린저", "조사 → 작성", True)'),
    ('("Explainer", "Gemini 3.8 Flash", False)', '("설명", "Gemini 3.8 Flash", False)'),
    ('"Tools: cash-flow model · balance chain · image hash · PDF text-layer cross-check · date/entity checks · LLM cache · feedback priorities"', '"도구: 현금흐름 모델 · 잔액 연속성 · 이미지 해시 · PDF 텍스트 레이어 교차검증 · 날짜/주체 검사 · LLM 캐시 · 피드백 우선순위"'),
    ('cont(0.08, 0.72, "Data")', 'cont(0.08, 0.72, "데이터")'),
    ('"Cloud Storage: documents, page renders"', '"Cloud Storage: 원본 문서, 페이지 렌더"'),
    ('"Firestore: cases · extractions · memos · objections · decisions · audit · traces"', '"Firestore: 케이스 · 추출 결과 · 메모 · 이의 · 결정 · 감사 · 트레이스"'),
    ('"One Google Cloud project end to end; every agent call is cached by content hash"', '"하나의 Google Cloud 프로젝트로 처음부터 끝까지. 모든 에이전트 호출은 콘텐츠 해시로 캐시"'),
    # roadmap
    ('("Pilot", "Q1 2027", ["One SEA bank or MFI, real consented SME files;", "underwriter decisions replace synthetic traps"]', '("파일럿", "2027년 1분기", ["동남아 은행 또는 MFI 한 곳, 동의받은 실제 SME 서류.", "합성 함정 대신 심사역의 실제 결정으로 평가"]'),
    ('("Integrate", "Q2–Q3 2027", ["Open-banking feeds (Brankas, Finverse) beside PDFs;", "hooks into loan origination systems"]', '("연동", "2027년 2~3분기", ["PDF와 함께 오픈뱅킹 데이터(Brankas, Finverse).", "여신 시스템(LOS)과 연결"]'),
    ('("Scale", "2028", ["Same pattern for trade finance and micro-insurance;", "shared Challenger check library"]', '("확장", "2028년", ["같은 구조를 무역금융과 소액보험에 적용.", "챌린저 검사 라이브러리 공유"]'),
    ('("Synthetic benchmark", ["A small synthetic sample with planted risks;", "real-data results come with the pilot."]', '("합성 데이터 벤치마크", ["위험을 심어 둔 소규모 합성 데이터.", "실제 데이터 결과는 파일럿에서 나옵니다."]'),
    ('("Forged documents", ["Hash and balance-chain checks catch crude edits.", "Open-banking data closes the gap for the rest."]', '("위조 문서", ["해시와 잔액 연속성 검사로 조잡한 편집은 잡습니다.", "나머지는 오픈뱅킹 데이터로 메웁니다."]'),
    ('("Platform sellers", ["Shopee and Grab already lend to their own sellers.", "We target banks and MFIs lending outside platforms."]', '("플랫폼 셀러", ["Shopee와 Grab은 자사 셀러에게 이미 대출합니다.", "대상은 플랫폼 밖에서 대출하는 은행과 MFI입니다."]'),
    ('"What we do not claim yet, and which phase answers it"', '"아직 주장하지 않는 것"'),
    ('"positioning, not a feature"', '"기능이 아니라 포지셔닝"'),
    ('"Where this goes next, and what we do not claim yet"', '"다음 단계, 그리고 아직 주장하지 않는 것"'),
    # checks map
    ('"Challenger: deterministic battery first, then 12 fixed questions with tools, then case-specific ones"', '"챌린저: 결정론적 검사 먼저, 이어서 도구를 쓰는 12개 고정 질문, 마지막으로 케이스별 질문"'),
    ('("Revenue quality", [("1", "Revenue double-counted", False), ("2", "Seasonal vs one-off inflows", False), ("10", "Month-end revenue clustering", False)])', '("매출 품질", [("1", "매출 이중 계산", False), ("2", "계절성 vs 일회성 유입", False), ("10", "월말 매출 집중", False)])'),
    ('("Round trips", [("3", "Self-transfers, own accounts", False)])', '("자금 순환", [("3", "본인 계좌 간 이체", False)])'),
    ('("Document integrity", [("4", "Receipt images reused/edited", True), ("8", "Premises photo vs sales", False), ("11", "Names, addresses consistent", False), ("12", "Language, currency vs location", False)])', '("문서 무결성", [("4", "영수증 사진 재사용·편집", True), ("8", "매장 사진 vs 매출", False), ("11", "이름·주소 일관성", False), ("12", "언어·통화 vs 소재지", False)])'),
    ('("Periods and balances", [("5", "Dashboard vs statement period", True), ("6", "Balance continuity, every row", True)])', '("기간과 잔액", [("5", "대시보드 vs 거래내역 기간", True), ("6", "모든 행의 잔액 연속성", True)])'),
    ('("Hidden debt", [("7", "Recurring loan-like debits", False)])', '("숨은 부채", [("7", "반복되는 상환성 출금", False)])'),
    ('("Sourcing", [("9", "Every figure has a source", True)])', '("출처", [("9", "모든 숫자에 출처", True)])'),
    ('"deterministic tool" if tool else "agent reasoning + evidence"', '"결정론적 도구" if tool else "에이전트 추론 + 근거"'),
    ('"Amber = enforced by a deterministic tool, so a finding is guaranteed to surface. Grey = reasoned by the Challenger with evidence references."', '"주황 = 결정론적 도구가 강제하므로 발견되면 반드시 표시됨.  회색 = 챌린저가 근거를 들어 추론."'),
    ('"Twelve fixed checks in six families; four of them are enforced by deterministic tools"', '"6개 영역의 12개 고정 검사. 그중 4개는 결정론적 도구가 강제합니다"'),
]

src = open(os.path.join(HERE, "diagrams2.py"), encoding="utf-8").read()
missing = [en for en, _ in KO if en not in src]
if missing:
    raise SystemExit("labels not found in diagrams2.py:\n" + "\n".join(missing))
for en, ko in KO:
    src = src.replace(en, ko)
src = src.replace('style="italic"', 'style="normal"')
src = src.replace('if __name__ == "__main__":', 'if False:')

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["Noto Sans CJK KR", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

mod = types.ModuleType("diagrams_ko")
mod.__file__ = os.path.join(HERE, "diagrams_ko_generated.py")
exec(compile(src, mod.__file__, "exec"), mod.__dict__)
import matplotlib.pyplot as _plt
_plt.rcParams["font.family"] = ["Noto Sans CJK KR", "DejaVu Sans"]
mod.OUT = os.path.join(HERE, "img_ko")
os.makedirs(mod.OUT, exist_ok=True)
for fn in (mod.process_flow2, mod.architecture2, mod.roadmap, mod.checks_map):
    fn()

from PIL import Image
for name in os.listdir(mod.OUT):
    p = os.path.join(mod.OUT, name)
    im = Image.open(p)
    if im.mode == "RGBA":
        bg = Image.new("RGB", im.size, (255, 255, 255)); bg.paste(im, mask=im.split()[3]); bg.save(p)
print("ok", sorted(os.listdir(mod.OUT)))
