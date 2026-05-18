"""
Universal AI Coding Tool Context Feature Extractor
Extracts 24-dimension feature vectors from any system prompt text.
Compatible with sklearn, XGBoost, PyTorch, and any ML framework.

Usage:
    extractor = ContextFeatureExtractor()
    features = extractor.extract(system_prompt_text)
    # features is a dict with 24 keys, all numeric
    # features_vector is a list of 24 floats for ML input
"""

import re
from typing import Dict, List, Tuple, Optional


class ContextFeatureExtractor:
    """Extract 24 structured features from AI coding tool system prompts."""

    def __init__(self):
        # ============================================================
        # F01-F04: Identity Features
        # ============================================================
        self.identity_patterns = {
            "first_person_identity": [
                r"you are (?:claude|codex|cline|gemini|cursor|copilot)",
                r"you are an? (?:intelligent|highly|expert|automated|deeply)",
                r"you are a coding agent",
            ],
            "third_person_role": [
                r"your name is",
                r"you are running as",
                r"this is (?:claude|codex|cursor)",
            ],
            "generic_assistant": [
                r"you are a helpful assistant",
                r"you are an? AI assistant",
                r"you can execute tasks",
            ],
            "mode_based_identity": [
                r"you are in agent mode",
                r"you are in chat mode",
                r"you are in plan mode",
                r"only use read.only tools",
            ],
        }

        self.brand_patterns = {
            "anthropic": [r"anthropic", r"claude code", r"claude agent sdk"],
            "openai": [r"openai", r"codex", r"gpt-5", r"chatgpt"],
            "google": [r"gemini", r"google"],
            "microsoft": [r"github copilot", r"microsoft", r"vscode"],
            "anysphere": [r"cursor ide", r"cursor cli", r"anysphere"],
            "independent": [r"aider", r"cline", r"continue\.dev", r"kiro"],
        }

        # Mode-based identity for Continue (unique: "you are in agent mode")
        self.mode_identity_patterns = {
            "continue_modes": [
                r"you are in agent mode",
                r"you are in chat mode",
                r"you are in plan mode",
                r"apply button",
                r"switch to agent mode",
                r"<important_rules>",
            ],
        }

        self.environment_patterns = {
            "ide_embedded": [r"cursor ide", r"vscode", r"copilot", r"editor"],
            "terminal_cli": [r"cli", r"terminal", r"command.line"],
            "virtual_machine": [r"virtual machine", r"sandbox", r"autonomously in the background"],
            "sdk_agent": [r"agent sdk", r"langchain", r"langgraph"],
        }

        self.subagent_patterns = [
            r"sub.?agent", r"delegate", r"spawn", r"fleet of",
            r"orchestrat(?:or|e)", r"task\(spawn",
        ]

        # ============================================================
        # F05-F08: Tool Features
        # ============================================================
        self.edit_tool_patterns = {
            "apply_patch": [r"apply_patch", r"applypatch"],
            "replace_in_file": [r"replace_in_file", r"replace_string_in_file"],
            "edit_file": [r"edit_file", r"edit file", r"insert_edit_into_file"],
            "write_to_file": [r"write_to_file", r"create_file"],
            "str_replace": [r"strreplace", r"search.*replace.*block"],
            "wholefile": [r"wholefile", r"whole file"],
            "continue_edit_tools": [r"edit tools", r"apply button", r"code blocks.*language.*file name"],
        }

        self.search_style_patterns = {
            "grep_glob_dedicated": [r"\bglob\b.*tool", r"\bgrep\b.*tool", r"\brg\b.*--files"],
            "semantic_search": [r"semantic.search", r"semantic_search", r"embedding"],
            "rg_command": [r"\brg\b", r"ripgrep"],
            "tree_sitter_tags": [r"tree.sitter", r"ast.*tag", r"repo.map"],
        }

        self.terminal_patterns = {
            "run_terminal_cmd": [r"run_terminal_cmd"],
            "execute_command": [r"execute_command"],
            "shell": [r"\bshell\b.*tool", r"\bshell\b.*command"],
            "bash": [r"\bbash\b.*tool", r"executebash"],
            "run_in_terminal": [r"run_in_terminal", r"core_run_in_terminal"],
        }

        self.planning_patterns = {
            "todo_write": [r"todo_write"],
            "update_plan": [r"update_plan"],
            "enter_plan_mode": [r"enter_plan_mode", r"enterplanmode"],
            "write_todos": [r"write_todos"],
            "manage_todo_list": [r"manage_todo_list"],
            "plan mode": [r"plan mode"],
            "none": [],
        }

        # ============================================================
        # F09-F12: Structure Features
        # ============================================================
        self.mode_patterns = {
            "multi_mode": [r"chat mode.*agent mode|agent mode.*chat mode", r"plan mode.*agent mode"],
            "act_plan": [r"act mode.*plan mode|plan mode.*act mode", r"act_vs_plan"],
            "yolo_plan": [r"yolo mode|YOLO mode"],
            "single_mode": [],
        }

        self.personality_patterns = [
            r"personality", r"pragmatic.*friendly|friendly.*pragmatic",
            r"vivid inner life", r"deeply pragmatic",
        ]

        self.role_type_patterns = {
            "system_role": [r'"role":\s*"system"', r"system.prompt", r"system_reminder"],
            "developer_role": [r'"role":\s*"developer"', r"developer.message"],
            "hybrid": [r"system.*user.*message|contextual.*user"],
        }

        # ============================================================
        # F13-F16: Memory Features
        # ============================================================
        self.instruction_file_patterns = {
            "claude_md": [r"CLAUDE\.md", r"claude\.md"],
            "agents_md": [r"AGENTS\.md", r"agents\.md"],
            "gemini_md": [r"GEMINI\.md", r"gemini\.md"],
            "cursor_rules": [r"\.cursor/rules/", r"\.cursorrules", r"\.mdc"],
            "cline_rules": [r"\.clinerules"],
            "copilot_instructions": [r"copilot-instructions\.md", r"\.github/instructions"],
        }

        self.persistence_patterns = {
            "file_based": [r"memory\.md", r"MEMORY\.md", r"memory_summary"],
            "sqlite": [r"sqlite", r"\.db", r"state\.vscdb"],
            "memory_summary": [r"memory_summary\.md"],
        }

        self.rule_system_patterns = {
            "multi_type": [r"team.*rules.*project.*rules|project.*rules.*user.*rules"],
            "glob_matched": [r"globs?", r"alwaysApply", r"file.*pattern"],
            "single_file": [r"\.clinerules|CLAUDE\.md|AGENTS\.md"],
        }

        self.hierarchical_memory_patterns = {
            "global_project_local": [r"global.*project.*local|global.*project.*extension"],
            "global_project": [r"global.*project|user.*project"],
            "project_only": [r"project.*instructions|project.*rules"],
        }

        # ============================================================
        # F17-F20: Processing Features
        # ============================================================
        self.code_understanding_patterns = {
            "semantic_index": [r"semantic.search.*index|embedding.*index|vector.*database"],
            "tree_sitter_ast": [r"tree.sitter|tags.*cache|pagerank|repomap"],
            "grep_on_demand": [r"\bgrep\b.*search|\bfind.*text\b|search.*files"],
            "vector_embedding": [r"embedding.*model|embed.*provider|vector.*search"],
        }

        self.compression_patterns = {
            "incremental_summary": [r"summarize|summary|compact"],
            "memento": [r"memento|replacement.history"],
            "user_first_person": [r"I asked you|I spoke to you|first.person.*summary"],
            "file_backed": [r"save.*history.*file|transcript.*file|history\.md"],
            "threshold_based": [r"\d+%.*compress|\d+%.*threshold|token.*threshold"],
            "tool_call_compress": [r"summarize_task|summarize.*tool"],
        }

        self.injection_timing_patterns = {
            "per_message": [r"each time.*message.*attach|automatically.*inject|silently.*attach"],
            "per_turn": [r"per.*turn|each.*request|before.*send"],
            "manual": [r"add.*files.*chat|add.*context"],
        }

        self.model_architecture_patterns = {
            "single": [],
            "dual": [r"apply.*model|core.*model.*apply|less intelligent.*apply"],
            "weak_strong": [r"weak.*model|strong.*model|main.*model.*weak"],
            "any": [r"model.agnostic|any.*model|provider.agnostic|multi.*model"],
        }

        # ============================================================
        # F21-F24: Quality Features
        # ============================================================
        self.mcp_integration_patterns = {
            "prefixed": [r"mcp__.*__|mcp_.*_.*tool"],
            "native": [r"mcp.*server.*instructions|mcp.*tool.*name"],
            "provider": [r"MCPContextProvider|mcp.*context.*provider"],
            "none": [],
        }

        self.output_constraint_patterns = {
            "no_emojis": [r"no.*emoji|don't use emoji|do not use emoji"],
            "no_great_prefix": [r"never.*start.*great|forbidden.*great.*certainly"],
            "ascii_default": [r"default.*ascii|prefer.*ascii"],
            "multi_backtick": [r"quadruple.*backtick|use \`\`\`\`|four.*backtick"],
        }

        self.safety_patterns = {
            "strict": [r"never.*destructive|never.*reset.*hard|never.*force.push|strictly.*forbidden"],
            "moderate": [r"do not.*unless.*explicitly|do not.*without.*approval"],
            "basic": [r"be careful|use caution|safety|security"],
        }

        # === Additional Continue-specific patterns ===
        self.continue_markers = [
            r"<important_rules>",
            r"apply button",
            r"switch to agent mode",
            r"context.providers?",
            r"CurrentFileContextProvider",
            r"CodebaseContextProvider",
            r"RulesContextProvider",
            r"lazy placeholders",
            r"// ... existing code ...",
            r"continue\.dev",
        ]

        self.lazy_loading_patterns = {
            "file_system_backed": [r"store.*in.*file|write.*to.*file.*read.*back|everything.*is.*a.*file"],
            "prompt_inline": [r"system.prompt.*contains|instructions.*below"],
            "provider_on_demand": [r"context.providers?|on.demand|fetch.*when"],
        }

    def _match_any(self, text: str, patterns: List[str]) -> bool:
        """Check if any pattern matches the text."""
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return True
        return False

    def _match_category(self, text: str, patterns: Dict[str, List[str]]) -> str:
        """Return the first matching category key, or 'unknown'."""
        best = None
        best_score = 0
        for category, pats in patterns.items():
            if category == "none":
                continue
            score = sum(1 for p in pats if re.search(p, text, re.IGNORECASE))
            if score > best_score:
                best_score = score
                best = category
        if best is None:
            # Check if "none" is a valid category
            for category in patterns:
                if category == "none" and all(
                    not any(re.search(p, text, re.IGNORECASE) for p in pats)
                    for cat2, pats in patterns.items() if cat2 != "none"
                ):
                    return "none"
            return "unknown"
        return best

    def extract(self, text: str) -> Dict[str, float]:
        """
        Extract 24-dimension feature vector from system prompt text.
        Returns dict with feature names as keys and numeric values.
        """
        t = text.lower()
        length = len(t)

        features = {}

        # === Identity Features (F01-F04) ===

        # F01: Role declaration style (one-hot)
        for cat, pats in self.identity_patterns.items():
            if self._match_any(t, pats):
                features[f"F01_{cat}"] = 1.0
                break
        else:
            features["F01_unknown"] = 1.0

        # F02: Brand affiliation (multi-label)
        for brand, pats in self.brand_patterns.items():
            features[f"F02_{brand}"] = 1.0 if self._match_any(t, pats) else 0.0

        # F03: Runtime environment (one-hot)
        for env, pats in self.environment_patterns.items():
            if self._match_any(t, pats):
                features[f"F03_{env}"] = 1.0
                break
        else:
            features["F03_unknown"] = 1.0

        # F04: Has subagent concept
        features["F04_has_subagent"] = 1.0 if self._match_any(t, self.subagent_patterns) else 0.0

        # === Tool Features (F05-F08) ===

        # F05: Edit tool naming (one-hot)
        for cat, pats in self.edit_tool_patterns.items():
            if self._match_any(t, pats):
                features[f"F05_{cat}"] = 1.0
                break
        else:
            features["F05_unknown"] = 1.0

        # F06: Search style (one-hot)
        for cat, pats in self.search_style_patterns.items():
            if self._match_any(t, pats):
                features[f"F06_{cat}"] = 1.0
                break
        else:
            features["F06_unknown"] = 1.0

        # F07: Terminal tool naming (one-hot)
        for cat, pats in self.terminal_patterns.items():
            if self._match_any(t, pats):
                features[f"F07_{cat}"] = 1.0
                break
        else:
            features["F07_unknown"] = 1.0

        # F08: Planning tool (one-hot)
        for cat, pats in self.planning_patterns.items():
            if self._match_any(t, pats):
                features[f"F08_{cat}"] = 1.0
                break
        else:
            features["F08_none"] = 1.0

        # === Structure Features (F09-F12) ===

        # F09: System prompt length (categorical → numeric)
        if length < 1000:
            features["F09_ultra_short"] = 1.0
        elif length < 3000:
            features["F09_short"] = 1.0
        elif length < 5000:
            features["F09_medium"] = 1.0
        elif length < 8000:
            features["F09_long"] = 1.0
        else:
            features["F09_ultra_long"] = 1.0

        # F10: Mode switching (one-hot)
        for cat, pats in self.mode_patterns.items():
            if self._match_any(t, pats):
                features[f"F10_{cat}"] = 1.0
                break
        else:
            features["F10_single_mode"] = 1.0

        # F11: Has personality system
        features["F11_has_personality"] = 1.0 if self._match_any(t, self.personality_patterns) else 0.0

        # F12: Role type
        for cat, pats in self.role_type_patterns.items():
            if self._match_any(t, pats):
                features[f"F12_{cat}"] = 1.0
                break
        else:
            features["F12_unknown"] = 1.0

        # === Memory Features (F13-F16) ===

        # F13: Instruction filename (one-hot)
        for cat, pats in self.instruction_file_patterns.items():
            if self._match_any(t, pats):
                features[f"F13_{cat}"] = 1.0
                break
        else:
            features["F13_none"] = 1.0

        # F14: Memory persistence (one-hot)
        for cat, pats in self.persistence_patterns.items():
            if self._match_any(t, pats):
                features[f"F14_{cat}"] = 1.0
                break
        else:
            features["F14_none"] = 1.0

        # F15: Rule system type (one-hot)
        for cat, pats in self.rule_system_patterns.items():
            if self._match_any(t, pats):
                features[f"F15_{cat}"] = 1.0
                break
        else:
            features["F15_none"] = 1.0

        # F16: Hierarchical memory (one-hot)
        for cat, pats in self.hierarchical_memory_patterns.items():
            if self._match_any(t, pats):
                features[f"F16_{cat}"] = 1.0
                break
        else:
            features["F16_none"] = 1.0

        # === Processing Features (F17-F20) ===

        # F17: Code understanding method (one-hot)
        for cat, pats in self.code_understanding_patterns.items():
            if self._match_any(t, pats):
                features[f"F17_{cat}"] = 1.0
                break
        else:
            features["F17_unknown"] = 1.0

        # F18: Compression strategy (multi-label)
        for cat, pats in self.compression_patterns.items():
            features[f"F18_{cat}"] = 1.0 if self._match_any(t, pats) else 0.0

        # F19: Context injection timing (one-hot)
        for cat, pats in self.injection_timing_patterns.items():
            if self._match_any(t, pats):
                features[f"F19_{cat}"] = 1.0
                break
        else:
            features["F19_unknown"] = 1.0

        # F20: Model architecture (one-hot)
        for cat, pats in self.model_architecture_patterns.items():
            if self._match_any(t, pats):
                features[f"F20_{cat}"] = 1.0
                break
        else:
            features["F20_single"] = 1.0

        # === Quality Features (F21-F24) ===

        # F21: MCP integration
        for cat, pats in self.mcp_integration_patterns.items():
            if self._match_any(t, pats):
                features[f"F21_{cat}"] = 1.0
                break
        else:
            features["F21_none"] = 1.0

        # F22: Output format constraints (multi-label)
        for cat, pats in self.output_constraint_patterns.items():
            features[f"F22_{cat}"] = 1.0 if self._match_any(t, pats) else 0.0

        # F23: Safety constraint strength (one-hot)
        for cat, pats in self.safety_patterns.items():
            if self._match_any(t, pats):
                features[f"F23_{cat}"] = 1.0
                break
        else:
            features["F23_basic"] = 1.0

        # F24: Lazy loading strategy (one-hot)
        for cat, pats in self.lazy_loading_patterns.items():
            if self._match_any(t, pats):
                features[f"F24_{cat}"] = 1.0
                break
        else:
            features["F24_no_lazy_loading"] = 1.0

        # === Extra: Continue-specific marker (F25) ===
        features["F25_continue_markers"] = 1.0 if self._match_any(t, self.continue_markers) else 0.0

        return features

    def to_vector(self, features: Dict[str, float], feature_order: Optional[List[str]] = None) -> List[float]:
        """Convert feature dict to ordered list, filling missing with 0.0."""
        if feature_order is None:
            feature_order = sorted(features.keys())
        return [features.get(k, 0.0) for k in feature_order]

    def extract_vector(self, text: str) -> Tuple[List[float], List[str]]:
        """Extract features and return (vector, feature_names)."""
        features = self.extract(text)
        names = sorted(features.keys())
        return [features[n] for n in names], names

    def extract_dataframe_row(self, text: str):
        """Extract features as a single pandas-like dict row."""
        return self.extract(text)


