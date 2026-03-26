# Obsidian Vault Graph Query Templates

JavaScript query templates for structural analysis of an Obsidian vault's link graph.
All templates are IIFEs that run inside Obsidian's developer console and return JSON.

Common conventions:
- `{{EXCLUDED_FOLDERS}}` — JSON array of folder prefixes to skip (e.g. `["Templates/", ".trash/"]`)
- Data source: `app.metadataCache.resolvedLinks` (adjacency table of resolved wiki-links)
- All markdown files: `app.vault.getMarkdownFiles()`
- Output: `JSON.stringify({...})`

---

## 1. neighbors — N-hop neighbor exploration

**Parameters**: `{{NOTE_PATH}}` (string), `{{MAX_HOPS}}` (number, default 2), `{{EXCLUDED_FOLDERS}}` (array)

BFS from a starting note up to MAX_HOPS on the undirected link graph.
Returns results grouped by hop level, with each node's degree. Max 50 notes per hop (sorted by degree descending).

```javascript
(() => {
  const NOTE_PATH = {{NOTE_PATH}};
  const MAX_HOPS = {{MAX_HOPS}};
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const adjSet = {};
  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    if (!adjSet[src]) adjSet[src] = new Set();
    for (const tgt of Object.keys(targets)) {
      if (isExcluded(tgt)) continue;
      if (!adjSet[tgt]) adjSet[tgt] = new Set();
      adjSet[src].add(tgt);
      adjSet[tgt].add(src);
    }
  }

  if (!adjSet[NOTE_PATH]) {
    return JSON.stringify({ startNote: NOTE_PATH, maxHops: MAX_HOPS, hops: [], totalFound: 0, error: 'Note not found in graph' });
  }

  const visited = new Set([NOTE_PATH]);
  let frontier = [NOTE_PATH];
  const hops = [];
  let totalFound = 0;

  for (let hop = 1; hop <= MAX_HOPS; hop++) {
    const nextFrontier = [];
    const hopNotes = [];

    for (const node of frontier) {
      for (const nb of (adjSet[node] || [])) {
        if (visited.has(nb)) continue;
        visited.add(nb);
        nextFrontier.push(nb);
        hopNotes.push({ note: nb, degree: (adjSet[nb] || new Set()).size });
      }
    }

    hopNotes.sort((a, b) => b.degree - a.degree);
    totalFound += hopNotes.length;
    hops.push({ hop: hop, notes: hopNotes.slice(0, 50) });
    frontier = nextFrontier;
    if (frontier.length === 0) break;
  }

  return JSON.stringify({ startNote: NOTE_PATH, maxHops: MAX_HOPS, hops: hops, totalFound: totalFound });
})()
```

**Output description**:
- `startNote` — the path of the origin note
- `maxHops` — the requested hop limit
- `hops` — array of `{hop, notes: [{note, degree}]}` per level
- `totalFound` — total unique notes discovered across all hops

---

## 2. path — Shortest path between two notes

**Parameters**: `{{FROM_PATH}}` (string), `{{TO_PATH}}` (string), `{{EXCLUDED_FOLDERS}}` (array)

BFS shortest path between two notes on the undirected graph.

