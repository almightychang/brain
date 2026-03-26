---
description: "논문 관리 — add: arxiv 논문을 vault에 아카이빙 + 구조화된 요약 생성, study: 논문 심층 분석 + 학습 자료 생성 (Q&A, 코드 데모 등)"
allowed-tools: Bash, Write, Edit, Read, Glob, Grep, Agent, WebFetch
argument-hint: "add <arxiv-url> | study <paper-path-or-url>"
---

# brain:paper — 논문 아카이빙 & 심층 학습

## 전제 조건

이 스킬 실행 전 `${CLAUDE_PLUGIN_ROOT}/config.md`를 읽어 VAULT, WORKSPACES 경로를 확인한다.

## 서브커맨드

| 커맨드 | 설명 | 예시 |
|--------|------|------|
| `add <arxiv-url>` | arxiv 논문을 vault에 아카이빙 + 요약 | `/brain:paper add https://arxiv.org/abs/2301.07041` |
| `study <path-or-url>` | 논문 심층 분석 + 학습 자료 생성 | `/brain:paper study ~/Downloads/paper.pdf` |

첫 번째 인자(`$ARGUMENTS[0]`)로 서브커맨드를 판별한다. 인자가 없으면 사용자에게 add/study 중 선택을 요청한다.

---

## 공통: 스크립트 경로

```
SCRIPTS="${CLAUDE_SKILL_DIR}/scripts"
```

---

# add — arxiv 논문 → 옵시디언 아카이빙

arxiv 논문 링크를 받아 옵시디언 Second Brain에 체계적으로 아카이빙하고, 학습 가능한 형태로 요약한다.

## 입력

`/brain:paper add <arxiv-url>`
예: `/brain:paper add https://arxiv.org/abs/2301.07041`

---

## Step 1: arxiv 메타데이터 파싱

arxiv URL에서 ID를 추출하고 WebFetch로 메타데이터를 가져온다.

```
WebFetch: https://export.arxiv.org/api/query?id_list=${ARXIV_ID}
prompt: "Extract title, authors, abstract, published date, categories"
```

제목에서 폴더명 slug 생성:
- 소문자 변환, 공백→하이픈, 특수문자 제거
- 예: "Attention Is All You Need" → `attention-is-all-you-need`

---

## Step 2: 폴더 생성 + PDF 다운로드 + 이미지 추출

**병렬 실행**: 폴더 생성, PDF 다운로드, 이미지 추출을 순차적으로 수행.

```
VAULT="{config.md의 VAULT}"
PAPER_DIR="${VAULT}/3. Resources/papers/${ARXIV_ID}-${SLUG}"
```

폴더 구조 (foldernote 패턴 — 요약 노트가 폴더명과 동일):
```
${PAPER_DIR}/
├── ${ARXIV_ID}-${SLUG}.md   ← foldernote (= summary)
├── paper.pdf
├── full-text.md
└── figures/
    ├── page_1_img_1.png
    └── ...
```

**FOLDERNOTE_NAME**: `${ARXIV_ID}-${SLUG}.md` (폴더명과 동일한 파일명)

PDF 다운로드:
```bash
mkdir -p "${PAPER_DIR}/figures"
PDF_PATH=$(node ${SCRIPTS}/download-pdf.cjs "https://arxiv.org/abs/${ARXIV_ID}")
cp "$PDF_PATH" "${PAPER_DIR}/paper.pdf"
```

이미지 추출:
```bash
pyenv shell 3.12.12
python3 ${SCRIPTS}/extract-images.py \
  "${PAPER_DIR}/paper.pdf" \
  "${PAPER_DIR}/figures/"
```

---

## Step 3: 서브에이전트 — PDF → full-text.md

> **핵심**: PDF를 메인 컨텍스트에서 직접 읽으면 이미지가 컨텍스트에 쌓여 이후 작업이 불가능해진다.
> 반드시 서브에이전트에게 위임하여 이미지 컨텍스트를 격리한다.

서브에이전트에게 다음 프롬프트를 전달:

```
PDF 파일을 읽고 마크다운 텍스트로 변환하라.

## 입력
- PDF 경로: ${PAPER_DIR}/paper.pdf
- 출력 경로: ${PAPER_DIR}/full-text.md

## 작업
1. PDF를 20페이지씩 분할하여 Read 도구로 읽는다 (pages: "1-20", "21-40", ...)
2. 읽은 내용을 마크다운으로 변환하여 full-text.md에 쓴다

## full-text.md 형식

---
title: "{{논문 제목}}"
arxiv: "{{ARXIV_ID}}"
authors: [{{저자목록}}]
date: {{출판일}}
tags:
  - paper
  - {{분야태그}}
---

# {{논문 제목}}

> [!info] 관련 문서
> - **요약**: [[${ARXIV_ID}-${SLUG}]]
> - **원본**: [[paper.pdf]]

{{PDF에서 추출한 전체 텍스트}}
- 섹션/서브섹션 구조를 마크다운 헤딩(##, ###)으로 유지
- 수식은 LaTeX ($...$, $$...$$)로 표기
- figure 위치에 wikilink 삽입: ![[figures/page_X_img_Y.png]]
- figure 캡션 포함: *Figure N: {{캡션}}*
- References 섹션은 포함하지 않는다 (용량 절약)

## 주의
- 반드시 Write 도구로 파일을 생성하라
- 텍스트가 너무 길면 Write로 앞부분을 쓰고, Edit으로 뒷부분을 append하라
```

서브에이전트 설정:
- `mode: "bypassPermissions"` (파일 쓰기 자동 허용)
- `model: "sonnet"` (빠른 처리)

---

## Step 4: 서브에이전트 — full-text.md → summary.md

> **핵심**: full-text.md가 길 수 있으므로 청크 분할 전략을 사용한다.

서브에이전트에게 다음 프롬프트를 전달:

```
논문 전문 텍스트를 읽고 구조화된 요약을 생성하라.

## 입력
- 텍스트 경로: ${PAPER_DIR}/full-text.md
- 출력 경로: ${PAPER_DIR}/${ARXIV_ID}-${SLUG}.md  (foldernote — 폴더명과 동일)
- figures 디렉토리: ${PAPER_DIR}/figures/

## 청크 분할 전략
full-text.md가 1000줄을 초과하면:
1. 1000줄씩, 100줄 오버랩을 두고 분할하여 읽는다
   - chunk 1: line 1-1000
   - chunk 2: line 901-1900
   - chunk 3: line 1801-2800
   - ...
2. 각 청크를 읽으며 핵심 내용을 메모한다
3. 모든 청크를 읽은 후 종합하여 summary.md를 작성한다

1000줄 이하면 한 번에 읽는다.

## 작성 원칙
- **분량**: 전체 요약은 최소 300줄 이상을 목표로 한다. 논문의 핵심 논증을 충분히 재구성하라.
- **깊이**: 단순 나열이 아닌, 논문의 논리 흐름을 따라가며 "왜 이런 설계를 했는지"까지 설명하라.
- **구체성**: 핵심 개념에는 반드시 예시(논문에서 사용한 예시 또는 코드 스니펫)를 포함하라.
- **figure 활용**: 가능한 모든 figure를 참조하고, 각 figure가 무엇을 보여주는지 설명하라.

## summary.md 형식

---
title: "{{논문 제목}}"
arxiv: "{{ARXIV_ID}}"
authors: [{{저자목록}}]
date: {{출판일}}
studied: {{오늘 날짜}}
tags:
  - paper
  - {{분야태그들}}
---

# {{논문 제목}}

> [!info] 메타데이터
> - **저자**: {{저자}}
> - **arxiv**: [{{ARXIV_ID}}](https://arxiv.org/abs/{{ARXIV_ID}})
> - **분야**: {{categories}}
> - **전문**: [[full-text]]
> - **원본**: [[paper.pdf]]

## 한줄 요약

{{논문의 핵심을 한 문장으로}}

## 배경 및 문제

{{왜 이 연구가 필요한지, 어떤 문제를 풀려 하는지}}
- 기존 접근법의 한계를 구체적으로 서술 (선행 연구 인용 포함)
- 논문이 제시하는 문제의 심각성을 데이터/예시로 뒷받침
- 최소 10줄 이상

## 핵심 기여

1. {{기여 1 — 2-3문장으로 상세히}}
2. {{기여 2 — 2-3문장으로 상세히}}
3. {{기여 3 — 2-3문장으로 상세히}}

## 방법론

{{핵심 방법론을 서브섹션(###)으로 나누어 설명}}
{{각 서브섹션에서:}}
  - 개념 정의와 직관적 설명
  - 논문의 예시나 코드 스니펫 인용 (코드블록 사용)
  - 기존 접근법과의 차이점
  - figure를 wikilink로 참조: ![[figures/filename.ext]]
{{최소 50줄 이상}}

## 주요 결과

{{정량적/정성적 결과를 테이블이나 리스트로 정리}}
- 실험 설정 간략 설명
- 핵심 수치와 그 의미 해석
- 기존 방법 대비 개선점
- 케이스 스터디가 있다면 상세히 서술

## 한계 및 향후 연구

### 논문이 인정한 한계
{{테이블 또는 리스트로 정리, 각 항목에 설명 포함}}

### 향후 연구 방향
{{논문이 제시한 방향 + 자체 분석}}

## 핵심 인사이트

> [!tip] 이 논문에서 가져갈 것
> {{이 논문이 주는 핵심 교훈/통찰 — 3-5개 bullet point로 구체적으로}}

## 추가 작업
- figures/ 디렉토리의 파일 목록을 확인하고 (ls 또는 Glob), 핵심 figure는 설명적 이름으로 rename
  - 예: page_33_img_1.jpeg → face-construction-plan.jpeg
- summary.md와 full-text.md의 figure 참조를 rename된 이름으로 업데이트

## 주의
- 반드시 Write 도구로 파일을 생성하라
- 한국어로 작성하되, 기술 용어는 영어 유지
```

