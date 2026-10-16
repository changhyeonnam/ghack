"""Korean edition of the LedgerLens deck (internal sharing, not for submission).
Takes build_deck.py, swaps every English string for Korean (each swap must match exactly once or more),
points diagrams at img_ko/, and sets an East Asian font on every run, table cell and chart label."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
KFONT = "Noto Sans CJK KR"

T = [
    ('"Team name: ": "Team name: Hey Merlion!", "Team leader name: ": "Team leader name: Changhyeon Nam (team: Changhyeon Nam, Hyunho Yang)",',
     '"Team name: ": "팀명: Hey Merlion!", "Team leader name: ": "팀장: 남창현 (팀원: 남창현, 양현호)",'),
    ('"Problem Statement:": "Problem Statement: BFSI: Intelligent Risk, Fraud & Financial Experiences"}',
     '"Problem Statement:": "문제 영역: BFSI (지능형 리스크, 사기 탐지, 금융 경험)", "Team Details": "팀 정보"}'),
    ('set_title(s, "Why this matters")',
     'set_title(s, "왜 중요한가")'),
    ('eyebrow(s, "The problem", y=1.18)',
     'eyebrow(s, "문제", y=1.18)'),
    ('"Banks are ready to lend on cash flow, but reading the records by hand costs too much, and the numbers a plain AI writes cannot be traced back to a page."',
     '"은행은 현금흐름으로 대출할 준비가 됐습니다. 그런데 사람이 읽으면 너무 비싸고, AI가 쓴 숫자는 원본을 찾을 수 없습니다."'),
    ('"MEET LINH"',
     '"린의 사례"'),
    ('"Shopee seller, Vietnam"',
     '"베트남의 Shopee 셀러"'),
    ('"Asks for VND 150M of working capital. Her sales are real."',
     '"운전자금 VND 1억 5천만을 신청했습니다. 매출은 실제로 나고 있습니다."'),
    ('"She brings 14 documents: a bank statement PDF, monthly Shopee dashboard screenshots, supplier receipts, photos of the shop."',
     '"가져온 서류는 14개입니다. 은행 거래내역 PDF, 월별 Shopee 대시보드 캡처, 매입 영수증, 매장 사진."'),
    ('"No credit file. No collateral."',
     '"신용기록도, 담보도 없습니다."'),
    ('"Today her file is declined, or priced blind."',
     '"지금은 거절되거나, 근거 없이 고금리를 받습니다."'),
    ('"Synthetic demo case B"',
     '"합성 데모 케이스 B"'),
    ('"of Vietnam\'s SMEs have a bank loan; large firms: 47.1%. Without a credit file or collateral, small firms are declined."',
     '"베트남 SME 중 은행 대출을 받은 비율. 대기업은 47.1%. 신용기록과 담보가 없으면 거절됩니다."'),
    ('"of Vietnamese firms cannot borrow without collateral, so banks are moving to cash-flow lending (VPBank, Vietcombank, Agribank)."',
     '"베트남 기업 중 담보 없이는 대출이 불가능한 비율. 그래서 은행들이 현금흐름 대출로 옮겨가고 있습니다(VPBank, Vietcombank, Agribank)."'),
    ('("~45 min", "to read and verify one file by hand. For a small loan, the reading costs more than the loan earns.", False)',
     '("~45분", "서류 한 건을 사람이 읽고 검증하는 시간. 소액 대출이면 심사 비용이 대출 수익보다 큽니다.", False)'),
    ('("77%", "of the numbers in a memo written by a single Gemini prompt point to no page, so the underwriter has to find each one again. That prompt also caught only 15% of the planted risks.", True)',
     '("77%", "단일 Gemini 프롬프트가 쓴 메모 속 숫자 중 원본 페이지가 없는 비율. 심사역이 하나씩 다시 찾아야 합니다. 심어 둔 위험도 15%만 잡았습니다.", True)'),
    ('"Sources: 1 FiinGroup via Viet Nam News (Aug 2026) · 2 VCCI 2025 via VTV (May 2026) · 3 team estimate; ADB Asia SME Monitor 2025 · 4 our live benchmark, gemini-3.8-flash"',
     '"출처: 1 FiinGroup, Viet Nam News (2026년 8월) · 2 VCCI 2025, VTV (2026년 5월) · 3 팀 추정, ADB Asia SME Monitor 2025 · 4 자체 벤치마크, gemini-3.8-flash 실측"'),
    ('set_title(s, "Brief about the idea")',
     'set_title(s, "아이디어 개요")'),
    ('eyebrow(s, "The solution", y=1.18)',
     'eyebrow(s, "해결책", y=1.18)'),
    ('"LedgerLens reads the shoebox, shows its work, and argues against itself before a human signs."',
     '"LedgerLens는 서류 더미를 읽고, 근거를 보여주고, 사람이 서명하기 전에 스스로를 반박합니다."'),
    ('("1", "Read with evidence", "Answers: reading cost",',
     '("1", "근거와 함께 읽기", "해결: 읽는 비용",'),
    ('"Gemini reads every page. Each value carries document, page and bounding box. Python computes the cash flow. A memo with an unsourced number is rejected and regenerated."',
     '"Gemini가 모든 페이지를 읽고, 값마다 문서·페이지·좌표를 붙입니다. 현금흐름은 Python이 계산합니다. 출처 없는 숫자가 있는 메모는 거부되고 다시 작성됩니다."'),
    ('"14 documents, every figure sourced to a page and box, in about 2 minutes."',
     '"서류 14개, 모든 숫자에 페이지와 좌표, 약 2분."'),
    ('("2", "Challenge", "Answers: AI trust",',
     '("2", "반박", "해결: AI 신뢰",'),
    ('"A separate agent that never sees the writer\'s prompt runs deterministic checks and 12 underwriting questions, then ranks objections with evidence."',
     '"작성자의 프롬프트를 보지 않는 별도 에이전트가 결정론적 검사와 12개 심사 질문을 돌리고, 근거와 함께 이의를 심각도순으로 올립니다."'),
    ('"Flags a reused receipt photo and VND 82.5M of own-account transfers counted as income."',
     '"재사용된 영수증 사진, 매출로 잡힌 본인 계좌 이체 VND 8,250만을 잡아냅니다."'),
    ('("3", "Human signs", "Keeps: accountability",',
     '("3", "사람이 서명", "유지: 책임",'),
    ('"The underwriter accepts or dismisses each objection and signs. Every agent call is logged; decisions re-weight the next run."',
     '"심사역이 이의를 하나씩 수용하거나 기각하고 서명합니다. 모든 에이전트 호출이 기록되고, 결정은 다음 심사의 검사 가중치에 반영됩니다."'),
    ('"Linh gets the decision and the conditions to meet, in Vietnamese."',
     '"린은 결정과 충족할 조건을 베트남어로 받습니다."'),
    ('("In Linh\'s file: ", {"bold": True, "color": INK})',
     '("린의 서류에서: ", {"bold": True, "color": INK})'),
    ('("Grounded only in the applicant\'s documents. ", {"bold": True, "color": INK}), ("Guardrails: output schema, deterministic checks, a second agent, a human signature.", {})',
     '("신청자의 서류에만 근거합니다. ", {"bold": True, "color": INK}), ("가드레일: 출력 스키마, 결정론적 검사, 두 번째 에이전트, 사람의 서명.", {})'),
    ('sh = set_title(s, "Opportunities")',
     'sh = set_title(s, "기회와 기대효과")'),
    ('eyebrow(s, "Expected impact", y=1.18)',
     'eyebrow(s, "기대효과", y=1.18)'),
    ('headline(s, "What changes, and for whom.", y=1.4, size=19, h=0.45)',
     'headline(s, "누구에게, 무엇이 달라지는가.", y=1.4, size=19, h=0.45)'),
    ('("For the lender", "45 → 2", "minutes per file", "USD ~11 → 0.28 per case. Small-ticket loans become worth underwriting.", False)',
     '("대출기관", "45 → 2", "서류 한 건당 분", "건당 USD ~11 → 0.28. 소액 대출도 심사할 가치가 생깁니다.", False)'),
    ('("For the small business", "Cash flow", "not collateral, decides the loan", "Assessed on the records she already has. A no comes with reasons, in her own language.", False)',
     '("소상공인", "현금흐름", "담보가 아니라 현금흐름으로 심사", "이미 가진 서류로 심사받습니다. 거절되더라도 사유를 자기 언어로 받습니다.", False)'),
    ('("For risk and audit", "77% → 0%", "of memo numbers with no page", "Every figure points to a page and box, so nothing is re-checked by hand. Planted risks caught: 90% vs 15%.", True)',
     '("리스크·감사", "77% → 0%", "원본 페이지가 없는 숫자의 비율", "모든 숫자가 페이지와 좌표를 가리켜 다시 찾을 필요가 없습니다. 심어 둔 위험 탐지율 90% vs 15%.", True)'),
    ('("USP   ", {"bold": True, "color": AMBER}), ("The writer and the verifier are separate agents · numbers are computed by code, never generated · every number clicks back to its source line · decisions re-weight the checks", {"color": WHITE})',
     '("차별점   ", {"bold": True, "color": AMBER}), ("작성과 검증은 서로 다른 에이전트 · 숫자는 생성하지 않고 코드로 계산 · 모든 숫자는 클릭하면 원본 줄로 · 결정이 검사 가중치에 반영", {"color": WHITE})'),
    ('("Back to the 8.8%: ", {"bold": True, "color": INK}), ("when reading a file costs cents and minutes instead of an hour, the loans banks decline today become worth making.", {})',
     '("다시 8.8%로: ", {"bold": True, "color": INK}), ("서류 한 건을 읽는 데 한 시간이 아니라 몇 분과 몇백 원이 든다면, 지금 거절되는 대출이 할 만한 대출이 됩니다.", {})'),
    ('"Manual baseline (45 min at USD 15/h) is a team estimate. A number counts as untraceable when no document and page stand behind it; correctness was not measured. Live gemini-3.8-flash on a small synthetic sample."',
     '"수작업 기준치(45분, 시간당 USD 15)는 팀 추정치. 근거 문서와 페이지가 없는 숫자를 \'원본 없는 숫자\'로 셌으며, 맞고 틀림은 측정하지 않음. gemini-3.8-flash 실측, 소규모 합성 데이터 기준."'),
    ('set_title(s, "List of features offered by the solution")',
     'set_title(s, "제공 기능")'),
    ('"Every feature hangs on one pipeline, and the pipeline ends with a person."',
     '"모든 기능은 하나의 파이프라인 위에 있고, 그 끝에는 사람이 있습니다."'),
    ('("Intake", "Multimodal intake", "PDF, screenshots, photos. Classified and quality-flagged.", False)',
     '("접수", "멀티모달 접수", "PDF, 캡처, 사진. 문서 유형 분류와 품질 표시.", False)'),
    ('("Extract", "Evidence-linked extraction", "Doc id, page, bbox on every value. PDF text layer verifies it.", False)',
     '("추출", "근거 연결 추출", "모든 값에 문서·페이지·좌표. PDF 텍스트 레이어로 검증.", False)'),
    ('("Cash flow", "Deterministic model", "Inflow, outflow, trend, volatility, debt service. Python, not the model.", False)',
     '("현금흐름", "결정론적 모델", "유입, 유출, 추세, 변동성, 상환 여력. 모델이 아니라 Python이 계산.", False)'),
    ('("Analyze", "Clickable memo", "Cites catalog figures only. Click one, the source line opens.", False)',
     '("분석", "클릭 가능한 메모", "카탈로그 숫자만 인용. 누르면 원본 줄이 열림.", False)'),
    ('("Challenge", "Battery + 12 checks", "Image hash, balance chain, dates. Ranked objections with evidence.", True)',
     '("반박", "결정론적 검사 + 12개 질문", "이미지 해시, 잔액 연속성, 날짜. 근거 있는 이의를 순위대로.", True)'),
    ('("Decide", "Underwriter workbench", "Accept or dismiss, sign. Audit log. Decisions re-weight the checks.", False)',
     '("결정", "심사역 워크벤치", "수용·기각, 서명. 감사 로그. 결정이 검사 가중치에 반영.", False)'),
    ('("Explain", "Letter and paper memo", "Customer letter in the local language. Memo prints with footnoted sources.", False)',
     '("설명", "안내문과 인쇄 메모", "현지 언어로 고객 안내문. 메모는 출처 각주와 함께 인쇄.", False)'),
    ('("Out of scope by design: ", {"bold": True, "color": INK}), ("credit scoring, loan pricing, core-banking integration. LedgerLens informs the decision; it does not make it.", {})',
     '("의도적으로 제외한 범위: ", {"bold": True, "color": INK}), ("신용점수 산출, 금리 결정, 코어뱅킹 연동. LedgerLens는 판단을 돕지만 결정하지 않습니다.", {})'),
    ('set_title(s, "Wireframes / Mock diagrams of the proposed solution")',
     'set_title(s, "핵심 화면")'),
    ('eyebrow(s, "The product in one interaction", y=1.18)',
     'eyebrow(s, "제품을 한 번의 클릭으로", y=1.18)'),
    ('"Click the number. See the line."',
     '"숫자를 누르면, 원본 줄이 보입니다."'),
    ('("The memo cites a figure", "Every underlined value is a catalog figure with a source. Here: VND 82,500,000, credits from the applicant\'s own accounts.")',
     '("메모가 숫자를 인용", "밑줄 친 값은 모두 출처가 있는 카탈로그 숫자입니다. 여기서는 VND 82,500,000, 신청자 본인 계좌에서 들어온 입금.")'),
    ('("One click opens the evidence", "The computation (sum of 3 credits whose sender matches the account holder) and all 3 source references: pages 2, 4 and 5.")',
     '("클릭하면 근거가 열림", "계산식(송금인이 예금주와 같은 입금 3건의 합)과 출처 3곳: 2, 4, 5페이지.")'),
    ('("The source line lights up", "The statement page opens with the extractor\'s bounding box drawn on the exact row. A memo with an unsourced number is rejected and regenerated.")',
     '("원본 줄이 강조됨", "거래내역 페이지가 열리고, 추출기가 찾은 좌표가 정확한 행에 표시됩니다. 출처 없는 숫자가 있는 메모는 거부되고 다시 작성됩니다.")'),
    ('set_title(s, "Technologies to be used in the solution")',
     'set_title(s, "사용 기술")'),
    ('"Gemini reads, ADK orchestrates, Python computes, Cloud Run serves."',
     '"Gemini가 읽고, ADK가 조율하고, Python이 계산하고, Cloud Run이 서비스합니다."'),
    ('"Default for every agent. Measured USD 0.26-0.31 per cold case; USD 0 cached."',
     '"모든 에이전트의 기본 모델. 최초 실행 건당 USD 0.26~0.31 실측, 캐시 재실행은 USD 0."'),
    ('"One env var moves Extractor, Analyst and Challenger to Pro."',
     '"환경변수 하나로 추출·분석·챌린저를 Pro로 전환."'),
    ('"Agent Platform: Intake, 5 Extractors, Analyst, Challenger (investigator, writer), Explainer."',
     '"Agent Platform: 접수, 추출기 5개, 분석, 챌린저(조사·작성), 설명."'),
    ('"FastAPI backend scales to zero; React workbench on Firebase Hosting."',
     '"FastAPI 백엔드는 0까지 자동 축소. React 워크벤치는 Firebase Hosting."'),
    ('"Cases, extractions, memos, objections, decisions, audit, traces; documents."',
     '"케이스, 추출 결과, 메모, 이의, 결정, 감사, 트레이스. 원본 문서."'),
    ('("Python", "Deterministic tools", "Cash-flow model, balance chain, image hash, PDF text-layer cross-check, date and entity checks.", False)',
     '("Python", "결정론적 도구", "현금흐름 모델, 잔액 연속성, 이미지 해시, PDF 텍스트 레이어 교차검증, 날짜·주체 검사.", False)'),
    ('("Python", "LLM cache, budget cap", "Content-hash cache per model and prompt version; hard USD cap per process.", False)',
     '("Python", "LLM 캐시, 예산 상한", "모델·프롬프트 버전별 콘텐츠 해시 캐시. 프로세스당 USD 상한.", False)'),
    ('("Integration", "REST API", "Any loan origination system can create cases, run stages and read memos.", True)',
     '("연동", "REST API", "어떤 여신 시스템(LOS)이든 케이스 생성, 단계 실행, 메모 조회 가능.", True)'),
    ('"Grounding: only the applicant\'s documents; every value must carry source {doc_id, page, bbox}. No separate OCR: Gemini reads rendered pages."',
     '"그라운딩: 신청자의 서류만 사용. 모든 값은 출처 {doc_id, page, bbox}를 가져야 함. 별도 OCR 없이 Gemini가 렌더링된 페이지를 직접 읽음."'),
    ('set_title(s, "Prototype performance report / Benchmarking")',
     'set_title(s, "성능 및 벤치마크")'),
    ('"LedgerLens caught 90% of the planted risks on live Gemini output; a single prompt on the same documents caught 15%."',
     '"실제 Gemini 실행에서 심어 둔 위험의 90%를 잡았습니다. 같은 서류에 단일 프롬프트는 15%."'),
    ('[{"t": "LEDGERLENS", "size": 9',
     '[{"t": "LedgerLens", "size": 9'),
    ('{"t": "of planted risks caught", "size": 11, "color": TXT}, {"t": "small synthetic sample, read as indicative", "size": 8.5, "color": GREY}',
     '{"t": "심어 둔 위험 탐지", "size": 11, "color": TXT}, {"t": "소규모 합성 데이터, 참고 지표", "size": 8.5, "color": GREY}'),
    ('[{"t": "SINGLE PROMPT", "size": 9',
     '[{"t": "단일 프롬프트", "size": 9'),
    ('{"t": "same documents", "size": 11, "color": GREY}, {"t": "and same model", "size": 8.5, "color": GREY}',
     '{"t": "같은 서류", "size": 11, "color": GREY}, {"t": "같은 모델", "size": 8.5, "color": GREY}'),
    ('"of memo numbers trace to a page (single prompt: 23%)"',
     '"메모 속 숫자 중 원본 페이지가 있는 비율 (단일 프롬프트: 23%)"'),
    ('[{"t": "~2 min", "size": 30',
     '[{"t": "~2분", "size": 30'),
    ('"per case cold, USD 0.26-0.31; cached re-run USD 0"',
     '"최초 실행 건당, USD 0.26~0.31. 캐시 재실행 USD 0"'),
    ('rows = [["Metric", "Target", "Result"],\n        ["Risks caught (strict)", "≥ 80%", "90% (single prompt: 15%)"],\n        ["Traceable numbers", "100%", "100% (single prompt: 23%)"],\n        ["Objections on clean case A", "≤ 20%", "none"],\n        ["Extraction row accuracy*", "≥ 97%", "100%"],\n        ["Evidence-link accuracy*", "≥ 95%", "100%"],\n        ["Time per case (cold)", "≤ 180 s", "~2 min"],\n        ["Cost per case (cold)", "≤ USD 0.50", "USD 0.26-0.31"]]',
     'rows = [["지표", "목표", "결과"],\n        ["위험 탐지율 (엄격)", "≥ 80%", "90% (단일 프롬프트: 15%)"],\n        ["원본 있는 숫자", "100%", "100% (단일 프롬프트: 23%)"],\n        ["정상 케이스 A의 이의", "≤ 20%", "없음"],\n        ["추출 행 정확도*", "≥ 97%", "100%"],\n        ["근거 연결 정확도*", "≥ 95%", "100%"],\n        ["건당 시간 (최초)", "≤ 180초", "~2분"],\n        ["건당 비용 (최초)", "≤ USD 0.50", "USD 0.26~0.31"]]'),
    ('("How measured. ", {"bold": True}), ("Live gemini-3.8-flash runs, 2026-10-15/16, on three synthetic businesses with team-planted risks. Strict scoring: an objection counts only if it carries the risk\'s identifying amount or document, one objection per risk. ", {}), ("Traceable = a memo number with a document and page behind it; correctness not measured. The sample is small, so read every percentage as indicative. Missed: dashboard gross vs payout, COD vs cash deposits. Recommendation matched on C; A gave approve_with_conditions (expected approve), B request_more_documents (expected approve_with_conditions). *Clean born-digital synthetic PDFs; real scans will be lower.", {})',
     '("측정 방법. ", {"bold": True}), ("gemini-3.8-flash 실측, 2026-10-15/16. 팀이 위험을 심어 둔 합성 사업자 세 곳. 엄격 채점: 이의에 위험을 특정하는 금액이나 문서가 있어야 인정, 위험당 이의 1개. ", {}), ("원본 있는 숫자 = 근거 문서와 페이지가 있는 숫자이며, 맞고 틀림은 측정하지 않음. 표본이 작으므로 모든 비율은 참고 지표. 놓친 것: 대시보드 총매출 vs 정산액, COD vs 현금 입금. 권고안은 C에서 일치, A는 조건부 승인(기대: 승인), B는 추가 서류 요청(기대: 조건부 승인). *깨끗한 디지털 합성 PDF 기준이며, 실제 스캔본은 더 낮을 것.", {})'),
    ('set_title(s, "Process flow diagram")',
     'set_title(s, "프로세스 흐름")'),
    ('"Three lanes: the loan officer uploads, the agents read and challenge, the underwriter decides. Decisions flow back into the Challenger\'s priorities."',
     '"세 개의 레인: 대출 담당자가 올리고, 에이전트가 읽고 반박하고, 심사역이 결정합니다. 결정은 다시 챌린저의 우선순위로 돌아갑니다."'),
    ('set_title(s, "Architecture diagram of the proposed solution")',
     'set_title(s, "아키텍처")'),
    ('set_title(s, "Estimated implementation cost")',
     'set_title(s, "구현 비용")'),
    ('"Measured: USD 0.26-0.31 per case on a cold Flash run, USD 0 on a cached re-run"',
     '"실측: Flash 최초 실행 건당 USD 0.26~0.31, 캐시 재실행 USD 0"'),
    ('cd.categories = ["LedgerLens cold run, case B (14 docs)", "LedgerLens cold run, case C (11 docs)", "Single-prompt baseline (no checks)", "LedgerLens cached re-run"]',
     'cd.categories = ["LedgerLens 최초 실행, 케이스 B (서류 14개)", "LedgerLens 최초 실행, 케이스 C (서류 11개)", "단일 프롬프트 기준선 (검사 없음)", "LedgerLens 캐시 재실행"]'),
    ('cd.add_series("USD per case",',
     'cd.add_series("건당 USD",'),
    ('"Cost per case, USD (gemini-3.8-flash, live run 2026-10-15)"',
     '"건당 비용, USD (gemini-3.8-flash, 2026-10-15 실측)"'),
    ('rows = [["Assumption", "Value"],\n        ["Gemini 3.8 Flash list price", "USD 0.75 / 3.75 per 1M tokens"],\n        ["Measured cold run", "~2 min and USD 0.26-0.31 per case"],\n        ["Cached re-run", "USD 0 (content-hash LLM cache)"],\n        ["Public demo", "Replays the recorded live Gemini run, USD 0; only the customer letter calls Gemini (~USD 0.0015)"],\n        ["Hosting", "Cloud Run scales to zero; Firestore and Storage in free tier"],\n        ["Guardrail", "Budget-cap env var stops Gemini calls once spent"],\n        ["Build", "2 engineers, 4 days, free tier and trial credits"]]',
     'rows = [["가정", "값"],\n        ["Gemini 3.8 Flash 정가", "100만 토큰당 USD 0.75 / 3.75"],\n        ["최초 실행 실측", "건당 약 2분, USD 0.26~0.31"],\n        ["캐시 재실행", "USD 0 (콘텐츠 해시 LLM 캐시)"],\n        ["공개 데모", "녹화된 실제 실행을 재생, USD 0. 고객 안내문만 Gemini 호출 (~USD 0.0015)"],\n        ["호스팅", "Cloud Run은 0까지 축소, Firestore·Storage는 무료 구간"],\n        ["가드레일", "예산 상한 환경변수로 초과 시 Gemini 호출 중단"],\n        ["개발", "엔지니어 2명, 4일, 무료 구간과 체험 크레딧"]]'),
    ('set_title(s, "Snapshots of the prototype")',
     'set_title(s, "프로토타입 화면")'),
    ('"1", "New case", "Applicant details, then the raw documents. Intake classifies and quality-flags them."',
     '"1", "새 케이스", "신청자 정보를 넣고 원본 서류를 올리면, 접수 에이전트가 분류하고 품질을 표시합니다."'),
    ('"2", "Click a number, see the line", "Evidence panel with computation and all sources; the statement opens with the bounding box highlighted."',
     '"2", "숫자를 누르면 원본 줄", "계산식과 모든 출처를 보여주는 근거 패널. 거래내역의 해당 위치가 강조됩니다."'),
    ('"3", "Challenger objections", "Critical: two receipt photos are the same image with an edited date. Evidence chips open the photo."',
     '"3", "챌린저의 이의", "심각: 두 영수증 사진이 날짜만 바꾼 같은 이미지. 근거 칩을 누르면 사진이 열립니다."'),
    ('"4", "The underwriter signs", "Outcome, conditions and rationale, written to the audit log; accept/dismiss rates re-weight the checks."',
     '"4", "심사역 서명", "결과, 조건, 사유가 감사 로그에 기록되고, 수용·기각 비율이 검사 가중치에 반영됩니다."'),
    ('set_title(s, "Additional details / Future development")',
     'set_title(s, "향후 계획")'),
    ('"Humans decide, every figure and decision is traceable, the prototype uses watermarked synthetic data only, and production keeps documents and model endpoints in-region."',
     '"결정은 사람이 하고, 모든 숫자와 결정은 추적 가능합니다. 프로토타입은 워터마크가 찍힌 합성 데이터만 쓰며, 운영 시 문서와 모델 엔드포인트는 역내에 둡니다."'),
    ('sh = set_title(s, "Provide links to your:")',
     'sh = set_title(s, "링크")'),
    ('("GitHub public repository", "github.com/changhyeonnam/ghack", "English README, architecture, run instructions, synthetic-data notice, presentation/")',
     '("GitHub 저장소", "github.com/changhyeonnam/ghack", "README, 아키텍처, 실행 방법, 합성 데이터 안내, presentation/ 폴더")'),
    ('("Demo video (3 to 4 minutes)", VIDEO_URL, "Problem in 20 seconds, click-to-source and Challenger scenes, benchmark near the end")',
     '("데모 영상 (3~4분)", "준비 중", "20초 안에 문제 제시, 숫자 클릭과 챌린저 장면, 마지막에 벤치마크")'),
    ('("Final product", APP_URL, "Cloud Run service; each browser gets its own copy of the three demo cases (Reset demo). Scales to zero; demo cases replay the recorded live Gemini run (only the customer letter calls Gemini live), so judging costs nothing")',
     '("배포 버전", "준비 중", "Cloud Run 서비스. 브라우저마다 데모 케이스 3개의 사본을 받습니다(데모 초기화 가능). 0까지 축소되고, 데모는 녹화된 실제 실행을 재생해 비용이 들지 않습니다(고객 안내문만 Gemini 실시간 호출).")'),
    ('"Links are inserted at submission on 18 October 2026."',
     '"내부 공유용 한국어판입니다. 영문 제출본과 내용이 같습니다."'),
    ('"Appendix: the Challenger\'s 12 fixed checks"',
     '"부록: 챌린저의 12개 고정 검사"'),
    ('set_title(s, "Appendix: portfolio, cash flow and audit views")',
     'set_title(s, "부록: 포트폴리오, 현금흐름, 감사 화면")'),
    ('("v2_portfolio.jpg", "Portfolio", "Cases in review, open objections and unsourced numbers across the book; filters by status.")',
     '("v2_portfolio.jpg", "포트폴리오", "심사 중인 케이스, 미해결 이의, 출처 없는 숫자를 한눈에. 상태별 필터.")'),
    ('("v2_cashflow_c.jpg", "Cash flow", "Deterministic monthly model: inflow, net, trend, volatility, end-of-month share, repayment capacity.")',
     '("v2_cashflow_c.jpg", "현금흐름", "결정론적 월별 모델: 유입, 순현금, 추세, 변동성, 월말 집중도, 상환 여력.")'),
    ('("v2_audit_c.jpg", "Audit timeline", "Every stage and agent call with version, model and prompt; the trail a regulator can read.")',
     '("v2_audit_c.jpg", "감사 타임라인", "모든 단계와 에이전트 호출을 버전, 모델, 프롬프트와 함께 기록. 감독기관이 읽을 수 있는 이력.")'),
    ('"Also in the build: dark and light themes, PDF text-layer cross-check on every extracted amount, content-hash LLM cache, cache_only demo mode, budget cap, printable paper memo with footnoted sources."',
     '"그 밖의 구현: 다크·라이트 테마, 추출한 모든 금액의 PDF 텍스트 레이어 교차검증, 콘텐츠 해시 LLM 캐시, cache_only 데모 모드, 예산 상한, 출처 각주가 붙은 인쇄용 메모."'),
    ('IMG = HERE + "/img"',
     'IMG = HERE + "/img_ko"'),
    ('out = os.path.join(os.path.dirname(HERE), "LedgerLens_AI_Builder_Cup_Submission.pptx") if os.path.basename(HERE) == "build" else HERE + "/LedgerLens_AI_Builder_Cup_Submission.pptx"',
     'out = os.path.join(os.path.dirname(HERE), "LedgerLens_KR.pptx") if os.path.basename(HERE) == "build" else HERE + "/LedgerLens_KR.pptx"'),
    ('[{"t": "90%", "size": 60',
     '[{"t": "90%", "size": 60'),
    ('[{"t": "15%", "size": 60',
     '[{"t": "15%", "size": 60'),
    ('[{"t": "100%", "size": 30',
     '[{"t": "100%", "size": 30'),
]


src = open(os.path.join(HERE, "build_deck.py"), encoding="utf-8").read()
bad = [en[:90] for en, _ in T if en not in src]
if bad:
    raise SystemExit("not found in build_deck.py:\n  " + "\n  ".join(bad))
for en, ko in T:
    src = src.replace(en, ko)

# Team-details heading: the loop only matches keys with a trailing colon; add the heading.
src = src.replace('key = next((k for k in fills if p.runs and p.runs[0].text.strip() == k.strip()), None)',
                  'key = next((k for k in fills if p.runs and p.runs[0].text.strip() == k.strip()), None)\n            if key == "Team Details":\n                p.runs[0].text = fills[key]\n                for r in p.runs[1:]:\n                    r.text = ""\n                continue')
# Italic Hangul reads badly; keep everything upright.
src = src.replace('"italic": True', '"italic": False')


# ---- Korean-only layout changes ----
# Headlines with a forced line break (avoid "AI / 에게" and a lone "개." at a line end).
src = src.replace('headline(s, "은행은 현금흐름으로 대출할 준비가 됐습니다. 그런데 사람이 읽으면 너무 비싸고, AI가 쓴 숫자는 원본을 찾을 수 없습니다.", y=1.4, size=16.5, h=0.72)',
                  'tb(s, 0.3, 1.4, 9.4, 0.72, [{"t": "은행은 현금흐름으로 대출할 준비가 됐습니다.", "size": 17, "bold": True, "color": INK}, {"t": "그런데 사람이 읽으면 너무 비싸고, AI가 쓴 숫자는 원본을 찾을 수 없습니다.", "size": 17, "bold": True, "color": INK}])')
src = src.replace('headline(s, "실제 Gemini 실행에서 심어 둔 위험의 90%를 잡았습니다. 같은 서류에 단일 프롬프트는 15%.", y=1.22, size=17, h=0.7)',
                  'tb(s, 0.3, 1.2, 9.4, 0.72, [{"t": "실제 Gemini 실행에서 심어 둔 위험의 90%를 잡았습니다.", "size": 16, "bold": True, "color": INK}, {"t": "같은 서류를 단일 프롬프트로 읽으면 15%입니다.", "size": 16, "bold": True, "color": INK}])')
src = src.replace('"수용·기각, 서명. 감사 로그. 결정이 검사 가중치에 반영."', '"수용·기각, 서명. 감사 로그. 결정이 가중치에 반영."')
src = src.replace('    tb(s, x + 0.1, 3.25, cw - 0.2, 1.75, [{"t": d, "size": 9.5, "color": TXT}], margin=0.0)',
                  '    tb(s, x + 0.1, 3.05, cw - 0.2, 1.95, [{"t": d, "size": 10, "color": TXT}], margin=0.0)')
# Cost chart drawn with shapes and text boxes, so Korean labels render cleanly everywhere.
_a = src.index("from pptx.chart.data import CategoryChartData\nfrom pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION\ncd = CategoryChartData()")
_b = src.index("va.minimum_scale = 0.0", _a) + len("va.minimum_scale = 0.0")
src = src[:_a] + """tb(s, 0.3, 1.8, 5.7, 0.3, [{"t": "건당 비용, USD (gemini-3.8-flash, 2026-10-15 실측)", "size": 10.5, "bold": True, "color": INK}], margin=0.0)
_bars = [("LedgerLens 최초 실행", "케이스 B, 서류 14개", 0.306, AMBER),
         ("LedgerLens 최초 실행", "케이스 C, 서류 11개", 0.257, AMBER),
         ("단일 프롬프트 기준선", "검사 없음", 0.015, RGBColor(0xB0, 0xB8, 0xBE)),
         ("LedgerLens 캐시 재실행", "콘텐츠 해시 캐시", 0.0, TEAL)]