```javascript
(() => {
  const FROM_PATH = {{FROM_PATH}};
  const TO_PATH = {{TO_PATH}};
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const adjSet = {};
  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    if (!adjSet[src]) adjSet[src] = new Set();
    for (const tgt of Object.keys(targets)) {
      if (isExcluded(tgt)) continue;
      if (!adjSet[tgt]) adjSet[tgt] = new Set();
      adjSet[src].add(tgt);
      adjSet[tgt].add(src);
    }
  }

  if (!adjSet[FROM_PATH] || !adjSet[TO_PATH]) {
    return JSON.stringify({ from: FROM_PATH, to: TO_PATH, path: [], hops: -1, found: false, error: 'One or both notes not found in graph' });
  }

  const visited = new Set([FROM_PATH]);
  const parent = {};
  parent[FROM_PATH] = null;
  const queue = [FROM_PATH];
  let qi = 0;
  let found = false;

  while (qi < queue.length) {
    const node = queue[qi++];
    if (node === TO_PATH) { found = true; break; }
    for (const nb of (adjSet[node] || [])) {
      if (visited.has(nb)) continue;
      visited.add(nb);
      parent[nb] = node;
      queue.push(nb);
    }
  }

  if (!found) {
    return JSON.stringify({ from: FROM_PATH, to: TO_PATH, path: [], hops: -1, found: false });
  }

  const path = [];
  let cur = TO_PATH;
  while (cur !== null) {
    path.unshift(cur);
    cur = parent[cur];
  }

  return JSON.stringify({ from: FROM_PATH, to: TO_PATH, path: path, hops: path.length - 1, found: true });
})()
```

**Output description**:
- `from`, `to` — the start and end note paths
- `path` — ordered array of note paths from source to destination
- `hops` — number of edges traversed (-1 if not found)
- `found` — boolean indicating whether a path exists

---

## 3. cluster — Connected component from a starting note

**Parameters**: `{{NOTE_PATH}}` (string), `{{EXCLUDED_FOLDERS}}` (array)

BFS to find all reachable notes from the starting note. Groups results by top-level folder.
If totalReachable exceeds 500, the `notes` array is omitted and only `byFolder` is returned.

```javascript
(() => {
  const NOTE_PATH = {{NOTE_PATH}};
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const adjSet = {};
  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    if (!adjSet[src]) adjSet[src] = new Set();
    for (const tgt of Object.keys(targets)) {
      if (isExcluded(tgt)) continue;
      if (!adjSet[tgt]) adjSet[tgt] = new Set();
      adjSet[src].add(tgt);
      adjSet[tgt].add(src);
    }
  }

  if (!adjSet[NOTE_PATH]) {
    return JSON.stringify({ startNote: NOTE_PATH, totalReachable: 0, byFolder: {}, notes: [], error: 'Note not found in graph' });
  }

  const visited = new Set([NOTE_PATH]);
  const queue = [NOTE_PATH];
  let qi = 0;

  while (qi < queue.length) {
    const node = queue[qi++];
    for (const nb of (adjSet[node] || [])) {
      if (visited.has(nb)) continue;
      visited.add(nb);
      queue.push(nb);
    }
  }

  const reachable = [...visited];
  const totalReachable = reachable.length;

  const byFolder = {};
  for (const p of reachable) {
    const folder = p.includes('/') ? p.substring(0, p.indexOf('/')) : '(root)';
    byFolder[folder] = (byFolder[folder] || 0) + 1;
  }

  const result = { startNote: NOTE_PATH, totalReachable: totalReachable, byFolder: byFolder };
  if (totalReachable <= 500) {
    result.notes = reachable;
  }

  return JSON.stringify(result);
})()
```

**Output description**:
- `startNote` — the origin note path
- `totalReachable` — number of notes reachable from the start
- `byFolder` — object mapping top-level folder names to note counts
- `notes` — array of all reachable note paths (omitted when totalReachable > 500)

---

## 4. bridges — Bridge edges and articulation points (Iterative Tarjan)

**Parameters**: none (full vault scan), `{{EXCLUDED_FOLDERS}}` (array)

Finds bridge edges (whose removal disconnects the graph) and articulation points using an iterative implementation of Tarjan's algorithm. This avoids recursion stack overflow on large vaults.