서브에이전트 설정:
- `mode: "bypassPermissions"` (파일 쓰기 자동 허용)
- `model: "sonnet"` (빠른 처리)

---

## Step 5: 완료 + 논문 소개 + Thread 추천 + 학습 프롬프트

모든 서브에이전트 완료 후, foldernote를 Read로 읽어서 내용을 확인한다.

### 5-1. 논문 내용 소개

foldernote(summary.md)를 기반으로 사용자에게 논문 내용을 **대화체로 자세히 소개**한다.
단순히 요약 파일의 내용을 복붙하는 것이 아니라, 읽은 내용을 바탕으로 자연스럽게 설명해준다.

**소개 형식:**

```
## 논문 소개: {{논문 제목}}

### 이 논문이 풀려는 문제
{{배경과 문제를 2-3 문단으로 풀어서 설명. "왜 이게 중요한지"를 강조}}

### 핵심 아이디어
{{방법론의 핵심을 직관적으로 설명. 비유나 예시 활용.
figure가 있으면 핵심 figure 1-2개를 인라인 이미지로 첨부하여 시각적으로 보여준다.}}

### 주요 결과
{{어떤 성과를 냈는지, 기존 대비 어떤 점이 나은지}}

### 왜 읽을 만한가
{{이 논문의 독특한 관점이나 실용적 가치를 1-2문장으로}}
```

**작성 원칙:**
- 한국어로 작성, 기술 용어는 영어 유지
- summary.md의 구조를 그대로 따르지 말고, 읽는 사람이 논문을 안 읽어도 핵심을 파악할 수 있도록 **이야기하듯** 설명
- 분량: 최소 30줄 이상. 방법론이 복잡한 논문은 더 길어도 됨
- figure를 적극 활용: `![설명](${PAPER_DIR}/figures/filename.ext)` 형식으로 터미널에서 볼 수 있도록 절대경로 사용
- 수식이 핵심이면 LaTeX 포함하되, 직관적 설명을 반드시 곁들임

### 5-2. Thread 연결 추천

방금 추가한 논문이 기존 research thread와 연결될 수 있는지 확인:

1. `${VAULT}/6. Thread/` 에서 `.md` 파일을 Glob으로 스캔 (패턴: `*.md`, path: `${VAULT}/6. Thread`)
2. 각 thread의 제목과 문제 정의를 빠르게 읽는다 (상단 30줄이면 충분)
3. 방금 추가한 논문의 주제와 비교하여 연결 가능성 판단

**연결이 있으면:**
```
Thread 연결 가능:
  - "{{thread 제목}}" — {{왜 연결되는지 한줄}}
  → /brain:thread 로 추가할 수 있습니다.
```

**연결이 없으면:** 이 섹션을 출력하지 않는다. 억지로 만들지 않는다.

