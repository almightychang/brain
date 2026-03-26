---
description: "오늘의 모닝 브리핑 데일리 노트를 생성한다."
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, WebFetch, WebSearch
---

# Morning Briefing

## 전제 조건

이 스킬 실행 전 `${CLAUDE_PLUGIN_ROOT}/config.md`를 읽어 VAULT, WORKSPACES 경로를 확인한다.

오늘의 모닝 브리핑 데일리 노트를 생성한다.
볼트 경로: config.md의 VAULT

## Step 1: 오늘/어제 날짜 확인

```bash
date +%Y-%m-%d
date -d "yesterday" +%Y-%m-%d
```

## Step 2: 정보 수집 (병렬 실행)

아래 단계를 실행한다. 2-1~2-4는 **병렬 수집**, 2-5는 수집 결과를 종합하는 분석 단계, 2-6은 분석 결과 기반 검색이다.

### 2-1. 어제 완료한 태스크

볼트 전체에서 어제 완료된 태스크를 검색한다.
- 패턴: `✅ {어제날짜}` 를 포함하는 라인
- 검색 경로: `${VAULT}/`
- `- [x]` 로 시작하는 라인만 수집
- 태그(`#RLWRLD` 등)는 유지, 날짜 이모지는 정리해서 읽기 좋게 표시

### 2-2. 오늘 할 일 (Due Today + Overdue)

볼트 전체에서 미완료 + 오늘 이전 마감인 태스크를 검색한다.
- 패턴: `- [ ]` 로 시작하고 `📅` 를 포함하는 라인
- 📅 뒤의 날짜가 오늘 이하인 것만 필터링
- 마감일 기준 정렬 (오래된 것 먼저 = overdue 강조)

### 2-3. 어제 코드 변경점

`${WORKSPACES}/` 아래 git 저장소들의 어제 커밋과 **변경량 통계**를 수집한다.

#### A. 커밋 로그 수집

```bash
for dir in ${WORKSPACES}/*/; do
  if [ -d "$dir/.git" ]; then
    log=$(git -C "$dir" log --after="{어제날짜} 00:00" --before="{오늘날짜} 00:00" --oneline --no-merges 2>/dev/null)
    if [ -n "$log" ]; then
      echo "### $(basename "$dir")"
      echo "$log"
    fi
  fi
done
```

#### B. 변경량 통계 수집

각 저장소의 어제 커밋에 대해 `--shortstat`을 집계하여 **커밋 수, 파일 수, insertions, deletions**를 수집한다.

```bash
for dir in ${WORKSPACES}/*/; do
  if [ -d "$dir/.git" ]; then
    name=$(basename "$dir")
    stats=$(git -C "$dir" log --after="{어제날짜} 00:00" --before="{오늘날짜} 00:00" --no-merges --shortstat --pretty=format:"" 2>/dev/null | awk '
      /files? changed/ {
        for(j=1;j<=NF;j++) {
          if($(j+1) ~ /files?/) f+=$j
          if($(j+1) ~ /insertion/) i+=$j
          if($(j+1) ~ /deletion/) d+=$j
        }
      }
      END { print f, i, d }
    ')
    commits=$(git -C "$dir" log --after="{어제날짜} 00:00" --before="{오늘날짜} 00:00" --no-merges --oneline 2>/dev/null | wc -l)
    if [ "$commits" -gt 0 ]; then
      echo "$name|$commits|$stats"
    fi
  fi
done
```

- 커밋이 있는 저장소만 표시
- 저장소명 + 커밋 메시지 목록 + 변경량 통계
- 통계 데이터는 Step 3의 HTML 인라인 바 렌더링에 사용

### 2-4. 최근 7일 볼트 노트 토픽 수집

볼트에서 최근 7일 이내에 생성 또는 수정된 노트를 수집하고 토픽을 추출한다.