```javascript
(() => {
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const adjSet = {};
  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    if (!adjSet[src]) adjSet[src] = new Set();
    for (const tgt of Object.keys(targets)) {
      if (isExcluded(tgt)) continue;
      if (!adjSet[tgt]) adjSet[tgt] = new Set();
      adjSet[src].add(tgt);
      adjSet[tgt].add(src);
    }
  }

  const nodes = Object.keys(adjSet);
  const adjArr = {};
  for (const n of nodes) {
    adjArr[n] = [...adjSet[n]];
  }

  const disc = {};
  const low = {};
  let timer = 0;
  const bridges = [];
  const artPoints = new Set();

  for (const start of nodes) {
    if (disc[start] !== undefined) continue;

    disc[start] = low[start] = timer++;
    const stack = [[start, null, 0, 0]];

    while (stack.length > 0) {
      const frame = stack[stack.length - 1];
      const node = frame[0];
      const parent = frame[1];
      const neighbors = adjArr[node] || [];

      if (frame[2] < neighbors.length) {
        const nb = neighbors[frame[2]];
        frame[2]++;

        if (disc[nb] === undefined) {
          disc[nb] = low[nb] = timer++;
          frame[3]++;
          stack.push([nb, node, 0, 0]);
        } else if (nb !== parent) {
          low[node] = Math.min(low[node], disc[nb]);
        }
      } else {
        stack.pop();
        if (parent !== null) {
          low[parent] = Math.min(low[parent], low[node]);

          if (low[node] > disc[parent]) {
            bridges.push([parent, node]);
          }

          if (low[node] >= disc[parent]) {
            artPoints.add(parent);
          }
        } else {
          if (frame[3] > 1) {
            artPoints.add(node);
          }
        }
      }
    }
  }

  const apSorted = [...artPoints].map(n => ({
    note: n,
    degree: (adjArr[n] || []).length
  })).sort((a, b) => b.degree - a.degree);

  const bridgesByFolder = {};
  for (const [a, b] of bridges) {
    const fa = a.includes('/') ? a.substring(0, a.indexOf('/')) : '(root)';
    const fb = b.includes('/') ? b.substring(0, b.indexOf('/')) : '(root)';
    bridgesByFolder[fa] = (bridgesByFolder[fa] || 0) + 1;
    if (fa !== fb) bridgesByFolder[fb] = (bridgesByFolder[fb] || 0) + 1;
  }

  return JSON.stringify({
    bridgeEdges: bridges.slice(0, 50),
    totalBridges: bridges.length,
    bridgesByFolder: bridgesByFolder,
    articulationPoints: apSorted.slice(0, 30),
    totalArticulationPoints: artPoints.size,
    totalNodes: nodes.length
  });
})()
```

**Output description**:
- `bridgeEdges` — up to 50 bridge edges as `[nodeA, nodeB]` pairs
- `totalBridges` — total number of bridge edges found
- `bridgesByFolder` — bridge counts grouped by top-level folder
- `articulationPoints` — up to 30 articulation points as `{note, degree}`, sorted by degree descending
- `totalArticulationPoints` — total number of articulation points
- `totalNodes` — number of nodes in the graph

---

## 5. hubs — Top N nodes by degree

**Parameters**: `{{TOP_N}}` (number, default 20), `{{FOLDER_FILTER}}` (string, default ''), `{{EXCLUDED_FOLDERS}}` (array)

Builds directed degree maps (inDegree, outDegree) from resolvedLinks. If FOLDER_FILTER is non-empty, only includes notes whose path starts with that prefix. Sorts by total degree (in + out) descending.

```javascript
(() => {
  const TOP_N = {{TOP_N}};
  const FOLDER_FILTER = {{FOLDER_FILTER}};
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const inDeg = {};
  const outDeg = {};

  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    const tgts = Object.keys(targets).filter(t => !isExcluded(t));
    outDeg[src] = (outDeg[src] || 0) + tgts.length;
    for (const tgt of tgts) {
      inDeg[tgt] = (inDeg[tgt] || 0) + 1;
    }
  }

  const allFiles = app.vault.getMarkdownFiles().filter(f => !isExcluded(f.path));
  const filtered = FOLDER_FILTER
    ? allFiles.filter(f => f.path.startsWith(FOLDER_FILTER))
    : allFiles;

  const totalNodes = filtered.length;

  const hubs = filtered.map(f => ({
    note: f.path,
    inDegree: inDeg[f.path] || 0,
    outDegree: outDeg[f.path] || 0,
    total: (inDeg[f.path] || 0) + (outDeg[f.path] || 0)
  }));

  hubs.sort((a, b) => b.total - a.total);

  return JSON.stringify({
    hubs: hubs.slice(0, TOP_N),
    topN: TOP_N,
    totalNodes: totalNodes,
    folderFilter: FOLDER_FILTER
  });
})()
```

