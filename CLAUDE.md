# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**Research and educational project** implementing AI coding assistants in 7 different ways. Written in Korean but code is universal.

**What's Implemented**:
- **7 versions**: v1 (OpenAI API), v2 (LangGraph), v2.1 (Improved), v2.2 (Hooks), v2.3 (DeepAgents), v3 (Agents SDK), v4 (Claude SDK)
- **16 core tools**: File ops, search, execution, web, agents, management
- **4 subagent types**: general-purpose, Explore, Plan, statusline-setup
- **LLM-driven conversation loop** with flexible tool execution

## Quick Start

```bash
# Install
uv sync

# Run launcher (interactive)
uv run python launcher.py

# Run specific version
uv run python -m custom_claude_code.v1_openai.main            # v1: OpenAI API
uv run python -m custom_claude_code.v2_langgraph.main         # v2: LangGraph + compression
uv run python -m custom_claude_code.v2_1_langgraph_improved.main  # v2.1: Simplified ⭐
uv run python -m custom_claude_code.v2_2_langgraph_hooks.main     # v2.2: Hook System
uv run python -m custom_claude_code.v2_3_deepagents.main          # v2.3: DeepAgents
uv run python -m custom_claude_code.v3_openai_agents.main    # v3: Agents SDK
uv run python -m custom_claude_code.v4_claude_agent.main     # v4: Claude SDK

# Test
uv run python test_v2.1_basic.py        # v2.1 tests
uv run python test_v2.2_hooks.py        # v2.2 Hook tests
pytest tests/                           # All tests
```

## Version Comparison

| Version | Lines | Pattern | Key Feature | Use Case |
|---------|-------|---------|-------------|----------|
| v1 | ~1,966 | Manual loop | 16 tools, explicit control | Learning |
| v2 | ~2,376 | StateGraph | Message compression (100k) | Production |
| v2.1 ⭐ | ~585 | Simplified | 14 tools, clean code | Recommended |
| v2.2 🔬 | ~1,400 | Hook System | Security validation, file extraction | Research |
| v2.3 🆕 | ~400 | DeepAgents | Middleware architecture, SubAgents | Modern |
| v3 | ~516 | Agent+Runner | Minimal boilerplate | Prototyping |
| v4 | ~311 | ClaudeSDK | Config-driven, MCP native | Claude-native |

## Version Highlights

### v1: OpenAI API Direct
- Manual conversation loop with `finish_reason` handling
- TOOL_REGISTRY pattern, 16 tools
- Complete control, educational clarity

### v2: LangGraph Base
- StateGraph with automatic tool loop
- Message compression at 100k tokens
- Multi-model support (OpenAI/Claude/Gemini)

### v2.1: LangGraph Improved ⭐
- Simplified code (273 lines removed)
- 14 tools (bash background, web search/fetch)
- Tag-based subagent filtering prevents message corruption
- **Recommended for new projects**

### v2.2: Hook System 🔬
- **6 Hook Events**: PreToolUse, PostToolUse, UserPromptSubmit, PreCompact, Stop, SubagentStop
- **Stateless Agents**: Validation Agent (bash security), File Extraction Agent (auto file paths)
- **Permission System**: can_use_tool high-level API
- **Settings Loader**: CLAUDE.md auto-loading
- **Research/educational** - demonstrates Claude Code's Hook System architecture

### v2.3: DeepAgents 🆕
- **LangChain DeepAgents**: Official `create_deep_agent` function
- **Middleware Architecture**: TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware, SummarizationMiddleware
- **Built-in Features**: Auto-summarization (170k tokens), File system access, Task planning
- **Custom Middleware**: ExecutionMiddleware (bash), SearchMiddleware (grep), WebMiddleware (search/fetch)
- **Modern Pattern**: Composable, production-ready framework

### v3: OpenAI Agents SDK
- `Agent.as_tool()` for subagents
- SQLiteSession history
- OpenAI-only, minimal code

### v4: Claude Agent SDK
- Subagents in `agents` parameter (config, not code!)
- Native MCP, hook system
- Official Anthropic SDK

## Core Patterns

### Conversation Loop
```
User Input → LLM Decision → Tool Execution → LLM Analysis → Repeat
```

**LLM freely chooses**:
- Task(Explore/Plan) for complex work
- Direct tool use for simple ops
- Respond when complete

