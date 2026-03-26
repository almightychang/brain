---
name: graph
description: "Obsidian vault의 연결 구조에 대해 그래프 쿼리를 실행한다. neighbors, path, hubs, bridges, orphans, vault-stats, suggest-links, health 등 지원."
allowed-tools: Bash, Read, Write, Glob, Grep
---

# Obsidian Graph Query

Obsidian vault의 연결 구조에서 그래프 쿼리를 실행한다. 데이터 소스는 `app.metadataCache.resolvedLinks`(완전 인접 테이블)이며, JS eval로 그래프 알고리즘을 실행한다.

---

## 전제 조건

쿼리 실행 전:

1. `${CLAUDE_SKILL_DIR}/references/vault-config.md`에서 설정 읽기:
   - `<CLI>`: Obsidian CLI 실행 경로
   - `<VAULT>`: vault 이름 (`vault=` 파라미터용)
   - `EXCLUDED_FOLDERS`: 제외 폴더 목록 (JSON 배열)
   - `RELATIONSHIP_FIELDS`: 관계 필드 목록 (JSON 배열)
2. Obsidian이 실행 중인지 확인
3. `vault-config.md`가 없으면 사용자에게 `vault-config.md.template`에서 복사 후 작성하도록 안내

---

## 쿼리 선택 가이드

```
사용자 질문
├─ "이 노트 주변에 뭐가 있어?"          → neighbors
├─ "A와 B는 어떻게 연결돼?"             → path
├─ "이 노트에서 도달 가능한 노트는?"      → cluster
├─ "가장 중요한 노트는?"                → hubs
├─ "고립된 노트는?"                     → orphans-rich
├─ "지식 그래프의 구조적 약점은?"         → bridges
├─ "이 노트와 이웃의 관계는?"            → relationship-summary
└─ "vault 전체 상태는?"                 → vault-stats
```

---

## 쿼리 인덱스

| # | 쿼리명 | 용도 | 파라미터 | 템플릿 위치 |
|---|--------|------|----------|------------|
| 1 | **neighbors** | N-hop 이웃 탐색 | `NOTE_PATH`, `MAX_HOPS`=2 | query-templates.md §1 |
| 2 | **path** | 두 노트 간 최단 경로 | `FROM_PATH`, `TO_PATH` | query-templates.md §2 |
| 3 | **cluster** | 연통 부분그래프 (도달 가능한 모든 노트) | `NOTE_PATH` | query-templates.md §3 |
| 4 | **bridges** | 브릿지 엣지 + 관절점 | 없음 | query-templates.md §4 |
| 5 | **hubs** | Top N 연결도 | `TOP_N`=20, `FOLDER_FILTER`='' | query-templates.md §5 |
| 6 | **orphans-rich** | 고립 노트 + frontmatter | `FOLDER_FILTER`='' | query-templates.md §6 |
| 7 | **frontmatter-relations** | 관계 필드 추출 | `NOTE_PATH` | query-templates.md §7 |
| 8 | **vault-stats** | Vault 전역 통계 | 없음 | query-templates.md §8 |
| 9 | **suggest-links** | 잠재적 연결 제안 (고립 구제 + 누락 연결) | `MAX_SUGGESTIONS`=30, `FRONTMATTER_MAPPING` | query-templates.md §9 |

relationship-summary와 /health는 단일 템플릿이 아닌 다단계 Agent 워크플로 (아래 참조).

---

## 실행 모드

### 단계

1. **설정 읽기**: `${CLAUDE_SKILL_DIR}/references/vault-config.md`에서 CLI 경로, vault 이름, 제외 폴더, 관계 필드 읽기
2. **템플릿 읽기**: `${CLAUDE_SKILL_DIR}/references/query-templates.md`에서 해당 JS 템플릿 읽기
3. **파라미터 대입**:
   - `{{EXCLUDED_FOLDERS}}` → vault-config.md의 제외 폴더 JSON 배열
   - `{{RELATIONSHIP_FIELDS}}` → vault-config.md의 관계 필드 JSON 배열
   - `{{FRONTMATTER_MAPPING}}` → vault-config.md의 Frontmatter 필드 매핑 JSON 객체. 기본값: `{ "domain": "tags", "source": "created-by", "noteType": "type" }`
   - 기타 `{{PARAM}}` 플레이스홀더를 사용자 제공 값으로 대체
   - **문자열 이스케이프**: `{{NOTE_PATH}}`, `{{FROM_PATH}}`, `{{TO_PATH}}`, `{{FOLDER_FILTER}}` 대입 전에 값 내의 `'`를 `\'`로 대체 (템플릿에서 작은따옴표로 감싸져 있으므로)
   - **숫자 검증**: `{{MAX_HOPS}}`는 1-5 정수, `{{TOP_N}}`은 1-100 정수. 범위 초과 시 기본값 사용 (MAX_HOPS=2, TOP_N=20)
