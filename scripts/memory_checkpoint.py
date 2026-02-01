#!/usr/bin/env python3
"""
Memory Checkpoint Loop (PARA Memory Skill)
Runs every 30 minutes via cron, or can be triggered manually.
Uses LLM to analyze context and extract permanent memories.

Features:
- Writes facts to PARA entity structure
- Entity creation heuristics (3+ mentions, direct relationship, significant)
- supersededBy chains for fact history tracking
- relatedEntities cross-references between entities
- Source tracking (conversation, timestamp, messageId)
- Access metadata bumping for decay system
- Daily notes timeline entries

Configuration (environment variables):
- PARA_WORKSPACE: Root workspace path (default: current directory)
- PARA_MEMORY_DIR: Daily notes directory (default: $PARA_WORKSPACE/memory)
- PARA_DIR: PARA entities directory (default: $PARA_WORKSPACE/para)
- PARA_CACHE_DIR: Cache directory (default: ~/.openclaw/memory-cache)
- PARA_OLLAMA_URL: Ollama API URL (default: http://localhost:11434/v1)
- PARA_MODEL: LLM model name (default: qwen2.5:7b)
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

# ---- Configuration ----

def get_config():
    """Get configuration from environment variables with sensible defaults."""
    workspace = Path(os.environ.get("PARA_WORKSPACE", os.getcwd()))
    return {
        "workspace": workspace,
        "memory_dir": Path(os.environ.get("PARA_MEMORY_DIR", workspace / "memory")),
        "para_dir": Path(os.environ.get("PARA_DIR", workspace / "para")),
        "cache_dir": Path(os.environ.get("PARA_CACHE_DIR", Path.home() / ".openclaw" / "memory-cache")),
        "ollama_url": os.environ.get("PARA_OLLAMA_URL", "http://localhost:11434/v1"),
        "model": os.environ.get("PARA_MODEL", "qwen2.5:7b"),
        "mention_threshold": int(os.environ.get("PARA_MENTION_THRESHOLD", "3")),
    }

CONFIG = get_config()

# ---- Helpers ----

def slugify(name: str) -> str:
    """Convert arbitrary model output into a safe directory slug."""
    s = name.strip().lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "unnamed"


def entity_path_for(entity_type: str, entity_name: str) -> Path:
    """Get the path for an entity."""
    entity_name = slugify(entity_name)
    para_dir = CONFIG["para_dir"]
    if entity_type in ["people", "companies"]:
        return para_dir / "areas" / entity_type / entity_name
    return para_dir / entity_type / entity_name


def get_recent_context():
    """Get recent conversation context from OpenClaw session files."""
    workspace = CONFIG["workspace"]
    memory_dir = CONFIG["memory_dir"]
    
    possible_paths = [
        workspace / ".openclaw" / "session-context.json",
        Path.home() / ".openclaw" / "sessions" / "main.json",
        memory_dir / f"{datetime.now().strftime('%Y-%m-%d')}.md"
    ]
    
    for context_file in possible_paths:
        if context_file.exists():
            if context_file.suffix == ".json":
                with open(context_file) as f:
                    data = json.load(f)
                    return data.get("recent_messages", data.get("messages", []))
            else:
                return [{"role": "context", "content": context_file.read_text()}]
    return []


def get_existing_entities():
    """Get list of existing PARA entities with their types."""
    para_dir = CONFIG["para_dir"]
    entities = {"people": [], "companies": [], "projects": [], "resources": []}
    
    for entity_type in entities.keys():
        if entity_type in ["people", "companies"]:
            type_dir = para_dir / "areas" / entity_type
        else:
            type_dir = para_dir / entity_type
        if type_dir.exists():
            entities[entity_type] = [d.name for d in type_dir.iterdir() if d.is_dir()]
    
    return entities


def get_all_entity_paths():
    """Get mapping of entity names to their full paths."""
    para_dir = CONFIG["para_dir"]
    paths = {}
    
    for entity_type in ["people", "companies", "projects", "resources"]:
        if entity_type in ["people", "companies"]:
            type_dir = para_dir / "areas" / entity_type
        else:
            type_dir = para_dir / entity_type
        if type_dir.exists():
            for d in type_dir.iterdir():
                if d.is_dir():
                    paths[d.name] = str(d).replace(str(para_dir) + "/", "")
    return paths


def analyze_with_llm(messages, current_memory, existing_entities, all_entity_paths):
    """Use LLM to analyze what should be checkpointed."""
    try:
        import openai
    except ImportError:
        print("[Checkpoint] Error: openai package required. Install with: pip install openai", file=sys.stderr)
        raise

    client = openai.OpenAI(base_url=CONFIG["ollama_url"], api_key="ollama", timeout=60.0)

    existing_str = json.dumps(existing_entities, indent=2)
    entity_paths_str = json.dumps(all_entity_paths, indent=2)
    
    prompt = f"""You are analyzing a conversation for memory checkpointing.

