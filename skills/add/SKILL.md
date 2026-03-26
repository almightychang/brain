---
description: "vault에 자료를 아카이빙한다. arxiv URL → paper, GitHub URL → repo, 그 외 → book. 입력을 자동 감지하여 도메인별 워크플로를 실행."
allowed-tools: Bash, Write, Edit, Read, Glob, Grep, Agent, WebFetch, WebSearch
argument-hint: "<url-or-title>"
---

# brain:add — vault 아카이빙

외부 자료를 Obsidian Second Brain에 체계적으로 아카이빙한다. 입력을 자동 감지하여 적절한 도메인 워크플로를 실행.

## 전제 조건

이 스킬 실행 전 `${CLAUDE_PLUGIN_ROOT}/config.md`를 읽어 VAULT, WORKSPACES 경로를 확인한다.

## 입력 자동 감지

```
/brain:add <input>
```

| 입력 패턴 | 감지 도메인 | 워크플로 |
|-----------|------------|---------|
| `arxiv.org/abs/...` 또는 `arxiv.org/pdf/...` | **paper** | arxiv 메타데이터 파싱 → PDF 다운로드 → 요약 생성 |
| `github.com/owner/repo` | **repo** | GitHub API 메타데이터 → README 추출 → 요약 생성 |
| 그 외 (책 제목, 검색어 등) | **book** | 교보문고 검색 → 독서 목록 노트 생성 |

명시적 지정도 가능: `/brain:add paper <url>`, `/brain:add repo <url>`, `/brain:add book <title>`

## 공통: 스크립트 경로

```
SCRIPTS="${CLAUDE_SKILL_DIR}/scripts"
```

---
---

# Paper — arxiv 논문 → 옵시디언 아카이빙

arxiv 논문 링크를 받아 옵시디언 Second Brain에 체계적으로 아카이빙하고, 학습 가능한 형태로 요약한다.

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
2. 각 청크를 읽으며 핵심 내용을 메모한다
3. 모든 청크를 읽은 후 종합하여 summary.md를 작성한다

1000줄 이하면 한 번에 읽는다.

## 작성 원칙
- **분량**: 전체 요약은 최소 300줄 이상을 목표로 한다.
- **깊이**: 논문의 논리 흐름을 따라가며 "왜 이런 설계를 했는지"까지 설명.
- **구체성**: 핵심 개념에는 반드시 예시(논문에서 사용한 예시 또는 코드 스니펫)를 포함.
- **figure 활용**: 가능한 모든 figure를 참조하고 설명.

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

## 한줄 요약 / ## 배경 및 문제 / ## 핵심 기여 / ## 방법론 / ## 주요 결과 / ## 한계 및 향후 연구 / ## 핵심 인사이트

## 추가 작업
- figures/ 핵심 figure를 설명적 이름으로 rename
- summary.md와 full-text.md의 figure 참조를 업데이트

## 주의
- 반드시 Write 도구로 파일을 생성하라
- 한국어로 작성하되, 기술 용어는 영어 유지
```

서브에이전트 설정:
- `mode: "bypassPermissions"` (파일 쓰기 자동 허용)
- `model: "sonnet"` (빠른 처리)

---

## Step 5: 완료 + 논문 소개 + Thread 추천

모든 서브에이전트 완료 후, foldernote를 Read로 읽어서 내용을 확인한다.

### 5-1. 논문 내용 소개

foldernote를 기반으로 사용자에게 논문 내용을 **대화체로 자세히 소개**한다. 요약 파일을 복붙하지 않고, 자연스럽게 설명.

**소개 형식:** 이 논문이 풀려는 문제 / 핵심 아이디어 / 주요 결과 / 왜 읽을 만한가

**작성 원칙:**
- 한국어로 작성, 기술 용어는 영어 유지
- **이야기하듯** 설명. 분량: 최소 30줄 이상.
- figure를 적극 활용: `![설명](${PAPER_DIR}/figures/filename.ext)` 절대경로
- 수식이 핵심이면 LaTeX + 직관적 설명

### 5-2. Thread 연결 추천

`${VAULT}/6. Thread/` 스캔 → 연결 가능성 판단. 연결이 없으면 출력하지 않는다.

### 5-3. 완료 출력

```
논문 아카이빙 완료: ${PAPER_DIR}

생성된 파일:
  - ${ARXIV_ID}-${SLUG}.md (foldernote — 구조화된 요약)
  - paper.pdf (원본)
  - full-text.md (전문 텍스트)
  - figures/ (추출된 이미지 N개)

학습하려면:
  /brain:grok ${PAPER_DIR}/${ARXIV_ID}-${SLUG}.md
