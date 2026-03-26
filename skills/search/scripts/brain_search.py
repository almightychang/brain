#!/usr/bin/env python3
"""brain:search — Grep + 벡터 검색으로 vault 노트 후보 수집.

Usage:
    python brain_search.py "검색 주제"
    python brain_search.py "검색 주제" --top 20
    python brain_search.py --rebuild-cache
"""

import argparse
import fnmatch
import json
import os
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import requests

# ── 설정 ──────────────────────────────────────────────

VAULT = Path.home() / "Documents" / "My Second Brain"
CACHE_PATH = Path(__file__).parent / "vault_embeddings.pkl"
CACHE_RETENTION_HOURS = 12
OLLAMA_URL = "http://localhost:11434/api/embed"
EMBED_MODEL = "bge-m3"
DEFAULT_TOP_K = 15

INCLUDE_PATTERNS = ["1. Project/**", "2. Areas/**", "3. Resources/**", "6. Thread/**"]
EXCLUDE_PATTERNS = ["4. Archive/**", "0. Inbox/**", "**/.obsidian/**", "**/.venv/**",
                    "**/node_modules/**", "**/.git/**"]



def _in_scope(rel_path: str) -> bool:
    for p in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_path, p): return False
    for p in INCLUDE_PATTERNS:
        if fnmatch.fnmatch(rel_path, p): return True
    return False


# ── 임베딩 캐시 ──────────────────────────────────────

def _embed_one(text: str) -> list[float]:
    r = requests.post(OLLAMA_URL, json={"model": EMBED_MODEL, "input": text[:2000]})
    return r.json()["embeddings"][0]


def _build_cache() -> dict:
    notes = []
    for md in VAULT.rglob("*.md"):
        rel = str(md.relative_to(VAULT))
        if not _in_scope(rel): continue
        try:
            content = md.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # frontmatter 제거
        text = content
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0: text = text[end + 3:]
        preview = text.strip()[:1500]
        notes.append({"title": md.stem, "path": rel, "text": f"{md.stem}\n{preview}"})

    print(f"임베딩 생성 중: {len(notes)}개 노트...", file=sys.stderr)
    embeddings = []
    for i, note in enumerate(notes):
        emb = _embed_one(note["text"])
        embeddings.append(emb)
        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(notes)}", file=sys.stderr)

    cache = {
        "notes": [{"title": n["title"], "path": n["path"]} for n in notes],
        "embeddings": np.array(embeddings),
        "built_at": time.time(),
    }
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)
    print(f"캐시 저장: {CACHE_PATH} ({os.path.getsize(CACHE_PATH) / 1024 / 1024:.1f}MB)", file=sys.stderr)
    return cache


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return _build_cache()

    age_hours = (time.time() - CACHE_PATH.stat().st_mtime) / 3600
    if age_hours > CACHE_RETENTION_HOURS:
        print(f"캐시 만료 ({age_hours:.1f}h > {CACHE_RETENTION_HOURS}h). 재생성...", file=sys.stderr)
        return _build_cache()

    with open(CACHE_PATH, "rb") as f:
        cache = pickle.load(f)
    return cache


# ── Grep 검색 ────────────────────────────────────────

def _extract_keywords(query: str) -> list[str]:
    """쿼리에서 검색 키워드 추출.
    쉼표로 분리된 것을 각각 하나의 키워드로 취급.
    한국어 조사 제거, 3자 미만 제거.
    """
    # 쉼표로 먼저 분리
    parts = re.split(r'[,，、]+', query)
    keywords = []
    # 한국어 조사 패턴
    josa = re.compile(r'(의|과|와|을|를|이|가|은|는|에|로|으로|에서|부터|까지|도|만|조차)$')
    for part in parts:
        part = part.strip()
        if not part: continue
        # 공백이 있는 구(phrase)는 통째로 키워드
        if ' ' in part:
            keywords.append(part)
            # 개별 단어도 추가 (3자 이상, 조사 제거)
            for word in part.split():
                word = josa.sub('', word).strip()
                if len(word) >= 3:
                    keywords.append(word)
        else:
            word = josa.sub('', part).strip()
            if len(word) >= 2:
                keywords.append(word)
    return list(dict.fromkeys(keywords))  # 순서 유지 중복 제거