## Recent Messages (truncated):
{json.dumps(messages[-30:], indent=2)[:15000]}

## Current Memory Summary:
{current_memory[:3000]}

## Existing PARA Entities:
{existing_str}

## Known Entity Paths (for relatedEntities references):
{entity_paths_str}

## PARA Structure:
- areas/people/ — People with direct relationships
- areas/companies/ — Companies/organizations
- projects/ — Active work with goals/deadlines
- resources/ — Topics of interest

## Task:
Extract durable information from the conversation. For each item, determine:
1. Is it a NEW PERMANENT FACT about an existing entity? (includes relatedEntities)
2. Should it CREATE A NEW ENTITY? (mentioned 3+ times OR direct relationship OR significant project)
3. Is it just DAILY NOTE material? (one-off, transient)

## Fact Schema:
Each fact needs:
- category: relationship|milestone|status|preference|context
- content: The actual fact text
- supersedes: (optional) ID of fact this replaces (creates supersededBy chain)
- relatedEntities: (optional) array of entity paths like ["areas/people/tara", "projects/bards-and-cards"]
- source: {{type: "conversation"|"file"|"manual", timestamp: "...", messageId: "...", channel: "..."}}

Respond in JSON format:
{{
  "entity_facts": [
    {{
      "entity_type": "people|companies|projects|resources",
      "entity_name": "slug-name",
      "action": "append|supersede",
      "supersedes_id": "ent-002",  // optional, only if superseding
      "fact": {{
        "category": "relationship|milestone|status|preference|context",
        "content": "The actual fact",
        "relatedEntities": ["areas/people/tara", "projects/bards-and-cards"]
      }}
    }}
  ],
  "daily_notes": "Timeline entry for today (or null)",
  "new_entities": [
    {{
      "entity_type": "people|companies|projects|resources",
      "entity_name": "slug-name",
      "reason": "Why this deserves an entity (3+ mentions, direct relationship, significant)"
    }}
  ],
  "decisions": ["Any decisions made"],
  "skip_reason": "If nothing to extract, explain why"
}}

