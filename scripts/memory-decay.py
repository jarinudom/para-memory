#!/usr/bin/env python3
"""
Memory Decay System (PARA Memory Skill)
Weekly script that:
1. Tracks access patterns (lastAccessed, accessCount)
2. Tiers facts into Hot/Warm/Cold with frequency resistance
3. Regenerates summaries from active facts
4. Manages supersededBy chains
5. Updates QMD indexes

Configuration (environment variables):
- PARA_WORKSPACE: Root workspace path (default: current directory)
- PARA_DIR: PARA entities directory (default: $PARA_WORKSPACE/para)
- PARA_CACHE_DIR: Cache directory (default: ~/.openclaw/memory-cache)
- PARA_HOT_DAYS: Days for Hot tier (default: 7)
- PARA_WARM_DAYS: Days for Warm tier (default: 30)
- PARA_HIGH_FREQ_THRESHOLD: Access count for frequency resistance (default: 10)
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from glob import glob

# ---- Configuration ----

def get_config():
    """Get configuration from environment variables with sensible defaults."""
    workspace = Path(os.environ.get("PARA_WORKSPACE", os.getcwd()))
    return {
        "workspace": workspace,
        "para_dir": Path(os.environ.get("PARA_DIR", workspace / "para")),
        "cache_dir": Path(os.environ.get("PARA_CACHE_DIR", Path.home() / ".openclaw" / "memory-cache")),
        "hot_days": int(os.environ.get("PARA_HOT_DAYS", "7")),
        "warm_days": int(os.environ.get("PARA_WARM_DAYS", "30")),
        "high_freq_threshold": int(os.environ.get("PARA_HIGH_FREQ_THRESHOLD", "10")),
    }

CONFIG = get_config()


def load_access_log():
    """Load access log from cache."""
    access_file = CONFIG["cache_dir"] / "access-log.json"
    if access_file.exists():
        return json.loads(access_file.read_text())
    return {}


def save_access_log(log):
    """Save access log to cache."""
    CONFIG["cache_dir"].mkdir(parents=True, exist_ok=True)
    (CONFIG["cache_dir"] / "access-log.json").write_text(json.dumps(log, indent=2))


def record_access(entity_id, fact_id):
    """Record that a fact was accessed."""
    log = load_access_log()
    key = f"{entity_id}:{fact_id}"
    now = datetime.now().isoformat()[:10]

    if key not in log:
        log[key] = {"accessCount": 0, "lastAccessed": now}

    log[key]["accessCount"] += 1
    log[key]["lastAccessed"] = now
    save_access_log(log)


def categorize_fact(last_accessed_str, access_count):
    """Categorize fact into Hot/Warm/Cold."""
    try:
        last_accessed = datetime.fromisoformat(last_accessed_str)
    except (ValueError, TypeError):
        last_accessed = datetime.now() - timedelta(days=100)
    
    days_ago = (datetime.now() - last_accessed).days

    # High frequency resists decay
    if access_count >= CONFIG["high_freq_threshold"]:
        return "hot"

    if days_ago <= CONFIG["hot_days"]:
        return "hot"
    elif days_ago <= CONFIG["warm_days"]:
        return "warm"
    else:
        return "cold"


def get_entity_type_from_path(entity_path):
    """Extract entity type from path."""
    para_dir = CONFIG["para_dir"]
    rel_path = str(entity_path).replace(str(para_dir) + "/", "")
    parts = rel_path.split("/")
    if parts[0] == "areas":
        if len(parts) >= 3:
            return parts[1]
    return parts[0] if parts else "unknown"


def update_entity_facts(entity_path):
    """Update facts.json with access metadata from log."""
    facts_file = entity_path / "facts.json"
    if not facts_file.exists():
        return [], set()

    access_log = load_access_log()
    entity_name = entity_path.name

    with open(facts_file) as f:
        data = json.load(f)

    active_facts = []
    related_entities = set()

    for fact in data.get("facts", []):
        # Use existing access data, or check log
        if "lastAccessed" not in fact:
            key = f"{entity_name}:{fact.get('id', '')}"
            if key in access_log:
                log_entry = access_log[key]
                fact["lastAccessed"] = log_entry["lastAccessed"]
                fact["accessCount"] = log_entry["accessCount"]
            else:
                fact["lastAccessed"] = data.get("created", "2026-01-01")
                fact["accessCount"] = 0

        # Only active facts go in summary
        if fact.get("status") == "active":
            active_facts.append(fact)
            for rel in fact.get("relatedEntities", []):
                related_entities.add(rel)

    # Always write back (updates access data)
    with open(facts_file, "w") as f:
        json.dump(data, f, indent=2)

    return active_facts, related_entities


def regenerate_summary(entity_path, active_facts, related_entities):
    """Regenerate summary.md from active facts with full metadata."""
    summary_file = entity_path / "summary.md"
    facts_file = entity_path / "facts.json"
    
    entity_type = get_entity_type_from_path(entity_path)
    entity_name = entity_path.name
    
    metadata = {
        "entity": entity_name,
        "entity_type": entity_type,
        "created": "unknown",
        "createdReason": "",
        "lastUpdated": "unknown"
    }
    
    if facts_file.exists():
        with open(facts_file) as f:
            data = json.load(f)
        metadata.update({
            "created": data.get("created", "unknown"),
            "createdReason": data.get("createdReason", ""),
            "lastUpdated": data.get("lastUpdated", "unknown")
        })
    
    # Categorize facts by tier
    categorized = {"hot": [], "warm": [], "cold": []}
    for fact in active_facts:
        tier = categorize_fact(
            fact.get("lastAccessed", metadata["created"]),
            fact.get("accessCount", 0)
        )
        categorized[tier].append(fact)
    
    # Build summary
    title = entity_name.replace("-", " ").title()
    lines = [
        f"# {title}",
        "",
        f"*Entity created: {metadata['created']}*",
        f"*Last updated: {metadata['lastUpdated']}*"
    ]
    
    if metadata["createdReason"]:
        lines.append(f"*Reason: {metadata['createdReason']}*")
    
    lines.append("")
    
    # Hot facts with tier indicator
    if categorized["hot"]:
        lines.append("## 🔥 Hot (Recent/Frequent)")
        for fact in categorized["hot"]:
            emoji = "📌" if fact.get("category") == "milestone" else "📎"
            if fact.get("supersededBy"):
                emoji = "🔄"
            lines.append(f"- {emoji} **{fact.get('category', 'context')}**: {fact.get('fact', '')}")
        lines.append("")
    
    # Warm facts
    if categorized["warm"]:
        lines.append("## 🌡️ Warm (Older)")
        for fact in categorized["warm"]:
            emoji = "📌" if fact.get("category") == "milestone" else "📎"
            if fact.get("supersededBy"):
                emoji = "🔄"
            lines.append(f"- {emoji} **{fact.get('category', 'context')}**: {fact.get('fact', '')}")
        lines.append("")
    
    # Cold count
    cold_count = len(categorized["cold"])
    if cold_count:
        lines.append(f"*(+ {cold_count} older facts in facts.json)*")
    
    # Related entities section
    if related_entities:
        lines.append("")
        lines.append("## 🔗 Connected To")
        for rel in sorted(related_entities):
            lines.append(f"- {rel}")
    
    summary_file.write_text("\n".join(lines))
    return len(categorized["hot"]) + len(categorized["warm"])


def clean_superseded_chains():
    """Optional: Report very old superseded facts."""
    print("[Decay] Checking superseded chains...")
    cleaned = 0
    para_dir = CONFIG["para_dir"]
    
    for entity_path in glob(str(para_dir / "areas/*/*")):
        entity_path = Path(entity_path)
        facts_file = entity_path / "facts.json"
        
        if not facts_file.exists():
            continue
        
        with open(facts_file) as f:
            data = json.load(f)
        
        active_count = sum(1 for f in data.get("facts", []) if f.get("status") == "active")
        superseded_count = sum(1 for f in data.get("facts", []) if f.get("status") == "superseded")
        
        if superseded_count > active_count * 2:
            print(f"[Decay] {entity_path.name}: {superseded_count} superseded vs {active_count} active")
    
    return cleaned


def update_qmd_indexes():
    """Refresh QMD indexes for all memory collections (if available)."""
    print("[Decay] Updating QMD indexes...")
    try:
        os.system("which qmd &>/dev/null && qmd update -c memory -c para -c para-facts &>/dev/null")
    except Exception:
        pass


def run_decay_cycle():
    """Main entry point for full decay cycle."""
    para_dir = CONFIG["para_dir"]
    
    print(f"[Decay] Starting weekly cycle - {datetime.now().date()}")
    print(f"[Decay] PARA dir: {para_dir}")
    print(f"[Decay] Tiers: Hot={CONFIG['hot_days']}d, Warm={CONFIG['warm_days']}d, HighFreq>={CONFIG['high_freq_threshold']}")

    total_summarized = 0
    entities_processed = 0

    # Process areas entities (people, companies)
    for entity_path in glob(str(para_dir / "areas/*/*")):
        entity_path = Path(entity_path)
        if entity_path.is_dir():
            active_facts, related_entities = update_entity_facts(entity_path)
            count = regenerate_summary(entity_path, active_facts, related_entities)
            total_summarized += count
            entities_processed += 1
            print(f"[Decay] {entity_path.name}: {count} facts in summary")

    # Process projects entities
    for entity_path in glob(str(para_dir / "projects/*")):
        entity_path = Path(entity_path)
        if entity_path.is_dir():
            active_facts, related_entities = update_entity_facts(entity_path)
            count = regenerate_summary(entity_path, active_facts, related_entities)
            total_summarized += count
            entities_processed += 1
            print(f"[Decay] {entity_path.name}: {count} facts in summary")

    # Process resources entities
    for entity_path in glob(str(para_dir / "resources/*")):
        entity_path = Path(entity_path)
        if entity_path.is_dir():
            active_facts, related_entities = update_entity_facts(entity_path)
            count = regenerate_summary(entity_path, active_facts, related_entities)
            total_summarized += count
            entities_processed += 1
            print(f"[Decay] {entity_path.name}: {count} facts in summary")

    # Clean chains
    cleaned = clean_superseded_chains()

    # Update QMD
    update_qmd_indexes()

    print(f"[Decay] Complete - {entities_processed} entities, {total_summarized} facts in summaries, {cleaned} cleaned")


def run_quick_decay():
    """Quick decay - just update summaries without full reprocessing."""
    para_dir = CONFIG["para_dir"]
    
    print(f"[Decay] Quick cycle - {datetime.now().date()}")
    print(f"[Decay] PARA dir: {para_dir}")

    # Process all entity types
    all_paths = (
        glob(str(para_dir / "areas/*/*")) + 
        glob(str(para_dir / "projects/*")) + 
        glob(str(para_dir / "resources/*"))
    )
    
    for entity_path in all_paths:
        entity_path = Path(entity_path)
        if entity_path.is_dir():
            active_facts, related_entities = update_entity_facts(entity_path)
            regenerate_summary(entity_path, active_facts, related_entities)

    update_qmd_indexes()
    print("[Decay] Quick cycle complete")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        run_quick_decay()
    else:
        run_decay_cycle()
