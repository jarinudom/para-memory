# PARA Memory System for AI Agents

A structured, decaying memory system based on Tiago Forte's PARA method. Give your AI agent persistent memory that organizes facts by entity, tracks relationships, and naturally forgets less-important information over time.

## 🚀 Quick Start

```bash
# 1. Clone or copy to your workspace
cd ~/your-workspace
cp -r /path/to/para-memory ./skills/para-memory

# 2. Install requirements
brew install ollama        # For local LLM
ollama serve
ollama pull qwen2.5:7b     # Or llama3.2
clawdhub install qmd       # For search indexing

# 3. Run setup
./skills/para-memory/scripts/setup.sh

# 4. Test checkpoint (requires Ollama running)
python3 scripts/memory_checkpoint.py manual
```

## ⚠️ Requirements (Local/Offline)

This skill is designed for **local, private operation**:

| Tool | Purpose | Install |
|------|---------|---------|
| **Ollama** | Local LLM for fact extraction | `brew install ollama && ollama serve` |
| **QMD** | Search indexing (BM25 + vectors) | `clawdhub install qmd` |
| **Python + openai** | Script dependencies | `pip install openai` |

No external APIs, no cloud services, no data leaves your machine.

## 📖 What It Does

### The Problem
AI agents wake up with amnesia every session. They need external memory to maintain relationships, track projects, and remember preferences.

### The Solution
PARA Memory provides:

1. **Structured Storage** - Facts organized by entity type (people, companies, projects, resources)
2. **Atomic Facts** - Each piece of information is a discrete, trackable unit
3. **Natural Decay** - Old, unused facts fade from active summaries (but aren't deleted)
4. **Automatic Extraction** - LLM analyzes conversations and extracts durable facts

## 🏗️ Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Conversation   │ ──▶ │   Checkpoint     │ ──▶ │   PARA Store    │
│  (Daily Notes)  │     │   (LLM Extract)  │     │   (facts.json)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                         │
                                                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Agent Reads   │ ◀── │   Summary.md     │ ◀── │   Decay System  │
│   (Hot/Warm)    │     │   (Regenerated)  │     │   (Weekly)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Memory Tiers

| Tier | Emoji | Access Age | Behavior |
|------|-------|------------|----------|
| Hot | 🔥 | 0-7 days | Always in summary |
| Warm | 🌡️ | 8-30 days | In summary, lower priority |
| Cold | ❄️ | 31+ days | Omitted from summary, kept in facts.json |

**Frequency Resistance:** Facts accessed 10+ times stay Hot regardless of age.

## 📁 Directory Structure

After setup, your workspace will have:

```
workspace/
├── para/
│   ├── projects/           # Active work
│   ├── areas/
│   │   ├── people/         # People you interact with
│   │   └── companies/      # Organizations
│   ├── resources/          # Topics of interest
│   └── archives/           # Inactive items
├── memory/
│   └── YYYY-MM-DD.md       # Daily conversation logs
└── scripts/
    ├── memory_checkpoint.py
    └── memory-decay.py
```

## ⚙️ Configuration

Set these environment variables (or edit the scripts):

```bash
export PARA_WORKSPACE=/path/to/workspace
export PARA_OLLAMA_URL=http://localhost:11434/v1
export PARA_MODEL=qwen2.5:7b
```

## 🔧 Commands

### Checkpoint (Extract Facts)

```bash
# Run manually
python3 scripts/memory_checkpoint.py manual

# Cron (every 30 min)
*/30 * * * * cd /workspace && python3 scripts/memory_checkpoint.py cron
```

### Decay (Update Summaries)

```bash
# Quick update (just regenerate summaries)
python3 scripts/memory-decay.py --quick

# Full cycle (weekly)
python3 scripts/memory-decay.py
```

## 📝 Example Entity

**para/areas/people/alice/facts.json:**
```json
{
  "entity": "alice",
  "entity_type": "people", 
  "facts": [
    {
      "id": "ali-001",
      "fact": "Lead engineer at Acme Corp",
      "category": "context",
      "status": "active",
      "accessCount": 5,
      "lastAccessed": "2026-01-31",
      "relatedEntities": ["areas/companies/acme-corp"]
    }
  ]
}
```

**para/areas/people/alice/summary.md:**
```markdown
# Alice

## 🔥 Hot (Recent/Frequent)
- 📎 **context**: Lead engineer at Acme Corp

## 🔗 Connected To
- areas/companies/acme-corp
```

## 🔍 Troubleshooting

### "No recent context" error
- Ensure `memory/YYYY-MM-DD.md` exists with today's date
- The checkpoint script reads from daily notes

### LLM not responding
- Check Ollama is running: `ollama list`
- Test API: `curl http://localhost:11434/v1/models`

### Facts not appearing in summary
- Run decay: `python3 scripts/memory-decay.py --quick`
- Check `facts.json` has `status: "active"`

## 📚 Full Documentation

See [SKILL.md](./SKILL.md) for complete documentation including:
- All configuration options
- Entity schema details
- Integration guides
- Fact categories reference

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📄 License

MIT License - Use freely, attribution appreciated.