_y = 2.3; _x0 = 2.35; _wmax = 2.95
card(s, _x0 - 0.02, 2.2, 0.015, 3.0, fill=LINE, line=None, radius=0.0)
for _t, _sub, _v, _c in _bars:
    tb(s, 0.3, _y, 1.95, 0.32, [{"t": _t, "size": 9.5, "bold": True, "color": INK, "align": PP_ALIGN.RIGHT}], margin=0.0)
    tb(s, 0.3, _y + 0.3, 1.95, 0.28, [{"t": _sub, "size": 8.5, "color": GREY, "align": PP_ALIGN.RIGHT}], margin=0.0)
    _w = max(_wmax * _v / 0.306, 0.02)
    card(s, _x0, _y + 0.05, _w, 0.5, fill=_c, line=None, radius=0.0, shape=MSO_SHAPE.RECTANGLE)
    tb(s, _x0 + _w + 0.08, _y + 0.1, 0.8, 0.4, [{"t": f"{_v:.3f}", "size": 11, "bold": True, "color": INK}], anchor=MSO_ANCHOR.MIDDLE, margin=0.0)
    _y += 0.74""" + src[_b:]


# Tables drawn with shapes and text boxes (LibreOffice ignores the spacing fix inside native tables).
src = src.replace("slides = list(prs.slides)\nS = {", """def table(slide, x, y, w, h, rows, col_w, font=9.5, header_fill=INK, zebra=True, bold_first_col=False):
    rh = h / len(rows)
    for ri, row in enumerate(rows):
        cx = x
        for ci, val in enumerate(row):
            fill = header_fill if ri == 0 else (PANEL if (zebra and ri % 2 == 0) else WHITE)
            card(slide, cx, y + ri * rh, col_w[ci], rh, fill=fill, line=LINE, lw=0.75, shape=MSO_SHAPE.RECTANGLE)
            tb(slide, cx + 0.04, y + ri * rh, col_w[ci] - 0.08, rh,
               [{"t": str(val), "size": font, "bold": (ri == 0) or (bold_first_col and ci == 0), "color": WHITE if ri == 0 else TXT}],
               anchor=MSO_ANCHOR.MIDDLE, margin=0.03)
            cx += col_w[ci]