**수집 방법**:
- `${VAULT}/` 아래 최근 7일 이내 수정된 `.md` 파일을 찾는다
- **제외**: `Daily Notes/`, `Templates/`, `Extras/` 폴더
- 각 노트의 제목, 태그(프론트매터 + 인라인), 첫 50줄을 읽어 핵심 토픽을 파악한다

**출력**: 노트별 `{제목} → {토픽 키워드 2-3개}` 목록 (2-5 맥락 분석의 입력으로 사용)

### 2-5. 맥락 분석 (2-1~2-4 수집 완료 후 실행)

2-1~2-4에서 수집한 정보를 **종합 분석**하여 읽을거리 검색의 기반을 만든다. 이 단계는 검색 전에 반드시 완료해야 한다.

#### A. 최근 1주일 완료 태스크 수집

볼트 전체에서 최근 1주일 이내 완료된 태스크를 검색한다.
- 패턴: `✅ {최근7일 날짜}` (어제 포함, 2-1보다 넓은 범위)
- 이 목록 + 2-1 어제 완료 + 2-2 오늘 할 일 + 2-3 코드 변경 + 2-4 최근 볼트 노트 토픽을 함께 본다

#### B. 작업 흐름(work thread) 식별

수집한 전체 데이터를 보고, 현재 진행 중인 **작업 흐름 2-4개**를 식별한다. 작업 흐름이란 "최근 완료한 것 → 오늘 할 것 → 다음에 할 것"으로 이어지는 연속적인 작업 맥락이다.

예시:
- "charuco calibration 개발 완료 → 데이터 품질 가시화 → 데이터셋 정제 동선 구현" = 데이터 품질 파이프라인 흐름
- "egocentric-100k 다운로드 완료 → EgoScale 논문 리뷰" = egocentric 데이터 스케일링 흐름

#### C. 오늘 태스크 맥락 심화

오늘 마감 태스크의 구체적인 내용을 파악한다:
- 태스크에 `[[wikilink]]`가 있으면 해당 노트를 **읽는다** (Read 도구 사용)
- 논문 리뷰 태스크가 있으면 해당 논문의 제목/arXiv ID를 확인한다
- 구현 태스크가 있으면 관련 코드베이스의 최근 변경(2-3)에서 기술 맥락을 파악한다

#### D. 최근 추천 이력 수집 (중복 방지)

최근 3일간 데일리 노트의 읽을거리 섹션에서 **이미 추천한 URL 목록**을 수집한다.

- 대상: `${VAULT}/Daily Notes/` 아래 최근 3일 날짜의 `.md` 파일 (월별 하위 폴더와 flat 구조 모두 확인)
- 패턴: `](http` 를 포함하는 라인에서 URL을 추출
- 이 목록을 **제외 목록(exclusion list)**으로 저장하여 2-6 검색 결과 선별 시 사용한다
- 동일 URL뿐 아니라 **동일 논문/글**(arXiv ID, 제목 일치)도 중복으로 간주한다

#### E. 검색 질문 도출

각 작업 흐름별로 **"오늘 이 작업을 하면서 알면 좋을 것"**을 구체적인 검색 질문 6-8개로 변환한다.

**질문 도출 규칙**:
- 반드시 B에서 식별한 작업 흐름에서 출발한다
- 2-4에서 추출한 최근 볼트 노트 토픽을 작업 흐름과 교차한다 — 최근 작성/수정한 노트의 주제에서 "이어서 읽으면 좋을 것"을 도출
- 정적 관심 분야 키워드("VLA", "macro economy" 등)를 그대로 쓰지 않는다
- 태스크 제목의 단어를 그대로 복사하지 않고, C에서 파악한 구체적 맥락을 반영한다
- 각 질문 옆에 어떤 작업 흐름/태스크에서 도출했는지 표기한다

예시 (좋은 질문):
- "EgoScale egocentric video dexterous manipulation scaling law" ← EgoScale 논문 리뷰 태스크
- "robot teleoperation data filtering gold standard quality gate" ← Lunchbox gold filtered + 데이터 품질 흐름
- "multi-camera extrinsic calibration accuracy validation method" ← charuco calibration 완료 → 품질 검증 다음 단계