Rules:
- Skip casual chat, greetings, transient requests
- Only extract facts that should persist beyond this conversation
- Use existing entity names when they exist (check the list above)
- Entity names MUST be slugs: lowercase, hyphen-separated, no spaces/parentheses
- Create new entities only for significant items
- When a fact updates previous info, set supersedes_id to mark old as superseded
- relatedEntities helps build the knowledge graph connections"""

    response = client.chat.completions.create(
        model=CONFIG["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return response.choices[0].message.content


def parse_llm_response(analysis):
    """Parse LLM response with multiple fallback strategies."""
    # Strategy 1: Direct JSON parse
    try:
        return json.loads(analysis)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract from markdown code blocks
    json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Strategy 3: Extract from ```code blocks
    json_match = re.search(r'```\s*(\{.*?\})\s*```', analysis, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Strategy 4: Find first { and last } with entity_facts key
    json_match = re.search(r'\{[^{}]*"entity_facts"[^{}]*\}', analysis, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # Strategy 5: Brute force - find all { } pairs and try each
    depth = 0
    start = -1
    for i, char in enumerate(analysis):
        if char == '{':
            if depth == 0:
                start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    candidate = analysis[start:i+1]
                    result = json.loads(candidate)
                    if "entity_facts" in result or "new_entities" in result:
                        return result
                except json.JSONDecodeError:
                    pass
                start = -1
    
    raise ValueError(f"Could not parse LLM response as JSON. First 500 chars:\n{analysis[:500]}")


def create_entity(entity_type, entity_name, reason=""):
    """Create a new PARA entity folder with initial files."""
    entity_name = slugify(entity_name)
    entity_path = entity_path_for(entity_type, entity_name)
    
    entity_path.mkdir(parents=True, exist_ok=True)
    
    # Create summary.md with proper metadata
    summary_file = entity_path / "summary.md"
    if not summary_file.exists():
        title = entity_name.replace("-", " ").title()
        summary_file.write_text(f"# {title}\n\n*Entity created: {datetime.now().strftime('%Y-%m-%d')}*\n*Reason: {reason}*\n")
    
    # Create facts.json with full schema
    facts_file = entity_path / "facts.json"
    if not facts_file.exists():
        facts_file.write_text(json.dumps({
            "entity": entity_name,
            "entity_type": entity_type,
            "created": datetime.now().strftime("%Y-%m-%d"),
            "lastUpdated": datetime.now().strftime("%Y-%m-%d"),
            "createdReason": reason,
            "facts": []
        }, indent=2))
    
    return entity_path


def append_fact_to_entity(entity_type, entity_name, fact, source=None, supersedes_id=None):
    """Append a fact to an existing entity's facts.json with full schema."""
    entity_name = slugify(entity_name)
    entity_path = entity_path_for(entity_type, entity_name)
    
    facts_file = entity_path / "facts.json"
    
    if not facts_file.exists():
        create_entity(entity_type, entity_name, "Auto-created for fact storage")
    
    with open(facts_file) as f:
        data = json.load(f)
    
    # Generate fact ID
    existing_ids = [f.get("id", "") for f in data.get("facts", [])]
    new_id = f"{entity_name[:3]}-{len(existing_ids) + 1:03d}"
    
    # Check for duplicates (simple content match)
    existing_contents = [f.get("fact", "") for f in data.get("facts", [])]
    if fact.get("content") in existing_contents:
        print(f"[Checkpoint] Skipping duplicate fact: {fact.get('content', '')[:50]}...")
        return None
    
    # Build fact with full schema
    new_fact = {
        "id": new_id,
        "fact": fact.get("content", ""),
        "category": fact.get("category", "context"),
        "status": "active",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "lastAccessed": datetime.now().strftime("%Y-%m-%d"),
        "accessCount": 1,
        "relatedEntities": fact.get("relatedEntities", [])
    }
    
    # Add source tracking
    if source:
        new_fact["source"] = source
    else:
        new_fact["source"] = {"type": "checkpoint", "timestamp": datetime.now().isoformat()}
    
    # Handle supersededBy chain
    new_fact["supersededBy"] = supersedes_id if supersedes_id else None
    
    # Mark old fact as superseded if we're replacing it
    if supersedes_id:
        for old_fact in data.get("facts", []):
            if old_fact.get("id") == supersedes_id and old_fact.get("status") == "active":
                old_fact["status"] = "superseded"
                old_fact["supersededBy"] = new_id
                print(f"[Checkpoint] ← Superseded fact {supersedes_id}")
                break
    
    data["facts"].append(new_fact)
    data["lastUpdated"] = datetime.now().strftime("%Y-%m-%d")
    
    with open(facts_file, "w") as f:
        json.dump(data, f, indent=2)
    
    return new_fact


def update_entity_cross_references(entity_type, entity_name, related_entities):
    """Update relatedEntities on referenced entities (bidirectional links)."""
    para_dir = CONFIG["para_dir"]
    
    for rel_path in related_entities:
        parts = rel_path.split("/")
        if len(parts) >= 2:
            ref_type = parts[0]
            ref_entity = parts[-1]
            
            if ref_type == "areas":
                if len(parts) >= 3:
                    actual_ref_type = parts[1]
                else:
                    continue
            else:
                actual_ref_type = ref_type.rstrip('s')
            
            ref_path = entity_path_for(actual_ref_type, ref_entity)
            ref_facts_file = ref_path / "facts.json"
            
            if ref_facts_file.exists():
                with open(ref_facts_file) as f:
                    data = json.load(f)
                
                if entity_type in ["people", "companies"]:
                    back_ref = f"areas/{entity_type}/{entity_name}"
                else:
                    back_ref = f"{entity_type}/{entity_name}"
                
                for fact in data.get("facts", []):
                    if fact.get("status") == "active":
                        current_rels = fact.get("relatedEntities", [])
                        if back_ref not in current_rels:
                            current_rels.append(back_ref)
                            fact["relatedEntities"] = current_rels
                
                with open(ref_facts_file, "w") as f:
                    json.dump(data, f, indent=2)


