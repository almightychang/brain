---
name: text-to-pdf
description: "Markdown 파일을 깔끔한 PDF로 변환한다. 한글, 코드블록, 테이블 지원."
---

# Text to PDF

Markdown 파일을 깔끔한 A4 PDF로 변환한다.

## 트리거

`/brain:text-to-pdf <파일 경로>` 로 호출.

## 입력 처리

- 절대 경로 또는 상대 경로를 받는다.
- 출력 파일은 입력 파일과 같은 디렉토리에 `.pdf` 확장자로 생성.

## 실행 절차

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/text-to-pdf/convert.py "{input_path}"
```

`uv run`이 인라인 스크립트 메타데이터를 읽어 의존성을 자동으로 해결한다. 별도 설치 불필요.

## 원칙

- 원본 .md 파일은 수정하지 않는다.
- PDF 스타일 전처리(긴 구분선 축소 등)는 변환 시에만 적용.
- 출력 경로를 사용자에게 명확히 알려준다.

ARGUMENTS: $ARGUMENTS
