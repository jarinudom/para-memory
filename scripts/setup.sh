#!/bin/bash
#
# PARA Memory Skill - Setup Script
# Installs the PARA memory system into your workspace
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   PARA Memory Skill - Setup          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""

# Determine workspace
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"

if [ -n "$PARA_WORKSPACE" ]; then
    WORKSPACE="$PARA_WORKSPACE"
elif [ -f "$PWD/AGENTS.md" ] || [ -f "$PWD/SOUL.md" ]; then
    WORKSPACE="$PWD"
else
    WORKSPACE="$PWD"
fi

echo -e "Workspace: ${YELLOW}$WORKSPACE${NC}"
echo ""

# Create directories
echo -e "${GREEN}Creating PARA directories...${NC}"
mkdir -p "$WORKSPACE/para/projects"
mkdir -p "$WORKSPACE/para/areas/people"
mkdir -p "$WORKSPACE/para/areas/companies"
mkdir -p "$WORKSPACE/para/resources"
mkdir -p "$WORKSPACE/para/archives"
mkdir -p "$WORKSPACE/memory"
mkdir -p "$WORKSPACE/scripts"

# Copy PARA README if not exists
if [ ! -f "$WORKSPACE/para/README.md" ]; then
    echo -e "${GREEN}Creating PARA README...${NC}"
    cat > "$WORKSPACE/para/README.md" << 'EOF'
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
  "timestamp": "2026-01-31",
  "status": "active",
  "supersededBy": null,
  "accessCount": 0,
  "lastAccessed": "2026-01-31"
}
```

## Memory Decay

- **Hot** (accessed < 7 days) - Prominent in summary
- **Warm** (accessed 8-30 days) - Included, lower priority  
- **Cold** (> 30 days) - Omitted from summary, still in facts

Accessing a cold fact "reheats" it.
EOF
fi

# Copy scripts to workspace (if desired)
read -p "Copy scripts to workspace/scripts/? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    echo -e "${GREEN}Copying scripts...${NC}"
    cp "$SKILL_DIR/scripts/memory_checkpoint.py" "$WORKSPACE/scripts/"
    cp "$SKILL_DIR/scripts/memory-decay.py" "$WORKSPACE/scripts/"
    chmod +x "$WORKSPACE/scripts/memory_checkpoint.py"
    chmod +x "$WORKSPACE/scripts/memory-decay.py"
    SCRIPTS_PATH="$WORKSPACE/scripts"
else
    SCRIPTS_PATH="$SKILL_DIR/scripts"
    chmod +x "$SKILL_DIR/scripts/memory_checkpoint.py"
    chmod +x "$SKILL_DIR/scripts/memory-decay.py"
fi

# Track missing requirements
MISSING_REQS=0

echo ""
echo -e "${GREEN}Checking required dependencies...${NC}"
echo ""

# Check for Python 3.10+
echo -e "${YELLOW}[1/4] Python 3.10+${NC}"
if command -v python3 &> /dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo $PY_VERSION | cut -d. -f1)
    PY_MINOR=$(echo $PY_VERSION | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
        echo -e "  ✓ Python $PY_VERSION found"
    else
        echo -e "  ${RED}✗ Python $PY_VERSION found, but 3.10+ required${NC}"
        MISSING_REQS=$((MISSING_REQS + 1))
    fi
else
    echo -e "  ${RED}✗ Python3 not found${NC}"
    echo -e "    Install: https://www.python.org/downloads/"
    MISSING_REQS=$((MISSING_REQS + 1))
fi

# Check for openai package
echo ""
echo -e "${YELLOW}[2/4] openai Python package${NC}"
if python3 -c "import openai" 2>/dev/null; then
    OPENAI_VERSION=$(python3 -c "import openai; print(openai.__version__)" 2>/dev/null || echo "unknown")
    echo -e "  ✓ openai package found (v$OPENAI_VERSION)"
else
    echo -e "  ${RED}✗ openai package not found${NC}"
    read -p "    Install openai package now? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        pip3 install openai
        if python3 -c "import openai" 2>/dev/null; then
            echo -e "  ✓ openai package installed"
        else
            echo -e "  ${RED}✗ Failed to install openai${NC}"
            MISSING_REQS=$((MISSING_REQS + 1))
        fi
    else
        MISSING_REQS=$((MISSING_REQS + 1))
    fi
fi

# Check for Ollama with compatible model
echo ""
echo -e "${YELLOW}[3/4] Ollama with LLM model${NC}"
if command -v ollama &> /dev/null; then
    echo -e "  ✓ Ollama CLI found"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/v1/models > /dev/null 2>&1; then
        echo -e "  ✓ Ollama API responding"
        
        # Check for compatible models
        MODELS=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}')
        COMPATIBLE_MODEL=""
        
        for model in qwen2.5:7b qwen2.5 llama3.2:8b llama3.2 mistral:7b mistral; do
            if echo "$MODELS" | grep -q "^$model"; then
                COMPATIBLE_MODEL="$model"
                break
            fi
        done
        
        if [ -n "$COMPATIBLE_MODEL" ]; then
            echo -e "  ✓ Compatible model found: ${GREEN}$COMPATIBLE_MODEL${NC}"
        else
            echo -e "  ${RED}✗ No compatible model found${NC}"
            echo -e "    Available models: $MODELS"
            echo -e "    Install one with: ${YELLOW}ollama pull qwen2.5:7b${NC}"
            read -p "    Pull qwen2.5:7b now? [Y/n] " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                ollama pull qwen2.5:7b
            else
                MISSING_REQS=$((MISSING_REQS + 1))
            fi
        fi
    else
        echo -e "  ${RED}✗ Ollama not running${NC}"
        echo -e "    Start with: ${YELLOW}ollama serve${NC}"
        MISSING_REQS=$((MISSING_REQS + 1))
    fi
else
    echo -e "  ${RED}✗ Ollama not installed${NC}"
    echo -e "    Install from: https://ollama.ai"
    MISSING_REQS=$((MISSING_REQS + 1))
fi

# Check for QMD
echo ""
echo -e "${YELLOW}[4/4] QMD (memory search)${NC}"
if command -v qmd &> /dev/null; then
    QMD_VERSION=$(qmd --version 2>/dev/null || echo "unknown")
    echo -e "  ✓ QMD found ($QMD_VERSION)"
    
    # Check if collections are configured
    if qmd collections 2>/dev/null | grep -q "para"; then
        echo -e "  ✓ PARA collection configured"
    else
        echo -e "  ${YELLOW}! PARA collection not configured${NC}"
        echo -e "    Add to ~/.config/qmd/config.yaml:"
        echo -e "    ${YELLOW}collections:"
        echo -e "      para:"
        echo -e "        paths: [\"$WORKSPACE/para\"]"
        echo -e "        extensions: [\".md\", \".json\"]${NC}"
    fi
else
    echo -e "  ${RED}✗ QMD not installed${NC}"
    echo -e "    Install from: https://github.com/openclaw/qmd"
    echo -e "    Or: ${YELLOW}cargo install qmd${NC}"
    MISSING_REQS=$((MISSING_REQS + 1))
fi

# Abort if missing requirements
echo ""
if [ $MISSING_REQS -gt 0 ]; then
    echo -e "${RED}╔══════════════════════════════════════╗${NC}"
    echo -e "${RED}║   Missing $MISSING_REQS required dependency(ies)   ║${NC}"
    echo -e "${RED}╚══════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Please install missing dependencies and run setup again."
    echo ""
    read -p "Continue anyway? (skill will not work correctly) [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    echo -e "${YELLOW}Continuing with warnings...${NC}"
else
    echo -e "${GREEN}All dependencies satisfied!${NC}"
fi

# Optional: Setup cron jobs
echo ""
read -p "Setup cron jobs for automatic checkpoint/decay? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Adding cron jobs...${NC}"
    
    # Create temp cron file
    CRON_TMP=$(mktemp)
    crontab -l > "$CRON_TMP" 2>/dev/null || true
    
    # Add checkpoint job (every 30 min)
    if ! grep -q "memory_checkpoint.py" "$CRON_TMP"; then
        echo "*/30 * * * * cd $WORKSPACE && PARA_WORKSPACE=$WORKSPACE python3 $SCRIPTS_PATH/memory_checkpoint.py cron >> /tmp/para-checkpoint.log 2>&1" >> "$CRON_TMP"
        echo -e "  ✓ Added checkpoint cron (every 30 min)"
    else
        echo -e "  - Checkpoint cron already exists"
    fi
    
    # Add decay job (weekly Sunday 3am)
    if ! grep -q "memory-decay.py" "$CRON_TMP"; then
        echo "0 3 * * 0 cd $WORKSPACE && PARA_WORKSPACE=$WORKSPACE python3 $SCRIPTS_PATH/memory-decay.py >> /tmp/para-decay.log 2>&1" >> "$CRON_TMP"
        echo -e "  ✓ Added decay cron (Sunday 3am)"
    else
        echo -e "  - Decay cron already exists"
    fi
    
    crontab "$CRON_TMP"
    rm "$CRON_TMP"
fi

# Create example entity
echo ""
read -p "Create example entity? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    EXAMPLE_DIR="$WORKSPACE/para/areas/people/example-person"
    mkdir -p "$EXAMPLE_DIR"
    
    cat > "$EXAMPLE_DIR/facts.json" << 'EOF'
{
  "entity": "example-person",
  "entity_type": "people",
  "created": "2026-01-31",
  "lastUpdated": "2026-01-31",
  "createdReason": "Example entity for reference",
  "facts": [
    {
      "id": "exa-001",
      "fact": "This is an example fact",
      "category": "context",
      "status": "active",
      "created": "2026-01-31",
      "lastAccessed": "2026-01-31",
      "accessCount": 1,
      "supersededBy": null,
      "relatedEntities": [],
      "source": {
        "type": "manual",
        "timestamp": "2026-01-31T12:00:00"
      }
    }
  ]
}
EOF

    cat > "$EXAMPLE_DIR/summary.md" << 'EOF'
# Example Person

*Entity created: 2026-01-31*
*Last updated: 2026-01-31*
*Reason: Example entity for reference*

## 🔥 Hot (Recent/Frequent)
- 📎 **context**: This is an example fact
EOF
    
    echo -e "  ✓ Created example entity at para/areas/people/example-person/"
fi

# Summary
echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Setup Complete!                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "PARA directory: ${YELLOW}$WORKSPACE/para/${NC}"
echo -e "Scripts: ${YELLOW}$SCRIPTS_PATH/${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Start Ollama: ${YELLOW}ollama serve${NC}"
echo -e "  2. Run checkpoint: ${YELLOW}python3 $SCRIPTS_PATH/memory_checkpoint.py manual${NC}"
echo -e "  3. Run decay: ${YELLOW}python3 $SCRIPTS_PATH/memory-decay.py --quick${NC}"
echo ""
echo -e "Environment variables (optional):"
echo -e "  export PARA_WORKSPACE=$WORKSPACE"
echo -e "  export PARA_OLLAMA_URL=http://localhost:11434/v1"
echo -e "  export PARA_MODEL=qwen2.5:7b"
echo ""