**Output description**:
- `hubs` — array of `{note, inDegree, outDegree, total}` sorted by total degree descending
- `topN` — the requested limit
- `totalNodes` — number of notes considered (after folder filter)
- `folderFilter` — the folder prefix filter applied (empty string if none)

---

## 6. orphans-rich — Orphan notes with frontmatter

**Parameters**: `{{FOLDER_FILTER}}` (string, default ''), `{{EXCLUDED_FOLDERS}}` (array)

Finds notes with 0 inDegree AND 0 outDegree. For each orphan, extracts frontmatter metadata (tags, created date, type) via `app.metadataCache.getFileCache()`. Sorted by modification date descending. Max 100 orphans returned.

```javascript
(() => {
  const FOLDER_FILTER = {{FOLDER_FILTER}};
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const outDeg = {};
  const inDeg = {};

  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    const tgts = Object.keys(targets).filter(t => !isExcluded(t));
    outDeg[src] = (outDeg[src] || 0) + tgts.length;
    for (const tgt of tgts) {
      inDeg[tgt] = (inDeg[tgt] || 0) + 1;
    }
  }

  const allFiles = app.vault.getMarkdownFiles().filter(f => !isExcluded(f.path));
  const filtered = FOLDER_FILTER
    ? allFiles.filter(f => f.path.startsWith(FOLDER_FILTER))
    : allFiles;

  const totalNotes = filtered.length;

  const connectedNodes = new Set();
  for (const [n, d] of Object.entries(outDeg)) { if (d > 0) connectedNodes.add(n); }
  for (const [n, d] of Object.entries(inDeg)) { if (d > 0) connectedNodes.add(n); }

  const orphanFiles = filtered.filter(f => !connectedNodes.has(f.path));

  orphanFiles.sort((a, b) => b.stat.mtime - a.stat.mtime);

  const orphans = orphanFiles.slice(0, 100).map(f => {
    const cache = app.metadataCache.getFileCache(f);
    const fm = (cache && cache.frontmatter) ? cache.frontmatter : {};
    const tags = Array.isArray(fm.tags) ? fm.tags : (fm.tags ? [fm.tags] : []);
    return {
      note: f.path,
      mtime: f.stat.mtime,
      tags: tags,
      frontmatter: {
        created: fm.created || fm.date || null,
        type: fm.type || fm.noteType || null
      }
    };
  });

  return JSON.stringify({
    orphans: orphans,
    totalOrphans: orphanFiles.length,
    totalNotes: totalNotes,
    folderFilter: FOLDER_FILTER
  });
})()
```

**Output description**:
- `orphans` — array of `{note, mtime, tags: [], frontmatter: {created, type}}` sorted by mtime descending (max 100)
- `totalOrphans` — total orphan count (may exceed 100)
- `totalNotes` — total notes considered
- `folderFilter` — the folder prefix filter applied

---

## 7. frontmatter-relations — Extract relationship fields

**Parameters**: `{{NOTE_PATH}}` (string), `{{RELATIONSHIP_FIELDS}}` (array of field names), `{{EXCLUDED_FOLDERS}}` (array)

For the given note and its direct neighbors (1-hop), extracts the relationship fields specified in `{{RELATIONSHIP_FIELDS}}` from frontmatter. Also counts in/out links.