예시 (나쁜 질문 — 금지):
- "robot AI data pipeline 2026" ← 관심 분야 키워드 복사
- "macro economy monetary policy February" ← 작업과 무관

### 2-6. 볼트 큐레이션 (내부 자료 서피싱)

2-5에서 식별한 작업 흐름을 기반으로, 볼트 내부에서 **읽어볼 만한 문서**를 선별한다. 웹 검색(2-7)과 별개로, 이미 볼트에 있지만 아직 충분히 활용하지 못한 자료를 꺼내준다.

#### A. Inbox 스캔

`0. Inbox/` 하위의 모든 파일을 수집한다.
- `.md` 파일: 제목, 첫 30줄, 파일 크기(줄 수) 파악
- `.pdf` 파일: 제목과 파일명에서 컨텍스트 추론
- `.png`, `.jpg` 등 이미지: 파일명만 기록
- 하위 폴더: 폴더 단위로 하나의 항목 취급
- **제외**: `Daily Notes/`, `Templates/`, `아이디어/` 폴더
- **정렬**: 파일 수정일 최신순

#### B. 미학습 논문 스캔

`3. Resources/papers/` 하위 논문 폴더를 스캔하여, 깊이 학습하지 않은 논문을 식별한다.

**미학습 판별 기준** (아래 중 하나라도 해당하면 미학습):
- 폴더 내에 `qa.md`, `insights.md`, `mental-model.md`, `method.md` 등 `brain:paper-study` 산출물이 없음
- foldernote(요약)의 내용이 `brain:paper-add` 자동 생성 상태 그대로임 (수동 편집 흔적 없음)

각 미학습 논문의 foldernote에서 제목, 태그, 한줄 요약을 읽는다.

#### C. 선별 & 매칭

2-5 B의 작업 흐름과 교차하여 추천 항목을 선별한다.

**Inbox** (최신순, 관련도 가중):
- 최신 문서를 우선하되, 작업 흐름과 관련 있으면 순위를 높인다
- 건수 제한 없음 — 있는 만큼 유연하게 추천 (보통 5-8건)
- 각 항목에 요약 1문장 + 어떤 작업/관심사와 연결되는지 표기

**논문** (관련도순):
- 작업 흐름과 직결되는 논문 우선
- 보통 4-6건
- 각 항목에 요약 1문장 + 연결 맥락 표기

**잊혀진 것** (오래 방치된 순):
- Inbox에서 **30일 이상** 방치된 항목
- 2-3건
- 각 항목에 방치 기간 + 관심사 연결 표기

#### D. 중복 제거

- 최근 3일간 데일리 노트의 "Vault Curation" 섹션에서 이미 추천한 wikilink를 수집
- 동일 문서는 제외 (제목 또는 파일 경로 일치)

### 2-7. 읽을거리 검색 (맥락 기반)

2-5에서 도출한 검색 질문으로 WebSearch를 **병렬 실행**한다. (2-6 볼트 큐레이션과 병렬 수행 가능)

**총 10-14건을 추천**한다. 네 가지 층위:

| 층위 | 건수 | 설명 |
|------|------|------|
| 직결 | 4-6건 | 오늘 태스크에 직접 도움. 논문 원문, 기술 가이드, 구현 참고 등 |
| 확장 | 3-4건 | 현재 작업 흐름의 다음 단계, 더 나은 접근법, 다른 팀의 유사 사례 |
| 시야 | 0-2건 | 관심 분야 중 현재 작업과 **간접 연결**이 있는 자료. 연결 근거 필수 |
| 도전 | 1-2건 | 관심/전문 분야 **바깥**의 자료. 약점 보완 또는 이질적 관점 제공 |

**관심 분야 참고** (시야 층위에서만 사용):

MEMORY에서 사용자의 관심 분야 목록을 참조한다 (type: user 메모리 중 관심사/interests 관련 항목). 관심 분야를 이 파일에 하드코딩하지 않는다.