```

---
---

# Repo — GitHub 레포 → 옵시디언 아카이빙

GitHub 레포 URL을 받아 옵시디언 Second Brain에 체계적으로 아카이빙하고, 핵심을 파악할 수 있는 요약을 생성한다.

URL에서 `OWNER`와 `REPO`를 추출한다.

## Step 1: 메타데이터 + README 수집

### 1-1. GitHub 메타데이터 수집

```bash
gh repo view ${OWNER}/${REPO} --json name,description,url,stargazerCount,forkCount,primaryLanguage,languages,licenseInfo,repositoryTopics,createdAt,updatedAt,homepageUrl,isArchived
```

### 1-2. README 다운로드 + 폴더 생성

```
VAULT="{config.md의 VAULT}"
REPO_DIR="${VAULT}/3. Resources/repos/${OWNER}-${REPO}"
```

폴더 구조 (foldernote 패턴):
```
${REPO_DIR}/
├── ${OWNER}-${REPO}.md   ← foldernote (= 구조화 요약)
└── README.md              ← 원본 README 보존
```

```bash
mkdir -p "${REPO_DIR}"
gh api "repos/${OWNER}/${REPO}/readme" --jq '.content' | base64 -d > "${REPO_DIR}/README.md"
```

README가 없는 레포도 있으므로 실패 시 빈 파일로 진행. Step 1-1과 1-2는 병렬 실행.

---

## Step 2: 소개와 인터뷰

### 2-1. 프로젝트 소개

README를 빠르게 읽고(500줄 이하면 한 번에, 초과면 앞부분 500줄만), 메타데이터와 함께 사용자에게 **대화체로 소개**: 이게 뭔가 / 핵심 아이디어 / 왜 주목할 만한가

**작성 원칙:** 한국어, 기술 용어는 영어 유지, 이야기하듯 설명, 최소 15줄

### 2-2. 아카이빙 이유 질문

```
이 레포를 아카이빙하는 이유가 뭔가요? (한 줄이면 충분합니다)
```

답변을 `ARCHIVE_REASON`으로 저장하여 foldernote에 반영.

---

## Step 3: 서브에이전트로 foldernote 생성

> README가 길 수 있으므로 서브에이전트에 위임하여 컨텍스트를 격리한다.

서브에이전트에게 README + 메타데이터 + ARCHIVE_REASON을 전달하여 구조화된 foldernote 생성.

**foldernote 형식:**
- frontmatter: type, name, url, stars, forks, language, license, topics, archived_date, tags
- 본문: 한줄 요약 / 왜 아카이빙했는가 / 핵심 기능 / 아키텍처·설계 특징 / 빠른 시작 / 주목할 점 / 관련 링크

**작성 원칙:** 한국어, 최소 100줄, README를 재구성하여 작성. Write 도구 사용.

서브에이전트 설정: `mode: "bypassPermissions"`, `model: "sonnet"`

---

## Step 4: 완료 + 연결 추천

foldernote를 Read로 확인 후:

### 4-1. 관련 항목 연결 추천
`${VAULT}/6. Thread/`, `${VAULT}/3. Resources/papers/`, `${VAULT}/3. Resources/repos/` 스캔. 연결이 없으면 출력하지 않는다.

### 4-2. 완료 출력

```
레포 아카이빙 완료: ${REPO_DIR}

생성된 파일:
  - ${OWNER}-${REPO}.md (foldernote — 구조화된 요약)
  - README.md (원본)

더 알아보려면:
  /brain:grok ${REPO_DIR}/${OWNER}-${REPO}.md
```

---
---

# Book — 책 → 옵시디언 독서 목록 추가

책 제목(또는 검색어)을 받아 교보문고에서 정보를 검색하고, 옵시디언 독서 목록에 노트를 생성한다.

인자가 없으면 사용자에게 책 제목을 물어본다.

## Step 1: 책 정보 검색

```
WebSearch: "교보문고 {책 제목}"
```

검색 결과에서 교보문고 상품 페이지 URL을 찾는다.
URL 패턴: `https://product.kyobobook.co.kr/detail/{ISBN}`

---

## Step 2: 메타데이터 추출

WebFetch로 교보문고 상품 페이지에서 추출:
- **제목**, **저자**, **출판일**, **ISBN**, **표지 이미지 URL**, **설명** (한줄 요약 직접 작성)

표지 이미지 URL 패턴: `https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/{ISBN}.jpg`

---

## Step 3: 사용자 확인

추출한 정보를 사용자에게 보여주고 확인. 수정 요청 시 반영.

---

## Step 4: 옵시디언 노트 생성

```
VAULT="{config.md의 VAULT}"
```

**파일 경로**: `${VAULT}/2. Areas/Life - 독서하기/{제목}.md`

**노트 내용**:
```markdown
---
description: {한줄 설명}
tags:
  - 독서
review_status:
  - 1. 독서 예정
cover: https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/{ISBN}.jpg
author:
  - {저자}
published: {출간일 YYYY-MM-DD}
review_started:
review_ended:
---
```

**주의사항**:
- 본문은 비워둔다 (나중에 독서 메모 작성용)
- `review_status`는 항상 `1. 독서 예정`으로 시작
- `review_started`, `review_ended`는 빈 값
- 동일 제목의 파일이 이미 있으면 사용자에게 알리고 중단

---

## Step 5: 완료 메시지

```
독서 노트 생성 완료!

파일: {파일 경로}
상태: 1. 독서 예정

독서를 시작하면 review_status를 "2. 독서 중"으로 변경하세요.
```

---

## 여러 권 동시 추가

사용자가 여러 책을 쉼표나 줄바꿈으로 나열하면, 각 책에 대해 Step 1-4를 반복한다.
검색은 병렬로 수행하고 확인은 한 번에 모아서 받는다.
