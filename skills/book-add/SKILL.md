---
description: "책을 옵시디언 독서 목록에 추가한다. 교보문고에서 책 정보와 표지를 검색하여 구조화된 노트를 생성."
allowed-tools: Bash, Write, Edit, Read, Glob, Grep, WebFetch, WebSearch
---

# brain:book-add — 책 → 옵시디언 독서 목록 추가

## 전제 조건

이 스킬 실행 전 `${CLAUDE_PLUGIN_ROOT}/config.md`를 읽어 VAULT, WORKSPACES 경로를 확인한다.

책 제목(또는 검색어)을 받아 교보문고에서 정보를 검색하고, 옵시디언 독서 목록에 노트를 생성한다.

## 입력

사용자가 `/brain:book-add <책 제목>` 형태로 호출.
예: `/brain:book-add 총균쇠`

인자가 없으면 사용자에게 책 제목을 물어본다.

---

## Step 1: 책 정보 검색

WebSearch로 교보문고에서 책을 검색한다.

```
WebSearch: "교보문고 {책 제목}"
```

검색 결과에서 교보문고 상품 페이지 URL을 찾는다.
URL 패턴: `https://product.kyobobook.co.kr/detail/{ISBN}`

---

## Step 2: 교보문고 상품 페이지에서 메타데이터 추출

WebFetch로 교보문고 상품 페이지를 가져와 다음 정보를 추출한다:

- **제목**: 책 제목 (부제 포함 시 분리)
- **저자**: 저자명 (여러 명일 수 있음)
- **출판일**: 출간일
- **ISBN**: 13자리 ISBN
- **표지 이미지 URL**: 교보문고 커버 이미지
- **설명**: 책 소개 한줄 요약 (직접 작성)

표지 이미지 URL 패턴:
```
https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/{ISBN}.jpg
```

ISBN을 추출했으면 위 패턴으로 cover URL을 구성한다.

---

## Step 3: 사용자 확인

추출한 정보를 사용자에게 보여주고 확인을 받는다:

```
📚 책 정보 확인

제목: {제목}
저자: {저자}
출간일: {출판일}
ISBN: {ISBN}
표지: {cover URL}

이 정보로 독서 노트를 생성할까요?
```

사용자가 수정을 요청하면 반영한다.

---

## Step 4: 옵시디언 노트 생성

확인 후 노트를 생성한다.

**파일 경로**:
```
${VAULT}/2. Areas/Life - 독서하기/{제목}.md
```

**노트 내용**:
```markdown
---
description: {한줄 설명 — 부제 또는 핵심 내용 요약}
tags:
  - 독서
review_status:
  - 1. 독서 예정
cover: https://contents.kyobobook.co.kr/sih/fit-in/458x0/pdt/{ISBN}.jpg
author:
  - {저자1}
  - {저자2 (있으면)}
published: {출간일 YYYY-MM-DD}
review_started:
review_ended:
---
```

**주의사항**:
- 본문은 비워둔다 (나중에 독서 메모 작성용)
- `review_status`는 항상 `1. 독서 예정`으로 시작
- `review_started`, `review_ended`는 빈 값으로 둔다
- 동일 제목의 파일이 이미 있으면 사용자에게 알리고 중단

---

## Step 5: 완료 메시지

```
📖 독서 노트 생성 완료!

파일: {파일 경로}
상태: 1. 독서 예정

독서를 시작하면 review_status를 "2. 독서 중"으로 변경하세요.
```

---

## 여러 권 동시 추가

사용자가 여러 책을 쉼표나 줄바꿈으로 나열하면, 각 책에 대해 Step 1-4를 반복한다.
단, 검색은 병렬로 수행하고 확인은 한 번에 모아서 받는다.