### 5-3. 완료 출력

```
논문 아카이빙 완료: ${PAPER_DIR}

생성된 파일:
  - ${ARXIV_ID}-${SLUG}.md (foldernote — 구조화된 요약)
  - paper.pdf (원본)
  - full-text.md (전문 텍스트)
  - figures/ (추출된 이미지 N개)

학습하려면:
  /brain:paper study ${PAPER_DIR}
  /brain:grok ${PAPER_DIR}/${ARXIV_ID}-${SLUG}.md
```

**추천 프롬프트 생성 규칙**:
- summary.md의 핵심 기여/방법론을 기반으로 구체적인 학습 질문 제안
- 2-3개의 다른 각도의 프롬프트 제안

---
---

# study — 논문 심층 분석 & 학습

논문 PDF를 깊이 읽고, 체계적인 학습 자료를 생성하여 옵시디언 Second Brain에 저장한다.

## 입력

`/brain:paper study <paper-path-or-url>`

지원 형식:
- **로컬 경로**: `/brain:paper study ~/Downloads/paper.pdf`
- **PDF URL**: `/brain:paper study https://arxiv.org/pdf/1706.03762.pdf`
- **arxiv URL**: `/brain:paper study https://arxiv.org/abs/1706.03762`
- **기존 paper add 디렉토리**: `/brain:paper study ${VAULT}/3. Resources/papers/2301.07041-some-paper/`

---

## Step 0: 입력 분석 & PDF 확보

```
VAULT="{config.md의 VAULT}"
```

### 경우 1: 기존 paper add 디렉토리가 주어진 경우
- `paper.pdf`와 `full-text.md`가 이미 있으면 그대로 사용
- PAPER_DIR = 주어진 디렉토리

### 경우 2: URL이 주어진 경우
```bash
PDF_PATH=$(node ${SCRIPTS}/download-pdf.cjs "<user-input>")
```
- arxiv URL이면 ID 추출 → slug 생성 → PAPER_DIR 설정
- 일반 URL이면 파일명에서 slug 생성

### 경우 3: 로컬 PDF 경로
- 파일명에서 slug 생성

**PAPER_DIR 결정**:
- arxiv 논문: `${VAULT}/3. Resources/papers/${ARXIV_ID}-${SLUG}/`
- 기타: `${VAULT}/3. Resources/papers/${SLUG}/`

```bash
mkdir -p "${PAPER_DIR}/study"
cp "$PDF_PATH" "${PAPER_DIR}/paper.pdf" 2>/dev/null || true
```

---

## Step 1: 서브에이전트 — PDF 파싱 & 이미지 추출

> **핵심**: PDF를 메인 컨텍스트에서 직접 읽으면 이미지가 컨텍스트에 쌓여 이후 작업이 불가능해진다.
> 반드시 서브에이전트에게 위임하여 이미지 컨텍스트를 격리한다.

서브에이전트에게 다음 프롬프트를 전달:

```
논문 PDF를 읽고 마크다운 텍스트로 변환하라.

## 입력
- PDF 경로: ${PAPER_DIR}/paper.pdf
- 출력 경로: ${PAPER_DIR}/study/full-text.md

## 작업
1. PDF를 20페이지씩 분할하여 Read 도구로 읽는다 (pages: "1-20", "21-40", ...)
2. 읽은 내용을 마크다운으로 변환하여 full-text.md에 쓴다

## full-text.md 형식
- 섹션/서브섹션 구조를 마크다운 헤딩(##, ###)으로 유지
- 수식은 LaTeX ($...$, $$...$$)로 표기
- 텍스트가 너무 길면 Write로 앞부분을 쓰고, Edit으로 뒷부분을 append하라
```

서브에이전트 설정:
- `mode: "bypassPermissions"`
- `model: "sonnet"`

이미지 추출 (병렬):
```bash
mkdir -p "${PAPER_DIR}/study/images"
pyenv shell 3.12.12
python3 ${SCRIPTS}/extract-images.py "${PAPER_DIR}/paper.pdf" "${PAPER_DIR}/study/images/"
```

---

## Step 2: 논문 평가 (Assessment)

full-text.md를 읽고 (청크 분할: 1000줄 초과 시 1000줄씩, 100줄 오버랩) 다음을 평가:

1. **난이도**: Beginner / Intermediate / Advanced / Highly Theoretical
2. **논문 유형**: Theoretical / Architecture / Empirical / System Design / Survey
3. **방법론 복잡도**: Simple Pipeline / Multi-stage / Novel Architecture / Heavy Math

이 평가 결과가 이후 생성할 자료의 깊이와 종류를 결정한다.

---

## Step 3: 핵심 학습 자료 생성

모든 파일은 `${PAPER_DIR}/study/` 아래에 생성한다.

### 3-1. summary.md (필수)
- 배경 및 문제 정의
- 핵심 기여 (numbered, 각 2-3문장)
- 주요 결과 (정량적 수치 포함)
- 한줄 요약

### 3-2. insights.md (가장 중요)
- 핵심 아이디어를 평이하게 설명
- 왜 이것이 작동하는지
- 어떤 개념적 전환(conceptual shift)을 도입하는지
- Trade-offs & 한계
- 선행 연구 대비 차이점
- 실무적 함의

### 3-3. method.md (대부분의 논문에 권장)
- 구성요소 분해 (component breakdown)
- 알고리즘 흐름
- 아키텍처 다이어그램 (ASCII)
- 단계별 설명 + 의사코드
- 구현 함정 (pitfalls)
- 하이퍼파라미터 민감도

### 3-4. qa.md (필수)
15개 질문 (기본 5 / 중급 5 / 고급 5):

```markdown
### Question

<details>
<summary>Answer</summary>

상세한 설명.

</details>

---
```

### 3-5. mental-model.md (권장)
- 이 논문이 풀고 있는 문제 유형
- 전제하는 사전 지식
- 넓은 연구 지도에서의 위치
- 이 연구를 어떻게 분류할 것인지

---

## Step 4: 코드 데모 (최소 1개 필수)

```bash
mkdir -p "${PAPER_DIR}/study/code"
```

가이드라인:
- Self-contained, 독립 실행 가능
- 교육적 주석 (why 중심)
- 핵심 기여에 집중, 명확성 > 완전성
- 설명적 파일명 (model_demo.py, contrastive_loss_viz.py 등)

가능한 유형:
- 단순화된 핵심 구현
- 시각화 스크립트
- 최소 아키텍처 데모
- 인터랙티브 노트북 (.ipynb)

---

## Step 5: 이미지 정리

`study/images/` 디렉토리의 핵심 이미지를 설명적 이름으로 rename:
- page_1_img_1.png → architecture.png
- page_5_img_2.png → training_pipeline.png

생성된 마크다운 파일들의 이미지 참조도 함께 업데이트.

---

## Step 6: 완료 + 대화형 학습

모든 파일 생성 후 사용자에게 출력:

```
논문 분석 완료: ${PAPER_DIR}/study/

생성된 자료:
  - summary.md (요약)
  - insights.md (핵심 통찰)
  - method.md (방법론 분석)
  - qa.md (Q&A 15문항)
  - mental-model.md (멘탈 모델)
  - code/ (코드 데모)
  - images/ (추출된 이미지)
```

이후 사용자에게 질문:
- 아직 불명확한 부분이 있나요?
- 수학적 유도 과정을 더 깊이 분석할까요?
- 구현 수준의 분석이 필요한가요?
- 다른 논문과 비교해볼까요?

### 추가 질문 시
같은 `study/` 폴더에 새 파일 생성:
- deep-dive-contrastive-loss.md
- math-derivation-breakdown.md
- comparison-with-transformers.md

### 사용자가 자신의 요약을 제공하면
1. 구조 개선 및 정제
2. `study/user-summary-v1.md`로 저장 (반복 시 v2, v3...)

---

## 작성 원칙 (공통)

- **언어**: 사용자의 입력 언어를 감지하여 모든 자료를 해당 언어로 생성. 기술 용어는 영어 유지.
- **분량**: 각 파일은 충분한 깊이를 가져야 한다. 단순 나열이 아닌, 논문의 논리 흐름을 따라가며 "왜 이런 설계를 했는지"까지 설명.
- **구체성**: 핵심 개념에는 반드시 논문의 예시나 코드 스니펫을 포함.
- **figure 활용**: 가능한 모든 figure를 참조하고, 각 figure가 무엇을 보여주는지 설명.
- 반드시 Write 도구로 파일을 생성하라.
