# Brain — Claude Code Plugin for Obsidian Second Brain

Obsidian Second Brain 지식 관리를 위한 Claude Code plugin. 15개 스킬 제공.

## Skills

| Skill | 설명 |
|-------|------|
| `brain:search` | vault에서 관련 노트 후보를 recall 우선으로 수집 (Grep + bge-m3 벡터) |
| `brain:connect` | 문서 간 누락된 연결을 발견하고 단방향 위키링크 추가 |
| `brain:brainstorm` | 아이디어 기반 지식 큐레이션 + 브레인스토밍 문서 생성 |
| `brain:thread` | 관심 주제의 흐름(thread) 발견 및 관리 |
| `brain:graph` | vault 연결 구조에 대한 그래프 쿼리 (neighbors, hubs, bridges, health 등) |
| `brain:goodmorning` | 모닝 브리핑 데일리 노트 생성 (태스크, 코드 변경, 읽을거리) |
| `brain:paper-add` | arxiv 논문을 vault에 아카이빙 + 구조화된 요약 생성 |
| `brain:paper-study` | 논문 심층 분석 + 학습 자료 생성 (Q&A, 코드 데모 등) |
| `brain:repo-add` | GitHub 레포를 vault에 아카이빙 + 구조화된 요약 생성 |
| `brain:book-add` | 교보문고에서 책 정보 검색 → 독서 목록 노트 생성 |
| `brain:grok` | 바이너리 서치 방식의 대화형 학습 튜터 |
| `brain:inbox-review` | Inbox 큐레이션 → PARA 폴더로 이관 |
| `brain:list-project` | 프로젝트 목록 조회 |
| `brain:open-project` | 프로젝트 폴더 탐색 + 핵심 요약 |
| `brain:text-to-pdf` | Markdown → PDF 변환 (한글, 코드블록, 테이블 지원) |

## Setup

### 1. Install

```bash
claude plugin marketplace add https://github.com/almightychang/brain.git
claude plugin install brain
```

### 2. Configure

```bash
cp config.md.template config.md
```

`config.md`를 열어 자신의 vault 경로와 workspaces 경로를 입력:

```markdown
| VAULT | `/path/to/your/obsidian/vault` |
| WORKSPACES | `/path/to/your/workspaces` |
```

> `config.md`는 `.gitignore`에 포함되어 repo에 push되지 않습니다.

### 3. Dependencies

- **Obsidian CLI** — `brain:graph` 스킬에서 사용
- **ollama + bge-m3** — `brain:search` 벡터 검색에서 사용
- **uv** — Python 스크립트 실행
- **Node.js** — PDF 다운로드 스크립트

## Structure

```
.claude-plugin/
├── plugin.json          # Plugin 메타데이터
└── marketplace.json     # Marketplace 등록 정보
skills/
├── search/SKILL.md      # 각 스킬 정의
├── connect/SKILL.md
├── graph/
│   ├── SKILL.md
│   └── references/      # 그래프 쿼리 템플릿 + vault 설정
├── ...
scripts/
├── search/              # 벡터 검색 Python 스크립트
├── paper/               # PDF 다운로드/이미지 추출
└── text-to-pdf/         # Markdown → PDF 변환
config.md                # 개인 경로 설정 (gitignored)
config.md.template       # 설정 템플릿
```