시야 층위 항목은 현재 작업 흐름과의 연결 근거를 반드시 1문장으로 명시한다.
연결이 억지스러우면 시야 항목 0건도 괜찮다 — 억지 추천보다 추천 안 하는 게 낫다.

**도전 층위 규칙**:

도전 층위는 comfort zone 바깥의 자료를 의도적으로 노출하여 사고의 폭을 넓힌다.

소싱 방법:
1. 현재 작업 흐름에서 **약한 고리**를 식별한다 — "이 작업을 잘하려면 필요하지만 내가 잘 모르는 분야"
2. 또는 현재 작업과 **전혀 다른 분야**에서 구조적으로 유사한 문제를 풀고 있는 사례를 찾는다

분야 예시 (관심 분야와 겹치지 않는 것):
- 통계/수학 이론 (실험 설계, 인과 추론, 베이즈 등)
- 인지과학/신경과학 (지각, 운동 제어, 학습 이론)
- 디자인/UX (정보 설계, 인터랙션 패턴)
- 시스템 이론/복잡계 (피드백 루프, 창발, 스케일링)
- 생물학/진화 (적응, 최적화, 로버스트니스)
- 역사/철학 (기술사, 과학 방법론)
- 순수 엔지니어링 (제어 이론, 신호 처리, 소재 역학)

각 항목에 **왜 이 분야가 지금 도움이 되는지** 1-2문장으로 명시한다. 단순 "시야 넓히기"가 아니라 구체적 전이 가능성을 설명한다.

예시 (좋은 도전 항목):
- 데이터 정제 작업 중 → 통계적 실험 설계 논문: "어떤 에피소드를 남길지의 판단이 사실상 sampling 문제이므로, stratified sampling 이론이 gold filtering 기준 설계에 전이 가능"
- 장갑 손 detection 작업 중 → 인지과학의 object recognition 논문: "사람이 장갑 낀 손을 인식하는 메커니즘(shape-from-contour)이 모델 아키텍처 선택의 힌트"

예시 (나쁜 도전 항목 — 금지):
- "시야를 넓히기 위해 추천합니다" ← 구체적 전이 설명 없음
- 해당 분야의 교과서적 입문 글 ← 깊이 없음

**선별 기준 (우선순위 순)**:
1. **비중복 (최우선)**: 2-5 D에서 수집한 제외 목록 (웹 읽을거리용)에 있는 URL/논문은 **무조건 제외**. 최근 3일 내 추천한 자료를 다시 추천하지 않는다. 동일 arXiv ID, 동일 도메인+경로도 중복으로 간주한다.
2. 구체성: "이 자료를 읽으면 오늘 태스크의 어떤 부분이 달라지는가?"에 답할 수 있어야 한다
3. 최신성: 최근 1주일 이내 우선. 단, 직결 참고자료는 시기 무관 (논문 원문 등)
4. 깊이: 일반론/개요/입문 글은 제외. 구체적 사례, 구현 디테일, 실험 결과가 있는 글 우선
5. 비중복(일반): 이미 알고 있을 법한 내용(태스크에서 직접 링크한 자료 등)은 제외

**Anti-pattern (금지)**:
- 관심 분야 키워드를 그대로 WebSearch에 넣지 않는다
- "이것도 관련 있을 수 있다" 수준의 느슨한 연결로 추천하지 않는다
- 모든 관심 분야에서 골고루 추천하려 하지 않는다 — 오늘 작업에 집중한다
- 일반론 글 (예: "What is JTBD?", "Introduction to Active Inference") 추천 금지
- **최근 3일 내 추천한 자료를 다시 추천하지 않는다** — 2-5 D의 제외 목록 반드시 확인

**읽을거리는 층위별로 heading 섹션**으로 구분한다. 각 층위의 heading 이름은 해당 층위의 내용을 대표하는 **영어 토픽/관점**으로 정한다 (예: "Data Quality & Curation", "Scaling Laws", "Pipeline Architecture" 등). 매일 내용에 따라 달라진다.