```javascript
(() => {
  const NOTE_PATH = {{NOTE_PATH}};
  const REL_FIELDS = {{RELATIONSHIP_FIELDS}};
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const outLinks = {};
  const inLinks = {};

  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    const tgts = Object.keys(targets).filter(t => !isExcluded(t));
    outLinks[src] = tgts;
    for (const tgt of tgts) {
      if (!inLinks[tgt]) inLinks[tgt] = [];
      inLinks[tgt].push(src);
    }
  }

  const outNbs = new Set(outLinks[NOTE_PATH] || []);
  const inNbs = new Set(inLinks[NOTE_PATH] || []);
  const allNbs = new Set([...outNbs, ...inNbs]);

  function extractRelations(path) {
    const file = app.vault.getAbstractFileByPath(path);
    if (!file) return [];
    const cache = app.metadataCache.getFileCache(file);
    if (!cache || !cache.frontmatter) return [];
    const fm = cache.frontmatter;
    const relations = [];
    for (const field of REL_FIELDS) {
      if (fm[field] !== undefined && fm[field] !== null) {
        let targets = fm[field];
        if (!Array.isArray(targets)) targets = [targets];
        targets = targets.map(t => String(t));
        relations.push({ field: field, targets: targets });
      }
    }
    return relations;
  }

  const noteRelations = extractRelations(NOTE_PATH);

  const neighbors = [];
  for (const nb of allNbs) {
    let direction = 'both';
    if (outNbs.has(nb) && !inNbs.has(nb)) direction = 'out';
    else if (!outNbs.has(nb) && inNbs.has(nb)) direction = 'in';
    neighbors.push({ note: nb, direction: direction });
  }

  neighbors.sort((a, b) => a.note.localeCompare(b.note));

  return JSON.stringify({
    note: NOTE_PATH,
    relations: noteRelations,
    neighbors: neighbors,
    inDegree: inNbs.size,
    outDegree: outNbs.size
  });
})()
```

**Output description**:
- `note` — the queried note path
- `relations` — array of `{field, targets: [notePath]}` for each relationship field found in frontmatter
- `neighbors` — array of `{note, direction}` where direction is `"in"`, `"out"`, or `"both"`
- `inDegree` — number of notes linking to this note
- `outDegree` — number of notes this note links to

---

## 8. vault-stats — Full vault statistics

**Parameters**: none (full vault scan), `{{EXCLUDED_FOLDERS}}` (array)

Comprehensive vault-wide statistics: note counts, link density, orphan ratio, connected components, folder breakdown, cross-folder link ratio, and monthly creation timeline.