# ============================================================
# CLI & Demo
# ============================================================
if __name__ == "__main__":
    import json, sys

    extractor = ContextFeatureExtractor()

    # Demo: extract features from a sample system prompt
    sample = """You are Cline, a highly skilled software engineer with extensive knowledge
    in many programming languages, frameworks, design patterns, and best practices.

    # RULES
    - Your current working directory is: /home/user/project
    - You cannot cd into a different directory.
    - NEVER end attempt_completion with a question.
    - You are STRICTLY FORBIDDEN from starting messages with "Great", "Certainly", "Okay".

    # TOOLS
    - replace_in_file: Perform exact string replacements
    - execute_command: Run terminal commands
    - search_files: Search with regex

    # MCP SERVERS
    memory: @modelcontextprotocol/server-memory
    """

    features = extractor.extract(sample)
    vector, names = extractor.extract_vector(sample)

    print("=" * 60)
    print("Context Feature Extractor — 24-Dimension Feature Vector")
    print("=" * 60)
    print(f"\nInput: {len(sample)} chars system prompt\n")

    # Show non-zero features
    nonzero = {k: v for k, v in features.items() if v > 0}
    print(f"Active features ({len(nonzero)}/{len(features)}):")
    for k, v in sorted(nonzero.items()):
        print(f"  {k}: {v}")

    print(f"\nFeature vector: {len(vector)} dimensions")
    print(f"First 10: {vector[:10]}")
    print(f"Non-zero count: {sum(1 for v in vector if v > 0)}")

    # Batch mode: read JSONL and output feature vectors
    if len(sys.argv) > 1 and sys.argv[1] == "--batch":
        path = sys.argv[2] if len(sys.argv) > 2 else "routing_training_data_v2.jsonl"
        print(f"\nBatch mode: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if not line.strip():
                    continue
                sample = json.loads(line)
                feats = extractor.extract(sample["text"])
                vec, _ = extractor.extract_vector(sample["text"])
                print(f"  [{i}] {sample['label']:15s} → {sum(1 for v in vec if v > 0):2d} non-zero features")