**각 항목 포맷**:
- 제목 (원문 링크)
- **내용 요약** (2-4문장): 논문/글의 핵심 로직과 흐름. 직접 열어보지 않아도 대략적인 접근법, 실험 설계, 핵심 결론을 파악할 수 있을 정도로 상세하게.
- **추천 이유** (1-2문장): 왜 지금 이 자료를 읽어야 하는지. 어떤 작업 흐름/태스크에서 어떤 부분이 달라지는지 구체적으로.
- 핵심 키워드 2-3개
- 관련 태스크가 있으면 끝에 `→ {태스크 제목}`

## Step 3: 데일리 노트 작성

수집한 정보를 아래 포맷으로 **파일에 직접 작성**한다.

파일 경로: `${VAULT}/Daily Notes/{오늘날짜}.md`

예: `Daily Notes/2026-03-19.md`

**주의**: 해당 날짜의 노트가 이미 존재하면, 기존 내용의 **맨 위에** 브리핑을 추가한다. 기존 태스크나 메모를 절대 삭제하지 않는다.

### 출력 포맷

아래 템플릿에서 `{변수}`를 실제 값으로 치환한다. 코드 변경이 없으면 "어제 코드" 섹션 전체를 생략한다.

````markdown
## ☀ Morning Briefing

### 어제 완료
```tasks
done on {어제날짜}
```

### 어제 코드

{코드 변경량 HTML 인라인 바 — 아래 "코드 변경량 렌더링 규칙" 참고}

{커밋 상세 HTML details — 아래 "커밋 상세 렌더링 규칙" 참고}

---

### 오늘 할 일
```tasks
not done
due before {내일날짜}
sort by due
```

### 다가오는 작업
```tasks
tags include #RLWRLD
tags do not include #claude-code
not done
sort by due
```

### 다가오는 작업 (Claude Code)
```tasks
tags include #claude-code
not done
sort by due
```

### Vault Curation

**Inbox** (미정리 {N}건 중, 최신순)

{5-8건. 최신 문서 우선, 작업 흐름 관련도 가중. 각 항목:}
{- **[[문서 제목]]** — 요약 1문장 (N줄). *작업/관심사 연결 맥락*}

**논문** (미학습 {N}건 중)

{4-6건. 작업 흐름 직결 우선. 각 항목:}
{- **[[arxiv-id-slug|논문 짧은 제목]]** — 요약 1문장. *연결 맥락*}

**잊혀진 것**

{2-3건. 30일 이상 방치된 inbox 항목, 오래된 순. 각 항목:}
{- **[[문서 제목]]** — 방치 기간. *관심사 연결*}

### 읽을거리

#### {English topic name for 직결 items, e.g. "Data Quality & Curation", "Calibration Methods"}
{4-6건. 각 항목: 제목+링크, 내용 요약 2-4문장, 추천 이유 1-2문장, 키워드, 관련 태스크}

#### {English topic name for 확장 items, e.g. "Scaling Laws & Data Strategy", "Pipeline Architecture"}
{3-4건. 동일 포맷}

#### {English topic name for 시야 items, e.g. "Broader Landscape"} (있을 때만)
{0-2건. 동일 포맷 + 연결 근거}

#### {English topic name for 도전 items, e.g. "Outside the Comfort Zone", "Cognitive Science Lens"}
{1-2건. 동일 포맷 + 전이 가능성 설명}

---

````

#### 코드 변경량 렌더링 규칙

2-3에서 수집한 변경량 통계를 **GitHub 스타일 HTML 인라인 바**로 렌더링한다.

**바 너비 계산**:
- 전체 저장소 중 가장 큰 insertions 값을 기준으로 `max_width = 150px`
- 각 저장소의 바 너비: `insertions / max_insertions * 150` (px), 최소 1px
- deletions도 동일 비율로 계산

