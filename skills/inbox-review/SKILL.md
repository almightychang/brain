---
description: "Obsidian Inbox를 검토하고, 항목을 큐레이션하여 적절한 PARA 폴더로 이관한다."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, Skill
---

# brain:inbox-review — Inbox 큐레이션 & PARA 정리

## 전제 조건

이 스킬 실행 전 `${CLAUDE_PLUGIN_ROOT}/config.md`를 읽어 VAULT, WORKSPACES 경로를 확인한다.

Obsidian Second Brain의 `0. Inbox` 폴더를 검토하고, 각 항목을 큐레이션하여 사용자에게 설명한 뒤, 적절한 PARA 위치로 이관하는 스킬.

## 경로 상수

```
VAULT="{config.md의 VAULT}"
INBOX="${VAULT}/0. Inbox"
PROJECT="${VAULT}/1. Project"
AREAS="${VAULT}/2. Areas"
RESOURCES="${VAULT}/3. Resources"
ARCHIVE="${VAULT}/4. Archive"
```

## 입력

`/brain:inbox-review` — 인자 없이 호출. 선택적으로 `/brain:inbox-review 5`처럼 최대 처리 개수를 지정할 수 있다 (기본: 전체).

---

## Step 1: Inbox 스캔

`0. Inbox/` 하위의 모든 파일과 폴더를 수집한다.

- **하위 폴더**: 폴더 단위로 묶어 하나의 항목으로 취급 (폴더 내 foldernote 또는 README 우선 읽기)
- **파일 분류**:
  - `.md` — 본문 읽기
  - `.pdf` — 제목과 첫 페이지만 읽기 (`Read` tool, `pages: "1"`)
  - `.txt` — 본문 읽기
  - `.png`, `.jpg`, `.jpeg` — 이미지로 인식, 파일명에서 컨텍스트 추론
  - 기타 — 파일명과 확장자만 기록

**Daily Notes 폴더는 제외한다.**

---

## Step 2: 항목별 큐레이션 (병렬 처리)

각 항목에 대해 Agent를 사용하여 병렬로 분석한다. 한 번에 최대 5개까지 병렬 처리.

각 항목의 분석 결과물:

```yaml
title: "항목 제목 (파일명 또는 본문에서 추출)"
type: "md | pdf | txt | image | folder | other"
summary: "2-3문장 요약"
highlights: ["핵심 포인트 1", "핵심 포인트 2"]  # 중요한 내용
suggested_destination: "PARA 위치 (예: 2. Areas/Agentic AI)"
reason: "이 위치를 추천하는 이유 (한 줄)"
confidence: "high | medium | low"
```

### 큐레이션 기준

**PARA 분류 기준:**
- **1. Project** — 명확한 마감/목표가 있는 진행 중인 작업
- **2. Areas** — 지속적으로 관리해야 하는 영역 (커리어, 재무, 건강, 특정 기술 등)
- **3. Resources** — 나중에 참고할 수 있는 자료 (논문, 아티클, 레시피 등)
- **4. Archive** — 완료됐거나 더 이상 관련 없는 항목

**기존 폴더 매칭:**
- 이관 전에 반드시 기존 PARA 폴더 목록을 확인하여, 가장 적합한 **기존 폴더**에 매칭한다.
- 적합한 기존 폴더가 없을 때만 새 폴더를 제안한다.

**Highlights 기준:**
- 실행 가능한 인사이트 (actionable)
- 현재 프로젝트/관심사와 관련된 내용
- 놀랍거나 반직관적인 사실
- 핵심 수치나 데이터

---

## Step 3: 큐레이션 리포트 출력

모든 항목 분석이 끝나면, 다음 형식으로 사용자에게 보고한다:

```markdown
## 📥 Inbox Review

**총 {N}개 항목** | 검토일: YYYY-MM-DD

---

### 🔴 즉시 처리 권장 (confidence: high)

| # | 항목 | 요약 | 이관 위치 |
|---|------|------|-----------|
| 1 | **제목** | 요약... | `2. Areas/XXX` |

> **💡 Highlights**
> - highlight 1
> - highlight 2

---

### 🟡 검토 필요 (confidence: medium)

(같은 형식)

---

### ⚪ 참고용 / 판단 보류 (confidence: low)

(같은 형식)

---

### 📊 요약
- Project로 이관: N개
- Areas로 이관: N개
- Resources로 이관: N개
- Archive로 이관: N개
- 판단 보류: N개
```

---

## Step 4: 사용자 확인 & 이관

리포트 출력 후, 사용자에게 확인을 요청한다:

```
이관을 진행할까요?
- "전체" — 모든 제안대로 이관
- "1,3,5" — 해당 번호만 이관
- "1→3. Resources/논문" — 특정 항목의 위치 변경 후 이관
- "취소" — 아무것도 하지 않음
```

### 이관 실행

사용자가 승인한 항목에 대해:

1. **대상 폴더 존재 확인** — 없으면 생성
2. **파일 이동** — `mv` 명령 사용
3. **이동 결과 보고** — 성공/실패 리스트 출력

```
✅ 이관 완료 (N/M개 성공)
- "제목A" → 2. Areas/Agentic AI
- "제목B" → 3. Resources/논문
❌ 실패
- "제목C" — 사유: ...
```

---

## 원칙

- **비파괴적**: 파일을 삭제하지 않는다. 이동만 한다.
- **사용자 결정 우선**: 자동 이관 없음. 반드시 사용자 확인 후 실행.
- **기존 구조 존중**: 새 폴더 생성보다 기존 폴더 활용을 우선한다.
- **간결한 요약**: 사용자가 빠르게 판단할 수 있도록 핵심만 전달한다.
- **PDF/이미지 주의**: 바이너리 파일은 내용을 완전히 파악하기 어려우므로 confidence를 낮게 설정한다.