def _grep_search(keywords: list[str], max_results: int = 30) -> list[dict]:
    """vault에서 키워드 grep 검색."""
    matched = {}
    for kw in keywords:
        try:
            result = subprocess.run(
                ["grep", "-r", "-l", "-i", "--include=*.md", kw, str(VAULT)],
                capture_output=True, text=True, timeout=10
            )
        except subprocess.TimeoutExpired:
            continue
        for line in result.stdout.strip().split("\n"):
            if not line: continue
            path = Path(line)
            try:
                rel = str(path.relative_to(VAULT))
            except ValueError:
                continue
            if not _in_scope(rel): continue
            if rel not in matched:
                matched[rel] = {"title": path.stem, "path": rel, "grep_hits": 0}
            matched[rel]["grep_hits"] += 1

    # grep_hits 기준 정렬 (더 많은 키워드 매칭 = 상위)
    results = sorted(matched.values(), key=lambda x: x["grep_hits"], reverse=True)
    return results[:max_results]


# ── 벡터 검색 ────────────────────────────────────────

def _vector_search(query: str, cache: dict, top_k: int = 15) -> list[dict]:
    q_emb = np.array(_embed_one(query))
    embeddings = cache["embeddings"]
    notes = cache["notes"]

    sims = embeddings @ q_emb / (np.linalg.norm(embeddings, axis=1) * np.linalg.norm(q_emb))
    top_idx = np.argsort(sims)[::-1][:top_k]

    results = []
    for i in top_idx:
        results.append({
            "title": notes[i]["title"],
            "path": notes[i]["path"],
            "score": round(float(sims[i]), 3),
        })
    return results


# ── 합산 ─────────────────────────────────────────────

def _merge(grep_results: list[dict], vector_results: list[dict]) -> list[dict]:
    merged = {}

    for r in grep_results:
        merged[r["path"]] = {
            "title": r["title"],
            "path": r["path"],
            "source": "grep",
            "score": None,
            "grep_hits": r.get("grep_hits", 1),
        }

    for r in vector_results:
        if r["path"] in merged:
            merged[r["path"]]["source"] = "both"
            merged[r["path"]]["score"] = r["score"]
        else:
            merged[r["path"]] = {
                "title": r["title"],
                "path": r["path"],
                "source": "vector",
                "score": r["score"],
                "grep_hits": 0,
            }

    # 정렬: both > grep(hits순) > vector(score순)
    def sort_key(item):
        source_order = {"both": 0, "grep": 1, "vector": 2}
        return (source_order.get(item["source"], 3), -item.get("grep_hits", 0), -(item.get("score") or 0))

    return sorted(merged.values(), key=sort_key)


# ── Main ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="brain:search — Grep + Vector vault search")
    parser.add_argument("query", nargs="?", help="검색 주제")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP_K, help="벡터 검색 상위 K개")
    parser.add_argument("--rebuild-cache", action="store_true", help="캐시 강제 재생성")
    args = parser.parse_args()

    if args.rebuild_cache:
        _build_cache()
        return

    if not args.query:
        print("Usage: python brain_search.py '검색 주제'", file=sys.stderr)
        sys.exit(1)

    # 캐시 로드
    cache = _load_cache()
    cache_age = (time.time() - CACHE_PATH.stat().st_mtime) / 3600
    cache_status = f"fresh ({cache_age:.1f}h)" if cache_age < CACHE_RETENTION_HOURS else "rebuilt"

    # 검색
    keywords = _extract_keywords(args.query)
    grep_results = _grep_search(keywords)
    vector_results = _vector_search(args.query, cache, top_k=args.top)
    merged = _merge(grep_results, vector_results)

    output = {
        "query": args.query,
        "keywords": keywords,
        "cache_status": cache_status,
        "grep_count": len(grep_results),
        "vector_count": len(vector_results),
        "merged_count": len(merged),
        "results": merged,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