```javascript
(() => {
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const outDeg = {};
  const inDeg = {};
  const adjSet = {};
  let edgeCount = 0;

  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    if (!adjSet[src]) adjSet[src] = new Set();
    const tgts = Object.keys(targets).filter(t => !isExcluded(t));
    outDeg[src] = (outDeg[src] || 0) + tgts.length;
    edgeCount += tgts.length;
    for (const tgt of tgts) {
      inDeg[tgt] = (inDeg[tgt] || 0) + 1;
      if (!adjSet[tgt]) adjSet[tgt] = new Set();
      adjSet[src].add(tgt);
      adjSet[tgt].add(src);
    }
  }

  const allFiles = app.vault.getMarkdownFiles().filter(f => !isExcluded(f.path));
  const totalNotes = allFiles.length;

  const connectedNodes = new Set();
  for (const [n, d] of Object.entries(outDeg)) { if (d > 0) connectedNodes.add(n); }
  for (const [n, d] of Object.entries(inDeg)) { if (d > 0) connectedNodes.add(n); }
  const orphanPaths = new Set();
  for (const f of allFiles) {
    if (!connectedNodes.has(f.path)) orphanPaths.add(f.path);
  }
  const orphanCount = orphanPaths.size;

  const visited = new Set();
  const componentSizes = [];

  for (const f of allFiles) {
    if (visited.has(f.path)) continue;
    let size = 0;
    const queue = [f.path];
    visited.add(f.path);
    let qi = 0;
    while (qi < queue.length) {
      const node = queue[qi++];
      size++;
      for (const nb of (adjSet[node] || [])) {
        if (!visited.has(nb)) {
          visited.add(nb);
          queue.push(nb);
        }
      }
    }
    componentSizes.push(size);
  }

  componentSizes.sort((a, b) => b - a);
  const componentCount = componentSizes.length;
  const largestComponent = componentSizes[0] || 0;
  const largestComponentRatio = totalNotes > 0
    ? Math.round(largestComponent / totalNotes * 10000) / 10000
    : 0;

  const getFolder = p => p.includes('/') ? p.substring(0, p.lastIndexOf('/')) : '(root)';
  const folderStats = {};

  for (const f of allFiles) {
    const folder = getFolder(f.path);
    if (!folderStats[folder]) folderStats[folder] = { notes: 0, links: 0, orphans: 0 };
    folderStats[folder].notes++;
    folderStats[folder].links += (outDeg[f.path] || 0);
    if (orphanPaths.has(f.path)) folderStats[folder].orphans++;
  }

  let crossFolderLinks = 0;
  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    const srcFolder = getFolder(src);
    for (const tgt of Object.keys(targets)) {
      if (isExcluded(tgt)) continue;
      if (getFolder(tgt) !== srcFolder) crossFolderLinks++;
    }
  }

  const monthlyCreation = {};
  for (const f of allFiles) {
    const d = new Date(f.stat.ctime);
    const key = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
    monthlyCreation[key] = (monthlyCreation[key] || 0) + 1;
  }
  const monthlySorted = {};
  for (const k of Object.keys(monthlyCreation).sort()) {
    monthlySorted[k] = monthlyCreation[k];
  }

  const outOnlyNotes = [];
  for (const f of allFiles) {
    if ((outDeg[f.path] || 0) > 0 && (inDeg[f.path] || 0) === 0) {
      outOnlyNotes.push(f.path);
    }
  }

  return JSON.stringify({
    totalNotes: totalNotes,
    totalLinks: edgeCount,
    avgLinksPerNote: Math.round(edgeCount / Math.max(totalNotes, 1) * 100) / 100,
    orphanCount: orphanCount,
    orphanRatio: Math.round(orphanCount / Math.max(totalNotes, 1) * 10000) / 10000,
    componentCount: componentCount,
    largestComponent: largestComponent,
    largestComponentRatio: largestComponentRatio,
    componentSizes: componentSizes.slice(0, 20),
    folderStats: folderStats,
    crossFolderLinks: crossFolderLinks,
    crossFolderRatio: Math.round(crossFolderLinks / Math.max(edgeCount, 1) * 10000) / 10000,
    monthlyCreation: monthlySorted,
    outOnlyCount: outOnlyNotes.length,
    outOnlyNotes: outOnlyNotes.slice(0, 50)
  });
})()
```

**Output description**:
- `totalNotes` — total markdown files in the vault
- `totalLinks` — total directed edges (outgoing links)
- `avgLinksPerNote` — average outgoing links per note
- `orphanCount` / `orphanRatio` — notes with zero connections
- `componentCount` — number of connected components
- `largestComponent` / `largestComponentRatio` — size and ratio of the biggest component
- `componentSizes` — sizes of up to 20 largest components
- `folderStats` — per-folder breakdown of `{notes, links, orphans}`
- `crossFolderLinks` / `crossFolderRatio` — links spanning different folders
- `monthlyCreation` — note creation counts by YYYY-MM
- `outOnlyCount` / `outOnlyNotes` — notes that link out but receive no inbound links (up to 50)

---

## 9. suggest-links — Structural link suggestions (orphan rescue + missing links)

**Parameters**: `{{MAX_SUGGESTIONS}}` (number, default 30), `{{EXCLUDED_FOLDERS}}` (array), `{{RELATIONSHIP_FIELDS}}` (array), `{{FRONTMATTER_MAPPING}}` (object with keys: domain, source, noteType)

