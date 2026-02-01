# PARA Memory System

Organized per Tiago Forte's PARA framework, extended for AI agent memory.

## Structure

```
para/
├── projects/          # Active work with goals/deadlines
├── areas/             # Ongoing responsibilities (no end date)
│   ├── people/        # People I interact with
│   └── companies/     # Companies/organizations
├── resources/         # Topics of interest
└── archives/          # Inactive items
```

## Entity Schema

Each entity gets two files:
- `summary.md` - Quick overview for context
- `facts.json` - Atomic facts with metadata

## Fact Schema

```json
{
  "id": "entity-001",
  "fact": "Description of the fact",
  "category": "relationship|milestone|status|preference|context",
  "created": "2026-01-31",
  "status": "active",
  "supersededBy": null,
  "accessCount": 0,
  "lastAccessed": "2026-01-31",
  "relatedEntities": ["areas/people/alice", "projects/my-project"],
  "source": {
    "type": "conversation|file|manual",
    "timestamp": "2026-01-31T14:30:00",
    "channel": "discord"
  }
}
```

## Fact Categories

| Category | Use For |
|----------|---------|
| `relationship` | How entities relate to each other |
| `milestone` | Significant events or achievements |
| `status` | Current state or situation |
| `preference` | Likes, dislikes, work style |
| `context` | Background information |

## Fact Status

| Status | Meaning |
|--------|---------|
| `active` | Current, valid fact |
| `superseded` | Replaced by newer fact |

## Memory Decay

Facts are tiered based on access patterns:

| Tier | Days Since Access | In Summary? |
|------|------------------|-------------|
| 🔥 Hot | 0-7 days | ✓ Prominent |
| 🌡️ Warm | 8-30 days | ✓ Lower priority |
| ❄️ Cold | 31+ days | ✗ Only in facts.json |

**Frequency Resistance:** Facts accessed 10+ times stay Hot regardless of age.

## Usage

### Manual Checkpoint
```bash
python3 scripts/memory_checkpoint.py manual
```

### Update Summaries (Quick Decay)
```bash
python3 scripts/memory-decay.py --quick
```

### Full Decay Cycle
```bash
python3 scripts/memory-decay.py
```

## Example Entity

```
para/areas/people/alice/
├── summary.md    # Human-readable overview
└── facts.json    # Machine-readable facts
```

**summary.md:**
```markdown
# Alice

*Entity created: 2026-01-15*
*Last updated: 2026-01-31*

## 🔥 Hot (Recent/Frequent)
- 📎 **relationship**: Best friend since college
- 📌 **milestone**: Got promoted to lead engineer

## 🔗 Connected To
- areas/companies/acme-corp
```
