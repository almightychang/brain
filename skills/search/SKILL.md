---
description: "Obsidian Second Brain에서 관련 노트 후보를 recall 우선으로 수집한다. brainstorm, connect, thread 등에서 소비."
allowed-tools: Bash, Read, Grep, Glob
---

# brain:search — vault 노트 후보 검색

주제 쿼리에 대해 vault에서 관련 노트 후보를 **recall 우선**으로 수집하여, 소비자가 필터링할 수 있는 원재료를 제공한다.

키워드 매칭(Grep)과 의미 유사도(bge-m3 벡터)를 병렬 실행하고 합산한다. precision은 30~45%이므로 노이즈가 포함된다 — 관련성 판단은 소비자(brainstorm, connect, thread, 또는 사용자)의 몫이다.

## 입력

`/brain:search <주제>` — 자연어 또는 쉼표 구분 키워드.

예시:
- `/brain:search 의식과 인공지능의 관계`
- `/brain:search dexterous manipulation, hand grasping`
- `/brain:search 데이터 파이프라인 아키텍처`

---

## 실행

### Step 1: 검색 실행

```bash
cd ${CLAUDE_SKILL_DIR}/scripts && uv run python brain_search.py "<주제>"
```

**캐시 동작:**
- 임베딩 캐시(`vault_embeddings.pkl`, 8MB)가 12시간 이내면 즉시 사용 (3ms)
- 12시간 초과 또는 캐시 없음 → 자동 재생성 (ollama bge-m3, ~84초). stderr에 진행 상황 출력
- 강제 재생성: `uv run python brain_search.py --rebuild-cache`

### Step 2: 결과 해석

JSON 반환. 결과는 3-tier로 정렬:

| Tier | source | 의미 |
|------|--------|------|
| 1 | `both` | Grep과 벡터 모두 발견 — 관련도 높을 가능성이 큼 |
| 2 | `grep` | 키워드 직접 매칭 |
| 3 | `vector` | 의미 유사도만으로 발견 — 키워드 없는 관련 노트일 수 있으나 노이즈 가능 |

### Step 3: 사용자에게 출력

```markdown
## 🔍 검색 결과: {주제}

**캐시**: {fresh (Nh) | 재생성됨}
**결과**: Grep {N}개 + 벡터 {M}개 = 합산 {T}개

| # | 제목 | 경로 | 소스 |
|---|------|------|------|
| 1 | **노트 제목** | `2. Areas/...` | both |
| 2 | **노트 제목** | `6. Thread/...` | grep |
| 3 | **노트 제목** | `3. Resources/...` | vector |
```

안내:
```
이 목록은 recall 우선 후보입니다. 관련 없는 노트가 포함될 수 있습니다.
- "N번 읽기" — 특정 노트 본문 확인
- "brainstorm" — 이 후보들로 브레인스토밍 시작
- "키워드 추가: XXX" — 추가 키워드로 재검색
```

---

## 소비자 인터페이스

다른 skill에서 사용할 때:

```
# brainstorm Step 2-2 대체 (폴더 스캔, 관련도 평가는 brainstorm이 유지)
brain:search.search(keywords + laterals) → candidates
brainstorm.evaluateRelevance(candidates) → curated_list

# connect에서
brain:search.search(note_topic) → candidates
connect.judgeDirection(candidates) → wikilinks

# thread에서
brain:search.search(thread_topic) → candidates
thread.clusterBySubtopic(candidates) → connections
```

---

## 원칙

- **Recall 우선**: 넓게 긁어오고, precision은 소비자에게 위임
- **후보만 반환**: 관련성 판단/분류(direct/indirect/lateral)는 하지 않는다
- **비파괴적**: vault를 수정하지 않는다
- **Transparency**: 캐시 상태, source 구분을 항상 반환에 포함
