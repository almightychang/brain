---
description: "GitHub 레포를 옵시디언 Second Brain에 아카이빙하고 구조화된 요약을 생성한다. GitHub API로 메타데이터 수집, README 추출, 서브에이전트 기반 요약까지 자동화."
allowed-tools: Bash, Write, Edit, Read, Glob, Grep, Agent, WebFetch
---

# brain:repo-add — GitHub 레포 → 옵시디언 아카이빙

## 전제 조건

이 스킬 실행 전 `${CLAUDE_PLUGIN_ROOT}/config.md`를 읽어 VAULT, WORKSPACES 경로를 확인한다.

GitHub 레포 URL을 받아 옵시디언 Second Brain에 체계적으로 아카이빙하고, 핵심을 파악할 수 있는 요약을 생성한다.

## 입력

사용자가 `/brain:repo-add <github-url>` 형태로 호출.
예: `/brain:repo-add https://github.com/vllm-project/vllm`

URL에서 `OWNER`와 `REPO`를 추출한다.

---

## Step 1: 간단히 살펴보기 — 메타데이터 + README 수집

### 1-1. GitHub 메타데이터 수집

`gh` CLI로 레포 메타데이터를 가져온다.

```bash
gh repo view ${OWNER}/${REPO} --json name,description,url,stargazerCount,forkCount,primaryLanguage,languages,licenseInfo,repositoryTopics,createdAt,updatedAt,homepageUrl,isArchived
```

추출할 필드:
- name, description, url
- stars, forks, primary language, all languages
- license, topics
- created/updated dates
- homepage URL (있으면)
- archived 여부

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

README 다운로드:
```bash
mkdir -p "${REPO_DIR}"
gh api "repos/${OWNER}/${REPO}/readme" --jq '.content' | base64 -d > "${REPO_DIR}/README.md"
```

README가 없는 레포도 있으므로 실패 시 빈 파일로 진행한다.

Step 1-1과 1-2는 병렬로 실행한다.

---

## Step 2: 소개와 인터뷰

### 2-1. 프로젝트 소개

README를 빠르게 읽고(500줄 이하면 한 번에, 초과면 앞부분 500줄만), 메타데이터와 함께 사용자에게 프로젝트를 **대화체로 소개**한다.

**소개 형식:**

```
## 프로젝트 소개: {{OWNER}}/{{REPO}}

### 이게 뭔가
{{프로젝트의 목적과 해결하는 문제를 2-3 문단으로. "왜 이게 존재하는지"를 강조}}

### 핵심 아이디어
{{기술적 핵심을 직관적으로 설명. 다른 유사 도구와의 차이점 포함}}

### 왜 주목할 만한가
{{stars, 커뮤니티, 기술적 혁신 등의 관점에서 1-2문장}}
```

**작성 원칙:**
- 한국어로 작성, 기술 용어는 영어 유지
- foldernote의 구조를 그대로 따르지 말고, **이야기하듯** 설명
- 분량: 최소 15줄 이상

### 2-2. 아카이빙 이유 질문

소개 직후, 사용자에게 질문한다:

```
이 레포를 아카이빙하는 이유가 뭔가요? (한 줄이면 충분합니다)
예: "로봇 시뮬레이션에 활용 검토", "설계 패턴 참고", "팀에 도입 후보"
```

사용자의 답변을 `ARCHIVE_REASON`으로 저장하여 foldernote에 반영한다.

---

## Step 3: 깊은 탐색 — 서브에이전트로 foldernote 생성

> **핵심**: README가 길 수 있으므로 서브에이전트에 위임하여 컨텍스트를 격리한다.

서브에이전트에게 다음 프롬프트를 전달:

```
GitHub 레포의 README와 메타데이터를 읽고 구조화된 요약을 생성하라.

## 입력
- README 경로: ${REPO_DIR}/README.md
- 출력 경로: ${REPO_DIR}/${OWNER}-${REPO}.md  (foldernote)
- 메타데이터 (JSON으로 전달):
  ${METADATA_JSON}
- 아카이빙 이유: ${ARCHIVE_REASON}

## 청크 분할 전략
README가 500줄을 초과하면:
1. 500줄씩, 50줄 오버랩을 두고 분할하여 읽는다
2. 모든 청크를 읽은 후 종합하여 foldernote를 작성한다

500줄 이하면 한 번에 읽는다.

## foldernote 형식

---
type: repo
url: {{repo URL}}
stars: {{stargazersCount}}
forks: {{forkCount}}
language: {{primaryLanguage}}
license: {{license}}
topics: [{{topics}}]
archived_date: {{오늘 날짜}}
tags:
  - repo
  - {{language 태그}}
  - {{분야 태그들}}
---

# {{REPO 이름}}

> [!info] 메타데이터
> - **GitHub**: [{{OWNER}}/{{REPO}}]({{url}})
> - **Stars**: {{stars}} ⭐ / **Forks**: {{forks}}
> - **Language**: {{primaryLanguage}} ({{other languages}})
> - **License**: {{license}}
> - **Homepage**: {{homepage URL, 있으면}}
> - **Created**: {{created}} / **Updated**: {{updated}}

## 한줄 요약

{{이 프로젝트가 무엇인지 한 문장으로}}

## 왜 아카이빙했는가

{{ARCHIVE_REASON을 기반으로 작성. 사용자의 맥락에서 이 레포가 왜 의미 있는지}}

## 핵심 기능

{{README에서 추출한 주요 기능 목록}}
- 각 기능을 1-2문장으로 설명
- 단순 feature list 나열이 아닌, "왜 이 기능이 중요한지" 포함

## 아키텍처 / 설계 특징

{{README나 프로젝트 구조에서 파악 가능한 설계 특징}}
- 기술 스택
- 핵심 설계 결정
- 다른 유사 프로젝트와의 차별점
- 파악이 어려우면 README에서 유추 가능한 범위만 작성

## 빠른 시작

{{설치 및 기본 사용법 — README의 Getting Started를 요약}}
- 핵심 명령어만 코드블록으로
- 불필요한 세부 옵션은 생략

## 주목할 점

> [!tip] 이 프로젝트에서 가져갈 것
> {{이 레포의 독특한 관점, 기술적 혁신, 또는 실용적 가치 — 3-5개 bullet point}}

## 관련 링크

{{README에서 발견한 관련 프로젝트, 논문, 문서 링크}}
- 옵시디언 vault에 이미 있는 논문이 있으면 wikilink 사용

## 작성 원칙
- 한국어로 작성, 기술 용어는 영어 유지
- 분량: 최소 100줄 이상
- README의 구조를 그대로 옮기지 말고, 핵심을 재구성하여 작성
- 반드시 Write 도구로 파일을 생성하라
```

서브에이전트 설정:
- `mode: "bypassPermissions"` (파일 쓰기 자동 허용)
- `model: "sonnet"` (빠른 처리)

---

## Step 4: 완료 + Thread 추천

모든 서브에이전트 완료 후, foldernote를 Read로 읽어서 내용을 확인한다.

### 4-1. 관련 항목 연결 추천

방금 추가한 레포가 기존 vault 콘텐츠와 연결될 수 있는지 확인:

1. `${VAULT}/6. Thread/` 에서 thread 스캔 (Glob: `*.md`, path: `${VAULT}/6. Thread`)
2. `${VAULT}/3. Resources/papers/` 에서 관련 논문 탐색 (폴더명 기준 빠른 스캔)
3. `${VAULT}/3. Resources/repos/` 에서 관련 레포 탐색 (있으면)

**연결이 있으면:**
```
🔗 관련 항목:
  - 📄 논문: [[논문명]] — {{연결 이유}}
  - 🧵 Thread: "{{thread 제목}}" — {{연결 이유}}
  - 🔧 레포: [[레포명]] — {{연결 이유}}
```

**연결이 없으면:** 이 섹션을 출력하지 않는다.

### 4-2. 완료 출력

```
✅ 레포 아카이빙 완료: ${REPO_DIR}

📁 생성된 파일:
  - ${OWNER}-${REPO}.md (foldernote — 구조화된 요약)
  - README.md (원본)

📚 더 알아보려면:
  /brain:grok ${REPO_DIR}/${OWNER}-${REPO}.md
```
