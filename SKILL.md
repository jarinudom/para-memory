# PARA Memory Skill

**Name:** para-memory  
**Version:** 1.0.0  
**Author:** OpenClaw Community  
**License:** MIT

## Requirements

| Dependency | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.10+ | Script runtime |
| **openai** | 1.0+ | LLM API client (Ollama-compatible) |
| **Ollama** | Latest | Local LLM inference |
| **QMD** | Latest | BM25 + vector search indexing |

### Required LLM Models (pick one)

| Model | Size | Notes |
|-------|------|-------|
| `qwen2.5:7b` | ~4.4GB | Recommended, good JSON output |
| `llama3.2:8b` | ~4.7GB | Alternative, slightly slower |
| `mistral:7b` | ~4.1GB | Alternative |

### Required QMD Collections

The skill expects these QMD collections to be configured:

```yaml
# ~/.config/qmd/config.yaml
collections:
  memory:
    paths: ["~/workspace/memory"]
    extensions: [".md"]
  para:
    paths: ["~/workspace/para"]
    extensions: [".md"]
  para-facts:
    paths: ["~/workspace/para"]
    extensions: [".json"]
```

## Description

A structured memory system for AI agents based on Tiago Forte's PARA method (Projects, Areas, Resources, Archives). Provides persistent, decaying memory with atomic facts, entity relationships, and intelligent checkpointing.

## Features

- 📁 **PARA Structure** - Organized entity storage (projects, areas/people, areas/companies, resources)
- 🧠 **Atomic Facts** - Fine-grained facts with metadata (category, status, timestamps)
- 🔗 **Entity Relationships** - `relatedEntities` cross-references build a knowledge graph
- 🔄 **Supersession Chains** - `supersededBy` tracks fact history and updates
- 🔥 **Memory Decay** - Hot/Warm/Cold tiers based on access patterns
- 📈 **Frequency Resistance** - High-access facts resist decay
- 📊 **Access Tracking** - `accessCount` and `lastAccessed` for each fact
- 🤖 **LLM-Powered Checkpointing** - Automatic fact extraction from conversations
- 📝 **Daily Notes Integration** - Timeline entries for transient events
- 🔍 **QMD Integration** - Optional search indexing

## Installation

### Quick Install

```bash
cd /path/to/your/workspace
git clone <skill-repo> skills/para-memory
./skills/para-memory/scripts/setup.sh
```

### Manual Install

1. Copy `para/` template to your workspace root
2. Copy scripts to `scripts/` (or keep in skill folder)
3. Set up cron jobs (see Configuration)
4. Optional: Install `qmd` for search indexing

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PARA_WORKSPACE` | Current directory | Root workspace path |
| `PARA_MEMORY_DIR` | `$PARA_WORKSPACE/memory` | Daily notes directory |
| `PARA_DIR` | `$PARA_WORKSPACE/para` | PARA entities directory |
| `PARA_CACHE_DIR` | `~/.openclaw/memory-cache` | Cache for access logs |
| `PARA_OLLAMA_URL` | `http://localhost:11434/v1` | Ollama API URL |
| `PARA_MODEL` | `qwen2.5:7b` | LLM model for checkpointing |

### Decay Thresholds

| Tier | Days Since Access | Description |
|------|------------------|-------------|
| 🔥 Hot | 0-7 days | Prominent in summary |
| 🌡️ Warm | 8-30 days | Included, lower priority |
| ❄️ Cold | 31+ days | Omitted from summary, kept in facts.json |

**Frequency Resistance:** Facts with `accessCount >= 10` stay Hot regardless of recency.

### Cron Jobs

```bash
# Checkpoint every 30 minutes
*/30 * * * * cd /path/to/workspace && python3 scripts/memory_checkpoint.py cron

# Weekly decay cycle (Sundays 3am)
0 3 * * 0 cd /path/to/workspace && python3 scripts/memory-decay.py
```

## Usage

### Manual Checkpoint

```bash
python3 scripts/memory_checkpoint.py manual
```

### Quick Decay (Update Summaries)

```bash
python3 scripts/memory-decay.py --quick
```

### Full Decay Cycle

```bash
python3 scripts/memory-decay.py
```

## File Structure