4. **임시 파일 작성**: Write 도구로 `/tmp/obsidian_graph_query.js`에 작성
5. **실행**: Bash 도구로 실행:
   ```bash
   <CLI> vault="<VAULT>" eval code='eval(require("fs").readFileSync("/tmp/obsidian_graph_query.js","utf8"))'
   ```
6. **파싱**: 출력은 JSON 문자열, 파싱 후 Markdown으로 표현

---

## 노트 이름 해석

사용자는 보통 부분 이름만 제공 (예: "BFS 관련 노트"). 해석 절차:

1. Obsidian CLI의 `search` 명령으로 검색:
   ```bash
   <CLI> vault="<VAULT>" search query="BFS" limit=5
   ```
2. 결과에서 완전한 경로 추출 (예: `notes/알고리즘/BFS.md`)
3. 완전한 경로를 템플릿의 `{{NOTE_PATH}}`에 대입

**중요**: 템플릿의 경로는 vault root부터의 완전한 상대 경로 + `.md` 확장자 필수.

---

## 필터링 옵션

### 폴더 필터링

`hubs`와 `orphans-rich`는 `FOLDER_FILTER` 파라미터 지원:

- 빈 문자열 `''`: 필터 없음 (전체 vault)
- 폴더 접두사: 예 `'notes/'` (끝 슬래시 포함)

### Frontmatter 필터링

frontmatter 속성으로 필터가 필요하면 후처리:

1. hubs/orphans-rich 실행으로 결과 획득
2. 결과의 노트에 `properties` 명령으로 frontmatter 확인
3. 조건에 맞지 않는 노트 필터링

---

## 관계 분석 워크플로 (relationship-summary)

다단계 Agent 프로세스 (단일 템플릿 아님).

### 적용 시나리오

- "이 노트와 어떤 노트들이 어떤 관계야?"
- "A와 B 사이의 관계는?"
- "특정 주제 아래 노트 구조 분석"

### 절차

```
1. 범위 판단
   ├─ 단일 노트 → neighbors(maxHops=1) + frontmatter-relations
   ├─ 두 노트 → path + 양쪽 frontmatter-relations
   └─ 주제/폴더 → hubs(folderFilter) + 샘플 분석

2. 그래프 쿼리 실행, 구조적 데이터 획득

3. Frontmatter 관계 필드 읽기
   └─ frontmatter-relations 템플릿으로 설정의 관계 필드 조회

4. Inline dataview 필드 확인 (선택)
   ├─ Obsidian CLI read 명령으로 노트 내용 읽기
   └─ 정규식 파싱: \[(\w+)::\s*\[\[([^\]]+)\]\]\]

5. 라벨 없는 연결 → LLM 추론 (선택)
   ├─ 양쪽 노트의 첫 500자 읽기
   ├─ 공통 frontmatter 속성 비교
   └─ relationship-types.md의 프롬프트 템플릿으로 추론

6. 관계 요약 생성
   ├─ 출처 표시: ✅ frontmatter / ✅ inline / 🤖 LLM 추론
   └─ 테이블 또는 그래프로 표현
```

---

## 건강 체크 워크플로 (/health)

vault 구조 건강도를 일괄 스캔하여 건강 보고서 + 행동 제안 생성.

### 적용 시나리오

- "vault 건강해?" "/health"
- "지식 기반에 문제가 있어?"
- 월간 vault 정기 점검

### 절차

```
1. 설정 읽기 (vault-config.md)
2. 세 가지 eval 쿼리 실행:
   ├─ 2a. vault-stats (§8) → 기본 KPI
   ├─ 2b. bridges (§4) → 구조적 리스크
   └─ 2c. suggest-links (§9) → 연결 제안
3. KPI 계산 + 건강 등급 판정
4. 건강 보고서 생성 (Markdown)
```

### KPI 정의

| KPI | 설명 | 출처 필드 | 🟢 건강 | 🟡 주의 | 🔴 경고 |
|-----|------|----------|---------|---------|---------|
| 고립 노트 비율 | 연결 없는 노트 비율 | orphanRatio | <10% | 10-25% | >25% |
| 지식망 연결도 | 최대 컴포넌트가 전체에서 차지하는 비율 | largestComponentRatio | >80% | 50-80% | <50% |
| 평균 연결 수 | 노트당 평균 연결 수 | avgLinksPerNote | >3.0 | 1.5-3.0 | <1.5 |
| 교차 폴더 연결율 | 다른 폴더를 가로지르는 연결 비율 | crossFolderRatio | >20% | 10-20% | <10% |
| 핵심 허브 의존도 | 제거 시 그래프가 분열되는 노트 비율 | articulationPoints / totalNotes | <5% | 5-15% | >15% |
| 단방향 연결율 | 연결 보내지만 인용 안 되는 비율 | outOnlyCount / totalNotes | <5% | 5-15% | >15% |

