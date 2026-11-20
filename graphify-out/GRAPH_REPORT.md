# Graph Report - regulator-construction-sequence  (2026-11-20)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 48 nodes · 92 edges · 6 communities (2 shown, 4 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 51,506 input · 96 output

## Graph Freshness
- Built from commit: `67cb63c8`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Drawing Script Dependencies
- Regulator Model and Export
- Plan and Section Drawing
- Text Labels and Annotations
- MCP Tool Configuration

## God Nodes (most connected - your core abstractions)
1. `Regulator` - 22 edges
2. `_canvas()` - 5 edges
3. `_footer()` - 4 edges
4. `_seq()` - 4 edges
5. `_lin()` - 3 edges
6. `Params` - 2 edges
7. `_halo()` - 2 edges
8. `el()` - 2 edges
9. `npx` - 2 edges
10. `chrome-devtools` - 2 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (6 total, 4 thin omitted)

### Community 2 - "Plan and Section Drawing"
Cohesion: 0.29
Nodes (3): _footer(), _lin(), _seq()

### Community 5 - "MCP Tool Configuration"
Cohesion: 0.67
Nodes (3): npx, chrome-devtools, rea

## Knowledge Gaps
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Regulator` connect `Regulator Model and Export` to `Drawing Script Dependencies`, `Plan and Section Drawing`, `Elevation Slopes and Bands`, `Text Labels and Annotations`?**
  _High betweenness centrality (0.460) - this node is a cross-community bridge._
- **Why does `_canvas()` connect `Drawing Script Dependencies` to `Plan and Section Drawing`, `Elevation Slopes and Bands`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `_footer()` connect `Plan and Section Drawing` to `Drawing Script Dependencies`, `Elevation Slopes and Bands`?**
  _High betweenness centrality (0.009) - this node is a cross-community bridge._