```
workspace/
├── para/
│   ├── README.md
│   ├── projects/           # Active work with goals
│   │   └── my-project/
│   │       ├── summary.md
│   │       └── facts.json
│   ├── areas/
│   │   ├── people/         # People entities
│   │   │   └── alice/
│   │   │       ├── summary.md
│   │   │       └── facts.json
│   │   └── companies/      # Organization entities
│   ├── resources/          # Topics of interest
│   └── archives/           # Inactive items
├── memory/
│   ├── 2026-01-31.md       # Daily notes
│   └── ...
└── scripts/
    ├── memory_checkpoint.py
    └── memory-decay.py
```

## Entity Schema

### facts.json

```json
{
  "entity": "alice",
  "entity_type": "people",
  "created": "2026-01-31",
  "lastUpdated": "2026-01-31",
  "createdReason": "Direct relationship with user",
  "facts": [
    {
      "id": "ali-001",
      "fact": "Works at Acme Corp as lead engineer",
      "category": "context",
      "status": "active",
      "created": "2026-01-31",
      "lastAccessed": "2026-01-31",
      "accessCount": 3,
      "supersededBy": null,
      "relatedEntities": ["areas/companies/acme-corp"],
      "source": {
        "type": "conversation",
        "timestamp": "2026-01-31T14:30:00",
        "channel": "discord"
      }
    }
  ]
}
```

### Fact Categories

- `relationship` - How entities relate to each other
- `milestone` - Significant events or achievements
- `status` - Current state or situation
- `preference` - Likes, dislikes, work style
- `context` - Background information

### Fact Status

- `active` - Current, valid fact
- `superseded` - Replaced by newer fact (has `supersededBy` pointing to replacement)

## Integration

### With AGENTS.md

Add to your workspace's AGENTS.md:

```markdown
## Memory

- **PARA:** `para/**/*.json` — structured entities with atomic facts
- Run checkpoint: `python3 scripts/memory_checkpoint.py manual`
- Run decay: `python3 scripts/memory-decay.py --quick`
```

### With QMD Search

```bash
# Index PARA entities
qmd update -c para -c para-facts

# Search
qmd search "alice acme" -c para
```

### With Heartbeats

During heartbeat polls, optionally run:

```bash
python3 scripts/memory-decay.py --quick
```

---
name: para-memory
version: 1.0.0
description: Structured memory system for AI agents based on PARA method (Projects, Areas, Resources, Archives) with atomic facts, memory decay, and LLM-powered checkpointing.
metadata:
  clawdbot:
    emoji: "🧠"
    requires:
      plugins: []
      skills: []
      external:
        - qmd  # Local search indexing (BM25 + vectors)
        - ollama  # Local LLM for checkpoint extraction
    install:
      commands:
        - "ollama pull qwen2.5:7b"  # Or llama3.2
        - "clawdhub install qmd"
---

## Requirements (Hard Dependencies)

This skill requires **local, offline tools** for privacy and cost savings:

### Required: Local LLM (Ollama)
The checkpoint system uses an LLM to extract facts from conversations. It **must** be a local Ollama instance for privacy.

```bash
# Install Ollama
brew install ollama

# Start Ollama
ollama serve

# Pull a compatible model
ollama pull qwen2.5:7b
# or
ollama pull llama3.2
```

**Required environment variables:**
```bash
export PARA_OLLAMA_URL="http://localhost:11434/v1"
export PARA_MODEL="qwen2.5:7b"
```

### Required: QMD (Local Search)
For search indexing across your memory corpus. Install via ClawHub:

```bash
clawdhub install qmd
```

Or from source: https://github.com/openclaw/qmd

### Python Requirements
```bash
pip install openai  # Compatible with Ollama's API
```

## Troubleshooting

### Checkpoint Not Extracting Facts

1. Check LLM is running: `curl http://localhost:11434/v1/models`
2. Verify context exists in `memory/YYYY-MM-DD.md`
3. Run with verbose: `python3 scripts/memory_checkpoint.py manual 2>&1`

### Summaries Not Updating

1. Run decay: `python3 scripts/memory-decay.py --quick`
2. Check facts.json has `lastAccessed` fields

### Entity Not Created

Entities are created when:
- Mentioned 3+ times in conversation
- Direct relationship with user
- Significant project or milestone

## Changelog

### 1.0.0
- Initial release
- PARA structure with atomic facts
- Memory decay system
- LLM-powered checkpointing
- Entity cross-references
- Supersession chains