### 출력 형식

```markdown
# Vault 건강 보고서

> 시간: YYYY-MM-DD | Vault: <name> | 노트 수: N

## 총체 평가: [대체로 건강 / 개선 여지 있음 / 관심 필요]

## KPI 대시보드

| 지표 | 수치 | 상태 | 설명 |
|------|------|------|------|
| 고립 노트 비율 | 15.2% | 🟡 주의 | X편의 노트에 아무 연결 없음 |
| ... | ... | ... | ... |

## 구조 리스크

지식망의 "핵심 허브" — 제거 시 지식망 분열 가능:
- 노트명 (연결 수: N)

## 연결 제안

### 고립 노트 구제 (Top 10)

| 고립 노트 | 추천 연결 대상 | 유사도 | 이유 |
|----------|-------------|--------|------|

### 누락된 연결 (Top 10)

| 노트 A | 노트 B | 공통 이웃 수 | 유사도 |
|--------|--------|------------|--------|

## 행동 제안

1. (가장 심각한 KPI 기반 구체적 실행 가능한 제안 3-5개)
2. 특정 성격의 노트(데일리 노트, 일기 등)가 KPI를 크게 끌어내리는 경우, 해당 폴더를 제외 목록에 추가 후 재실행 권장.
```

### 건강 등급 판정

- **대체로 건강**: 모든 KPI 🟢 또는 최대 1개 🟡
- **개선 여지 있음**: 2개 이상 🟡 또는 1개 🔴
- **관심 필요**: 2개 이상 🔴

---

## NEVER

- NEVER `eval code=` 파라미터에 직접 전체 JS 코드 작성 — 반드시 임시 파일에 쓰고 `fs.readFileSync`로 로드. 인용부호 이스케이프 문제 방지
- NEVER `{{NOTE_PATH}}`에 노트 이름만 사용 — vault root부터의 완전한 상대 경로 + `.md` 확장자 필수
- NEVER Obsidian 미실행 상태에서 쿼리 실행 — 조용히 실패함
- NEVER `{{MAX_HOPS}}`에 5 초과 값 대입 — BFS가 전체 그래프 순회, 출력 과다
- NEVER `resolvedLinks` 키 존재를 연결 있음으로 간주 — 0개 연결의 빈 entry일 수 있음
- NEVER 문자열 플레이스홀더에 작은따옴표 포함 값을 이스케이프 없이 대입 — JS 구문 파괴

---

## 출력 관례

### Markdown 표현

| 쿼리 | 표현 방식 |
|------|----------|
| neighbors | 레이어별 그룹 목록, 각 레이어에 hop 수 표시 |
| path | 화살표 연결 경로: `A → B → C` (hop 수 표시) |
| cluster | 폴더별 그룹 테이블 (truncated 시 카운트 표시) |
| bridges | 두 테이블: 브릿지 엣지 + 관절점 (degree 포함) |
| hubs | 정렬 테이블: 노트명, in-degree, out-degree, total |
| orphans-rich | 테이블: 노트명, 수정일, frontmatter 요약 |
| frontmatter-relations | 관계 테이블 + 연결 통계 |
| vault-stats | JSON 구조화 데이터 (vault-report 워크플로 소비용, 직접 표현 안 함) |
| suggest-links | JSON 구조화 데이터 (Agent가 학습 동반자 역할로 사용자에게 질문/토론 유도) |
| /health | 완전한 Markdown 건강 보고서 (Agent가 세 쿼리 결과 종합) |

### 대량 결과 절단

- neighbors: 50개 초과 시 top 50만 (degree 정렬)
- cluster: 500 노드 초과 시 폴더 카운트 모드로 전환
- orphans-rich: 최대 100건
- bridges: 최대 50 브릿지 엣지 + 30 관절점
- hubs: TOP_N으로 제어 (기본 20)
- vault-stats: componentSizes 최대 20개, outOnlyNotes 최대 50건
- suggest-links: orphanSuggestions 최대 30건, missingLinkSuggestions 최대 30건

### 노트 이름 표시

출력 시 경로 접두사와 `.md` 확장자 제거, 노트 이름만 표시. 동일 이름이 다른 폴더에 있으면 폴더명 유지하여 구분.