### Subagent Types
- **general-purpose**: Complex multi-step tasks (all tools)
- **Explore**: Codebase exploration
- **Plan**: Implementation planning
- **statusline-setup**: Config editing (Read/Edit only)

### Tools (v1: 16, v2.1: 14, v2.2: 13)
**File**: Read, Write, Edit, NotebookEdit
**Search**: Glob, Grep
**Execute**: Bash, BashBackground, BashOutput, KillShell
**Agent**: Task
**Management**: TodoWrite, AskUserQuestion, ExitPlanMode
**External**: WebSearch, WebFetch

## Environment Setup

`.env` file:
```bash
# v1, v2, v2.1, v2.2 (OpenAI SDK → Anthropic API)
OPENAI_API_KEY=sk-ant-api03-...
OPENAI_BASE_URL=https://api.anthropic.com/v1/

# v3 (actual OpenAI)
OPENAI_API_KEY_V3=sk-proj-...

# v4 (native Claude SDK)
ANTHROPIC_API_KEY=sk-ant-api03-...
```

## Working with Code

### Adding a Tool

**v2.1/v2.2 (LangGraph)**:
```python
# In tools.py
@tool
def my_tool(param: str) -> str:
    """Tool description."""
    return result

# Add to TOOLS list
```

**v4 (Claude SDK)**:
```python
# Define in SDK format, register in main.py tools list
```

### v2.1/v2.2 Critical Pattern: Subagent Filtering

**Problem**: `astream_events()` captures ALL nested graph events
**Solution**: Tag + depth filtering in EventHandler

```python
# Critical: Filter subagent events
tags = event.get("tags", [])
if not any(tag in ["seq:step:1", "graph:step:1"] for tag in tags):
    return  # Skip subagent events

if self.task_tool_depth > 0:
    return  # Skip messages inside subagent
```

**Why**: Prevents "tool_use without tool_result" API errors

### v2.2 Hook System Usage

```python
# Register hook
from custom_claude_code.v2_2_langgraph_hooks.hooks import register_hook
from custom_claude_code.v2_2_langgraph_hooks.validation_agent import create_bash_validation_hook

validation_hook = create_bash_validation_hook(
    allowlist=["ls", "cat", "git"],
    enable_validation=True
)
register_hook('PreToolUse', validation_hook, matcher='Bash')
```

### v2.3 Middleware Usage

```python
from deepagents import create_deep_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import tool

@tool
def my_custom_tool(param: str) -> str:
    """Custom tool description."""
    return f"Result: {param}"

class MyMiddleware(AgentMiddleware):
    tools = [my_custom_tool]
    system_prompt = "Use my_custom_tool when..."

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-20250514",
    middleware=[MyMiddleware()]
)
```

## Key Constraints

1. **Don't modify Korean docs** without explicit request
2. **Maintain backward compatibility** across all 7 versions
3. **Test changes** across applicable versions
4. **v2.1/v2.2**: Don't remove tag/depth filtering (critical!)
5. **v2.2**: Hook System is research/educational, not production
6. **v2.3**: Requires `deepagents` package (`uv add deepagents`)

## Troubleshooting

### Import Errors
```bash
uv sync
```

### Missing Dependencies (v2.1/v2.2)
```bash
uv add langchain-openai langchain-anthropic
uv add httpx beautifulsoup4 ddgs  # Web tools
```

### Consecutive AIMessages (v2.1/v2.2) ✅ FIXED
- **Fixed**: Tag + depth filtering in EventHandler
- **Verify**: `uv run python test_v2.1_subagents.py`
- See `docs/05-improvements/SUBAGENT_MESSAGE_FILTERING_FIX.md`

### v2.2 Hook Tests
```bash
uv run python test_v2.2_hooks.py
```

## Documentation

- `README.md`: Korean main docs
- `docs/`: Architecture analysis (Korean)
- `docs/05-improvements/`: v2.1/v2.2 improvements
- `docs/HOOK_SYSTEM_FLOW_DIAGRAM.md`: v2.2 Hook flow diagrams
- `src/custom_claude_code/v2_2_langgraph_hooks/README.md`: v2.2 detailed guide

## Performance Notes

- **Prompt Caching**: Essential for all versions
- **Streaming**: Supported across all versions
- **Async I/O**: All file/network ops are non-blocking
- **Parallel Tools**: LangGraph handles automatically (v2/v2.1/v2.2/v2.3)
- **Auto-Summarization**: v2.3 summarizes at 170k tokens via SummarizationMiddleware