slides = list(prs.slides)
S = {""", 1)

# East Asian font on every run, table cell and chart label, right before saving.
EA_FIX = '''
from pptx.oxml.ns import qn as _q
_KF = "''' + KFONT + '''"
_AFTER = ("a:cs", "a:sym", "a:hlinkClick", "a:hlinkMouseOver", "a:rtl", "a:extLst")
def _ea(root):
    for tag in ("a:rPr", "a:defRPr", "a:endParaRPr"):
        for rpr in root.iter(_q(tag)):
            ea = rpr.find(_q("a:ea"))
            if ea is None:
                ea = rpr.makeelement(_q("a:ea"), {})
                lat = rpr.find(_q("a:latin"))
                if lat is not None:
                    lat.addnext(ea)
                else:
                    nxt = next((rpr.find(_q(t)) for t in _AFTER if rpr.find(_q(t)) is not None), None)
                    if nxt is not None:
                        nxt.addprevious(ea)
                    else:
                        rpr.append(ea)
            ea.set("typeface", _KF)
for _sl in prs.slides:
    _ea(_sl._element)
    for _sh in _sl.shapes:
        if getattr(_sh, "has_chart", False) and _sh.has_chart:
            _ea(_sh.chart._chartSpace)
'''
src = src.replace("\nprs.save(out)", EA_FIX + "\nprs.save(out)")

exec(compile(src, os.path.join(HERE, "build_deck_ko_generated.py"), "exec"), {"__file__": os.path.join(HERE, "build_deck.py"), "__name__": "__main__"})