Two-pronged suggestion engine:
1. **Orphan rescue** — matches orphan notes to well-connected notes by frontmatter similarity (tags Jaccard, domain, source, note-type).
2. **Missing links** — finds pairs of notes that share 2+ common neighbors but are not directly linked (Jaccard similarity on neighbor sets).

```javascript
(() => {
  const MAX_SUGGESTIONS = {{MAX_SUGGESTIONS}};
  const EXCLUDED = {{EXCLUDED_FOLDERS}};
  const REL_FIELDS = {{RELATIONSHIP_FIELDS}};
  const FM = {{FRONTMATTER_MAPPING}};
  const isExcluded = p => !p.endsWith('.md') || EXCLUDED.some(e => p.startsWith(e));

  const rl = app.metadataCache.resolvedLinks;

  const outDeg = {};
  const inDeg = {};
  const adjSet = {};

  for (const [src, targets] of Object.entries(rl)) {
    if (isExcluded(src)) continue;
    if (!adjSet[src]) adjSet[src] = new Set();
    const tgts = Object.keys(targets).filter(t => !isExcluded(t));
    outDeg[src] = (outDeg[src] || 0) + tgts.length;
    for (const tgt of tgts) {
      inDeg[tgt] = (inDeg[tgt] || 0) + 1;
      if (!adjSet[tgt]) adjSet[tgt] = new Set();
      adjSet[src].add(tgt);
      adjSet[tgt].add(src);
    }
  }

  const allFiles = app.vault.getMarkdownFiles().filter(f => !isExcluded(f.path));
  const connectedNodes = new Set();
  for (const [n, d] of Object.entries(outDeg)) { if (d > 0) connectedNodes.add(n); }
  for (const [n, d] of Object.entries(inDeg)) { if (d > 0) connectedNodes.add(n); }

  const orphanPaths = [];
  const linkedPaths = [];
  for (const f of allFiles) {
    if (!connectedNodes.has(f.path)) orphanPaths.push(f.path);
    else linkedPaths.push(f.path);
  }

  function getFmProfile(path) {
    const file = app.vault.getAbstractFileByPath(path);
    if (!file) return null;
    const cache = app.metadataCache.getFileCache(file);
    if (!cache || !cache.frontmatter) return null;
    const fm = cache.frontmatter;
    const tags = Array.isArray(fm.tags) ? fm.tags : (fm.tags ? [fm.tags] : []);
    const getDomain = fm[FM.domain];
    const getSource = fm[FM.source];
    const getNoteType = fm[FM.noteType];
    return {
      tags: new Set(tags.map(t => String(t).toLowerCase())),
      domain: getDomain ? String(Array.isArray(getDomain) ? getDomain[0] : getDomain).toLowerCase() : '',
      source: getSource ? String(Array.isArray(getSource) ? getSource[0] : getSource) : '',
      noteType: getNoteType ? String(Array.isArray(getNoteType) ? getNoteType[0] : getNoteType).toLowerCase() : ''
    };
  }

  const ORPHAN_CAP = 50;
  const LINKED_CAP = 500;
  const orphanSuggestions = [];

  const orphanSlice = orphanPaths.slice(0, ORPHAN_CAP);
  const linkedSlice = linkedPaths.slice(0, LINKED_CAP);

  const linkedProfiles = [];
  for (const lp of linkedSlice) {
    const prof = getFmProfile(lp);
    if (prof) linkedProfiles.push({ path: lp, prof: prof });
  }

  for (const op of orphanSlice) {
    const oProf = getFmProfile(op);
    if (!oProf) continue;

    const candidates = [];
    for (const { path: lp, prof: lProf } of linkedProfiles) {
      let score = 0;
      const reasons = [];

      if (oProf.tags.size > 0 && lProf.tags.size > 0) {
        let inter = 0;
        for (const t of oProf.tags) { if (lProf.tags.has(t)) inter++; }
        if (inter > 0) {
          const union = new Set([...oProf.tags, ...lProf.tags]).size;
          const jaccard = inter / union;
          score += jaccard * 3;
          const shared = [];
          for (const t of oProf.tags) { if (lProf.tags.has(t)) shared.push(t); }
          reasons.push('tags: [' + shared.join(', ') + ']');
        }
      }

      if (oProf.domain && lProf.domain && oProf.domain === lProf.domain) {
        score += 2;
        reasons.push('domain: ' + oProf.domain);
      }

      if (oProf.source && lProf.source && oProf.source === lProf.source) {
        score += 2;
        reasons.push('source: ' + oProf.source);
      }

      if (oProf.noteType && lProf.noteType && oProf.noteType === lProf.noteType) {
        score += 1;
        reasons.push('note-type: ' + oProf.noteType);
      }

      if (score > 0) {
        candidates.push({ note: lp, score: Math.round(score * 100) / 100, reasons: reasons });
      }
    }

    candidates.sort((a, b) => b.score - a.score);
    if (candidates.length > 0) {
      orphanSuggestions.push({
        orphan: op,
        suggestions: candidates.slice(0, 3)
      });
    }
  }

  orphanSuggestions.sort((a, b) => b.suggestions[0].score - a.suggestions[0].score);

  const NODE_CAP = 500;
  const missingLinkSuggestions = [];

  const eligibleNodes = [];
  for (const n of Object.keys(adjSet)) {
    if ((adjSet[n] || new Set()).size >= 2) eligibleNodes.push(n);
  }
  const nodeSlice = eligibleNodes.slice(0, NODE_CAP);

  const seen = new Set();
  for (const node of nodeSlice) {
    const neighbors = adjSet[node];
    if (!neighbors) continue;
    const nbArr = [...neighbors];

    for (const nb of nbArr) {
      const nb2 = adjSet[nb];
      if (!nb2) continue;

      for (const hop2 of nb2) {
        if (hop2 === node) continue;
        if (neighbors.has(hop2)) continue;

        const pairKey = node < hop2 ? node + '|' + hop2 : hop2 + '|' + node;
        if (seen.has(pairKey)) continue;
        seen.add(pairKey);

        const nodeNb = adjSet[node] || new Set();
        const hop2Nb = adjSet[hop2] || new Set();
        let common = 0;
        for (const x of nodeNb) { if (hop2Nb.has(x)) common++; }

        if (common >= 2) {
          const union = new Set([...nodeNb, ...hop2Nb]).size;
          const jaccard = Math.round(common / union * 10000) / 10000;
          missingLinkSuggestions.push({
            noteA: node, noteB: hop2,
            commonNeighbors: common, jaccard: jaccard
          });
        }
      }
    }
  }

  missingLinkSuggestions.sort((a, b) => b.jaccard - a.jaccard || b.commonNeighbors - a.commonNeighbors);

  return JSON.stringify({
    orphanSuggestions: orphanSuggestions.slice(0, MAX_SUGGESTIONS),
    missingLinkSuggestions: missingLinkSuggestions.slice(0, MAX_SUGGESTIONS),
    totalOrphans: orphanPaths.length,
    scannedOrphans: Math.min(orphanPaths.length, ORPHAN_CAP),
    totalNodes: allFiles.length,
    scannedNodes: Math.min(eligibleNodes.length, NODE_CAP)
  });
})()
```

**Output description**:
- `orphanSuggestions` — array of `{orphan, suggestions: [{note, score, reasons}]}` — each orphan with up to 3 best candidate notes to link to
- `missingLinkSuggestions` — array of `{noteA, noteB, commonNeighbors, jaccard}` — pairs of notes that likely should be linked based on shared neighbors
- `totalOrphans` — total orphan count in the vault
- `scannedOrphans` — number of orphans actually evaluated (capped at 50)
- `totalNodes` — total notes in the vault
- `scannedNodes` — number of nodes scanned for missing links (capped at 500)