def bump_access_metadata(entity_type, entity_name, fact_ids=None):
    """Bump access metadata for facts (for decay system)."""
    entity_name = slugify(entity_name)
    entity_path = entity_path_for(entity_type, entity_name)
    
    facts_file = entity_path / "facts.json"
    if not facts_file.exists():
        return 0
    
    with open(facts_file) as f:
        data = json.load(f)
    
    now = datetime.now().strftime("%Y-%m-%d")
    bumped = 0
    
    for fact in data.get("facts", []):
        if fact_ids is None or fact.get("id") in fact_ids:
            fact["lastAccessed"] = now
            fact["accessCount"] = fact.get("accessCount", 0) + 1
            bumped += 1
    
    with open(facts_file, "w") as f:
        json.dump(data, f, indent=2)
    
    update_access_log(entity_name, [f["id"] for f in data.get("facts", [])])
    
    return bumped


def update_access_log(entity_name, fact_ids):
    """Update the central access log for decay system."""
    entity_name = slugify(entity_name)
    cache_dir = CONFIG["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    access_file = cache_dir / "access-log.json"
    
    if access_file.exists():
        log = json.loads(access_file.read_text())
    else:
        log = {}
    
    now = datetime.now().strftime("%Y-%m-%d")
    for fact_id in fact_ids:
        key = f"{entity_name}:{fact_id}"
        if key not in log:
            log[key] = {"accessCount": 0, "lastAccessed": now}
        log[key]["accessCount"] += 1
        log[key]["lastAccessed"] = now
    
    access_file.write_text(json.dumps(log, indent=2))


def write_daily_note(entry):
    """Write entry to today's daily note."""
    memory_dir = CONFIG["memory_dir"]
    memory_dir.mkdir(parents=True, exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    note_path = memory_dir / f"{today}.md"
    timestamp = datetime.now().strftime("%H:%M")

    if note_path.exists():
        content = note_path.read_text()
    else:
        content = f"# {today}\n"

    content += f"\n## {timestamp} - Checkpoint\n{entry}\n"
    note_path.write_text(content)
    return note_path


def update_qmd():
    """Refresh QMD index (if available)."""
    try:
        os.system("which qmd &>/dev/null && qmd update -c memory -c para -c para-facts &>/dev/null")
    except Exception:
        pass  # QMD is optional


def regenerate_entity_summary(entity_type, entity_name):
    """Regenerate summary.md from active facts (for decay system)."""
    entity_path = entity_path_for(entity_type, entity_name)
    facts_file = entity_path / "facts.json"
    summary_file = entity_path / "summary.md"
    
    if not facts_file.exists():
        return 0
    
    with open(facts_file) as f:
        data = json.load(f)
    
    entity = data.get("entity", entity_name)
    created = data.get("created", "unknown")
    created_reason = data.get("createdReason", "")
    last_updated = data.get("lastUpdated", "unknown")
    
    now = datetime.now()
    HOT_DAYS = 7
    WARM_DAYS = 30
    
    categorized = {"hot": [], "warm": [], "cold": []}
    for fact in data.get("facts", []):
        if fact.get("status") != "active":
            continue
            
        last_accessed = fact.get("lastAccessed", created)
        try:
            days_ago = (now - datetime.fromisoformat(last_accessed)).days
        except:
            days_ago = 100
        
        access_count = fact.get("accessCount", 0)
        
        if access_count >= 10:
            categorized["hot"].append(fact)
        elif days_ago <= HOT_DAYS:
            categorized["hot"].append(fact)
        elif days_ago <= WARM_DAYS:
            categorized["warm"].append(fact)
        else:
            categorized["cold"].append(fact)
    
    title = entity.replace("-", " ").title()
    lines = [
        f"# {title}",
        "",
        f"*Entity created: {created}*",
        f"*Last updated: {last_updated}*"
    ]
    
    if created_reason:
        lines.append(f"*Reason: {created_reason}*")
    
    lines.append("")
    
    if categorized["hot"]:
        lines.append("## 🔥 Hot (Recent/Frequent)")
        for fact in categorized["hot"]:
            tier_emoji = "📌" if fact.get("category") == "milestone" else "📎"
            lines.append(f"- {tier_emoji} **{fact['category']}**: {fact['fact']}")
        lines.append("")
    
    if categorized["warm"]:
        lines.append("## 🌡️ Warm (Older)")
        for fact in categorized["warm"]:
            tier_emoji = "📌" if fact.get("category") == "milestone" else "📎"
            lines.append(f"- {tier_emoji} **{fact['category']}**: {fact['fact']}")
        lines.append("")
    
    if categorized["cold"]:
        lines.append(f"*(+ {len(categorized['cold'])} older facts in facts.json)*")
    
    all_related = set()
    for fact in data.get("facts", []):
        if fact.get("status") == "active":
            for rel in fact.get("relatedEntities", []):
                all_related.add(rel)
    
    if all_related:
        lines.append("")
        lines.append("## 🔗 Connected To")
        for rel in sorted(all_related):
            lines.append(f"- {rel}")
    
    summary_file.write_text("\n".join(lines))
    
    return len(categorized["hot"]) + len(categorized["warm"])


def trigger_checkpoint(reason="manual"):
    """Main entry point for checkpoint."""
    print(f"[Checkpoint] Starting - {reason} - {datetime.now()}")
    print(f"[Checkpoint] Workspace: {CONFIG['workspace']}")

    messages = get_recent_context()
    if not messages:
        print("[Checkpoint] No recent context, skipping")
        return {"status": "skipped", "reason": "no context"}

    workspace = CONFIG["workspace"]
    current_memory = ""
    memory_file = workspace / "MEMORY.md"
    if memory_file.exists():
        current_memory = memory_file.read_text()
    
    existing_entities = get_existing_entities()
    all_entity_paths = get_all_entity_paths()
    
    try:
        analysis = analyze_with_llm(messages, current_memory, existing_entities, all_entity_paths)
        print(f"[Checkpoint] LLM analysis complete")

        result = parse_llm_response(analysis)
        
        stats = {"entities_created": 0, "facts_added": 0, "facts_superseded": 0, "daily_notes": False}
        
        for entity in result.get("new_entities", []):
            entity_type = entity.get("entity_type")
            entity_name = entity.get("entity_name")
            reason_text = entity.get("reason", "")
            
            if entity_type and entity_name:
                create_entity(entity_type, entity_name, reason_text)
                stats["entities_created"] += 1
                print(f"[Checkpoint] ✓ Created entity: {entity_type}/{entity_name}")
        
        for ef in result.get("entity_facts", []):
            entity_type = ef.get("entity_type")
            entity_name = ef.get("entity_name")
            fact = ef.get("fact", {})
            supersedes_id = ef.get("supersedes_id")
            
            if entity_type and entity_name and fact:
                new_fact = append_fact_to_entity(
                    entity_type, 
                    entity_name, 
                    fact,
                    source={"type": "conversation", "timestamp": datetime.now().isoformat()},
                    supersedes_id=supersedes_id
                )
                if new_fact:
                    stats["facts_added"] += 1
                    if supersedes_id:
                        stats["facts_superseded"] += 1
                    print(f"[Checkpoint] ✓ Added fact to {entity_type}/{entity_name}")
                
                if fact.get("relatedEntities"):
                    update_entity_cross_references(entity_type, entity_name, fact["relatedEntities"])
        
        modified_entities = set()
        for ef in result.get("entity_facts", []):
            if ef.get("entity_type") and ef.get("entity_name"):
                modified_entities.add((ef["entity_type"], ef["entity_name"]))
        
        for entity_type, entity_name in modified_entities:
            regenerate_entity_summary(entity_type, entity_name)
        
        if result.get("daily_notes"):
            write_daily_note(result["daily_notes"])
            stats["daily_notes"] = True
            print(f"[Checkpoint] ✓ Daily note updated")
        
        update_qmd()
        
        print(f"[Checkpoint] Complete - {stats}")
        return {"status": "success", "stats": stats}

    except Exception as e:
        print(f"[Checkpoint] Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    reason = sys.argv[1] if len(sys.argv) > 1 else "manual"
    trigger_checkpoint(reason)
