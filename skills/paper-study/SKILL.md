---
name: paper-study
description: "논문을 심층 분석하고 학습 자료를 생성한다. PDF를 읽고 난이도 평가, 방법론 분석, Q&A, 코드 데모까지 체계적 학습 환경을 구축."
allowed-tools: Bash, Write, Edit, Read, Glob, Grep, Agent
---

# brain:paper-study — 논문 심층 분석 & 학습

## 전제 조건

이 스킬 실행 전 `${CLAUDE_PLUGIN_ROOT}/config.md`를 읽어 VAULT, WORKSPACES 경로를 확인한다.

논문 PDF를 깊이 읽고, 체계적인 학습 자료를 생성하여 옵시디언 Second Brain에 저장한다.

## 입력

사용자가 `/brain:paper-study <paper-path-or-url>` 형태로 호출.

지원 형식:
- **로컬 경로**: `/brain:paper-study ~/Downloads/paper.pdf`
- **PDF URL**: `/brain:paper-study https://arxiv.org/pdf/1706.03762.pdf`
- **arxiv URL**: `/brain:paper-study https://arxiv.org/abs/1706.03762`
- **기존 paper-add 디렉토리**: `/brain:paper-study ${VAULT}/3. Resources/papers/2301.07041-some-paper/`

---

## Step 0: 입력 분석 & PDF 확보

```
VAULT="{config.md의 VAULT}"
SCRIPTS="${CLAUDE_PLUGIN_ROOT}/scripts/paper"
```

### 경우 1: 기존 paper-add 디렉토리가 주어진 경우
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

## 작성 원칙

- **언어**: 사용자의 입력 언어를 감지하여 모든 자료를 해당 언어로 생성. 기술 용어는 영어 유지.
- **분량**: 각 파일은 충분한 깊이를 가져야 한다. 단순 나열이 아닌, 논문의 논리 흐름을 따라가며 "왜 이런 설계를 했는지"까지 설명.
- **구체성**: 핵심 개념에는 반드시 논문의 예시나 코드 스니펫을 포함.
- **figure 활용**: 가능한 모든 figure를 참조하고, 각 figure가 무엇을 보여주는지 설명.
- 반드시 Write 도구로 파일을 생성하라.
