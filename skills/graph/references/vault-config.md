# Vault Configuration

## 환경 설정

| 항목 | 값 |
|------|-----|
| CLI 경로 | `obsidian` |
| Vault 이름 | `My Second Brain` |
| Vault 경로 | {config.md의 VAULT 경로 참조} |
| 플랫폼 | Linux |

> CLI 호출 예시: `obsidian vault="My Second Brain" <command>`

---

## 제외 폴더

```json
[".obsidian/", ".trash/", "4. Archive/", "0. Inbox/", "5. Plugins/", ".venv/", "node_modules/"]
```

---

## 관계 필드

```json
["Up", "Source", "References"]
```

---

### Frontmatter 필드 매핑 (FRONTMATTER_MAPPING)

```json
{ "domain": "tags", "source": "created-by", "noteType": "type" }
```

---

## 폴더 구조

| 폴더 | 용도 |
|------|------|
| 1. Project | 진행 중인 프로젝트 |
| 2. Areas | 지속 관리 영역 |
| 3. Resources | 참고 자료 (논문, 레포 등) |
| 6. Thread | 주제별 지식 흐름 |

---

## Frontmatter Schema

| 필드 | 타입 | 설명 |
|------|------|------|
| tags | list | 주제 태그 |
| created-by | string | 생성 주체 (claude-code 등) |
| created-at | date | 생성일 |
| status | string | 문서 상태 (draft 등) |