**저장소 분류**:
- **실질 코드 저장소**: 일반적인 코드 변경. 볼드 이름 + 녹/적 바 표시
- **자동화/데이터 저장소**: sync, config, data/metadata 커밋이 대부분인 저장소 (예: DVC 메타데이터, 사용자 sync). `opacity:0.6`으로 흐리게 처리하고 바 생략. 이름 뒤에 용도를 간략 표기 (예: "sync/config", "data/metadata")
- 분류 기준: insertions과 deletions의 차이가 전체의 10% 미만이면 sync로 간주하거나, 커밋 메시지에 sync/chore가 대부분이면 자동화로 분류

**HTML 템플릿**:

```html
<div style="margin:12px 0">
<!-- 실질 코드 저장소 (insertions 내림차순 정렬) -->
<div style="display:flex;align-items:center;gap:6px;margin:6px 0;font-family:monospace">
  <span style="width:110px;font-size:0.85em;text-align:right"><b>{repo_name}</b></span>
  <span style="background:#3fb950;height:12px;width:{ins_width}px;display:inline-block;border-radius:2px"></span><span style="background:#f85149;height:12px;width:{del_width}px;display:inline-block;border-radius:2px"></span>
  <span style="font-size:0.8em;color:#8b949e">+{insertions} −{deletions} ({N} commits)</span>
</div>
<!-- 자동화/데이터 저장소 -->
<div style="display:flex;align-items:center;gap:6px;margin:6px 0;font-family:monospace;opacity:0.6">
  <span style="width:110px;font-size:0.85em;text-align:right">{repo_name}</span>
  <span style="font-size:0.8em;color:#8b949e">+{insertions} −{deletions} ({N} commits) — {용도}</span>
</div>
</div>
```

#### 커밋 상세 렌더링 규칙

커밋 상세는 `<details>` 접기로 기본 숨김 처리한다. **내부는 반드시 순수 HTML**로 작성한다 (Obsidian이 `<details>` 안의 마크다운을 렌더링하지 않음).

```html
<details>
<summary>커밋 상세</summary>
<ul>
<li><b>{repo_name}</b> — {1줄 요약}
  <ul>
  <li>{commit_hash} {commit_message}</li>
  <li>{commit_hash} {commit_message}</li>
  </ul>
</li>
<li><b>{repo_name}</b> — {1줄 요약}
  <ul>
  <li>{commit_hash} {commit_message}</li>
  </ul>
</li>
</ul>
</details>
```

**상세 렌더링 규칙**:
- 각 저장소는 `<li><b>이름</b> — 1줄 요약</li>` 형태
- 1줄 요약은 커밋들의 공통 주제를 간결하게 (예: "catalog archive service, lineage 방어")
- 동일 패턴의 반복 커밋은 묶어서 표기 (예: "d32cade4 외 2건 chore: sync users")
- 리스트는 `<ul>`, `<li>`, `<b>` 등 HTML 태그만 사용

### 포맷 규칙

- 한국어로 작성, 기술 용어는 영어 유지
- 간결하게 — 전체 브리핑이 스크롤 없이 읽힐 수 있도록
- 이모지 사용은 섹션 제목의 ☀만 허용
- 태스크 섹션은 Obsidian Tasks plugin query block을 사용한다 (raw task 복사 금지 — 중복 방지)
- query의 날짜는 `{어제날짜}`, `{내일날짜}` 자리에 실제 날짜(YYYY-MM-DD)를 넣는다
- 읽을거리의 외부 링크는 `[텍스트](URL)` 형식

## Step 4: 완료 보고

사용자에게 브리핑 요약을 터미널에 출력한다:
- 완료 태스크 N건
- 오늘 할 일 N건
- 코드 변경 N개 저장소
- 볼트 큐레이션 N건 (Inbox N + 논문 N + 잊혀진 것 N)
- 읽을거리 N건 (직결 N + 확장 N + 시야 N), 섹션명 나열
- 파일 경로 안내
