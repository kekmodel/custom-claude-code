# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **research and educational project** that implements AI coding assistants inspired by Claude Code in 5 different ways. The project is written in Korean but code and technical concepts are universal.

**What This Project Implements**:
- 5 framework implementations (OpenAI API, LangGraph, Agents SDK, Claude SDK)
- 16 core tools (file ops, search, execution, web, agents)
- 4 subagent types (general, explore, plan, statusline)
- LLM-driven conversation loop with tool execution pattern

**Claude Code Reference Materials** (in reference/ folder):
- System prompt structure
- Tool schemas
- Captured API requests/responses

### Recent Updates

**v2.1 LangGraph Improved** (2025-11-19):
- ✅ Code simplification - Removed unnecessary `compact_messages()` (273 lines deleted), simplified `call_agent()` (83% reduction)
- ✅ Tool expansion - 9→14 tools: Added background execution (`bash_background`, `bash_output`, `kill_shell`), web access (`web_search`, `web_fetch`)
- ✅ Subagent message filtering fix - Tag + depth-based filtering prevents duplicate AIMessages in conversation history
- ✅ EventHandler improvements - Removed depth tracking complexity, relies on `callbacks=[]` and tag-based filtering
- ✅ Prompt updates - Enhanced guidance for new tools, version 2.1.0

**v2 LangGraph Base** (2025-01):
- ✅ Prompt centralization (`prompts.py`) - Separated prompts from logic
- ✅ Conversation compression - Auto-compacts at 100k tokens using Claude Haiku + Extended Thinking
- ✅ Multi-model support - OpenAI, Gemini via unified factory pattern in `models.py`
- ✅ Streaming optimization - Chunk batching eliminates stuttering

## Project Structure

```
custom-claude-code/
├── src/custom_claude_code/        # 5 implementation versions
│   ├── v1_openai/                  # OpenAI API direct (~1,891 lines)
│   ├── v2_langgraph/               # LangGraph StateGraph (~2,376 lines) - Base with compression
│   ├── v2_1_langgraph_improved/    # LangGraph Improved (~585 lines) - v2.1 simplified
│   ├── v3_openai_agents/           # OpenAI Agents SDK (~516 lines)
│   ├── v4_claude_agent/            # Claude Agent SDK (~311 lines)
│   └── common/                     # Shared utilities
├── docs/                           # Architecture documentation (Korean)
│   ├── 01-architecture/            # System overview, architecture analysis
│   ├── 02-components/              # System prompt, tools, agents
│   ├── 03-interactions/            # Interaction patterns
│   ├── 04-implementation/          # Implementation guides
│   └── 05-improvements/            # v2.1 improvements documentation
├── tests/                          # Test suite
│   └── v2_improvements/            # v2/v2.1 specific tests
├── launcher.py                     # Interactive version selector
├── test_v*.py                      # Version-specific test scripts
└── README.md                       # Korean documentation
```

## Development Commands

### Running the Interactive Launcher

```bash
# Main launcher - select which version to run
uv run python launcher.py
```

### Running Individual Versions

```bash
# v1 - OpenAI API direct implementation
uv run python -m custom_claude_code.v1_openai.main

# v2 - LangGraph StateGraph implementation (with compression)
uv run python -m custom_claude_code.v2_langgraph.main

# v2.1 - LangGraph Improved implementation (simplified, 14 tools)
uv run python -m custom_claude_code.v2_1_langgraph_improved.main

# v3 - OpenAI Agents SDK implementation
uv run python -m custom_claude_code.v3_openai_agents.main

# v4 - Claude Agent SDK implementation
uv run python -m custom_claude_code.v4_claude_agent.main
```

### Testing

```bash
# v2.1 tests (new)
uv run python test_v2.1_basic.py        # Basic functionality test
uv run python test_v2.1_tools.py        # 14 tools validation
uv run python test_v2.1_subagents.py    # Subagent filtering test

# Version-specific tests
uv run python test_v1_only.py
uv run python test_v2_korean.py
uv run python test_v4_korean.py

# Comprehensive tests
pytest tests/                            # Run all tests
```

### Package Management

```bash
# Install dependencies
uv sync

# Add new dependency
uv add <package-name>

# Update dependencies
uv lock --upgrade
```

## Architecture Highlights

### Version 1: OpenAI API (Refactored)
- **Core Pattern**: Manual conversation loop with `finish_reason` handling
- **Refactoring**: Registry pattern for tools (-66 lines), function decomposition (nesting reduced 40-60%)
- **Key Files**:
  - `tools.py`: TOOL_REGISTRY pattern, 16 tools with Pydantic validation
  - `subagent.py`: Recursive subagent execution (max_depth=5)
  - `main.py`: 5 focused functions (was 1 monolithic 188-line function)
- **Strengths**: Complete control, educational clarity, production-ready

### Version 2: LangGraph (Base)
- **Core Pattern**: StateGraph with automatic tool use loop
- **Key Features**: Message compression, multi-model support (OpenAI/Claude/Gemini)
- **Key Files**:
  - `graph.py`: StateGraph construction with custom tool node
  - `nodes.py`: execute_subagent() creates nested graphs, compact_messages()
  - `prompts.py`: Centralized prompt management
  - `models.py`: Model factory pattern for multi-LLM support
- **Strengths**: Visual workflow, automatic state management, message compression at 100k tokens

### Version 2.1: LangGraph Improved (Latest)
- **Core Pattern**: Simplified StateGraph with tag-based filtering
- **Key Improvements**:
  - Removed `compact_messages()` complexity (273 lines deleted)
  - Tag + depth-based subagent filtering prevents message corruption
  - Expanded to 14 tools (background bash, web search/fetch)
  - EventHandler simplified with `callbacks=[]` pattern
- **Key Files**:
  - `main.py`: ~585 lines with LivePanelManager and EventHandler
  - `tools.py`: 14 tools with improved web and background execution support
  - `prompts.py`: Enhanced prompts for new tools
- **Strengths**: Clean message history, more tools, simpler code

### Version 3: OpenAI Agents SDK
- **Core Pattern**: Agent + Runner.run() - highest abstraction
- **Key Concept**: `Agent.as_tool()` converts agents to tools
- **Strengths**: Minimal code (~516 lines total), SQLiteSession for history
- **Limitation**: OpenAI-only

### Version 4: Claude Agent SDK (Refactored)
- **Core Pattern**: ClaudeSDKClient with agents as configuration parameters
- **Revolutionary Feature**: Subagents defined in `agents` parameter (not code!)
- **Refactoring**: Config separation - moved 72 lines to `config.py`
- **Key Files**:
  - `config.py`: SUBAGENTS dict with explore/plan/general/statusline agents
  - `main.py`: ~208 lines of core logic (was ~122 lines before config split)
- **Strengths**: Native MCP, hook system, official Anthropic SDK, preset system prompts

## Core Concepts

### Conversation Loop Pattern
All versions implement an LLM-driven conversation loop:
```
User Input
  ↓
LLM Decision (what to do next?)
  ↓
  ├─→ [Option] Call Task(Explore/Plan) - For complex multi-step work
  ├─→ [Option] Direct tool use - For simple operations
  └─→ [Option] Respond to user - When task is complete
  ↓
Tool Execution (parallel when possible)
  ↓
LLM Analyzes tool_result
  ↓
  ├─→ Success? Continue to next step or finish
  └─→ Failure? Read error → Edit fix → Re-run (LLM decides)
  ↓
Repeat until LLM determines task is complete
```

**Key Points**:
- LLM freely chooses next action based on context
- No predefined workflow - flexible tool selection
- User retains control through conversation

### Subagent System (4 Types)
All versions support 4 subagent types:
- **general-purpose**: Complex multi-step tasks (all tools)
- **Explore**: Codebase exploration (search-focused)
- **Plan**: Implementation planning (outputs plan via ExitPlanMode)
- **statusline-setup**: Config file editing (Read/Edit only)

### 16 Core Tools (v1, v4) / 14 Tools (v2.1)

**All Versions (v1, v4)**:
- **File**: Read, Write, Edit, NotebookEdit
- **Search**: Glob (file patterns), Grep (content search)
- **Execute**: Bash, BashOutput, KillShell
- **Agent**: Task (launches subagents)
- **Management**: TodoWrite, AskUserQuestion
- **External**: WebSearch, WebFetch
- **Other**: ExitPlanMode, SlashCommand

**v2.1 Specific (14 Tools)**:
- **File**: read_file, write_file, edit_file
- **Search**: glob_files, grep_code
- **Execute**: run_bash, bash_background, bash_output, kill_shell
- **Agent**: task_tool (launches subagents)
- **Management**: todo_write
- **External**: web_search, web_fetch

## Key Implementation Patterns

### Version Selection by Use Case

**For learning Claude Code internals**: Use v1 - Every pattern is explicit

**For production multi-agent systems**: Use v2 or v2.1 - StateGraph scales well
- v2: Full-featured with message compression
- v2.1: Simplified, more tools, cleaner code

**For rapid prototyping with OpenAI**: Use v3 - Minimal boilerplate

**For Claude-native development**: Use v4 - Official SDK, config-driven

### Common Patterns Across Versions

1. **Conversation Loop**: User input → LLM response → Tool execution → Repeat
2. **Tool Dispatch**: Check tool name → Validate input (Pydantic) → Execute → Return result
3. **Subagent Execution**: Create isolated context → Run independently → Return final message
4. **Error Handling**: Capture tool errors → Return as tool_result → LLM handles recovery

## Working with This Codebase

### Adding a New Tool

**v1 (OpenAI API Direct)**:
1. Define Pydantic input model in `types.py`
2. Implement tool function in `tools.py`
3. Add to TOOL_REGISTRY in `tools.py`
4. Add OpenAI schema to TOOLS list

**v2.1 (LangGraph Improved)**:
1. Define tool function in `tools.py` using `@tool` decorator
2. Add to TOOLS list for graph registration
3. Update system prompt in `prompts.py` to guide usage

**v4 (Claude SDK)**:
1. Define tool in SDK-compatible format
2. Register in main.py tools list

### Understanding Subagent Message Filtering (v2.1)

The v2.1 implementation uses a critical filtering mechanism to prevent duplicate AIMessages:

**Problem**: `graph.astream_events()` captures ALL nested graph events, including subagent internal messages
**Solution**: Tag + depth-based filtering in EventHandler

```python
# Tag filtering: Main graph has "seq:step:1" or "graph:step:1"
tags = event.get("tags", [])
if not any(tag in ["seq:step:1", "graph:step:1"] for tag in tags):
    return  # Skip subagent events

# Depth tracking: task_tool_depth > 0 means inside subagent
if self.task_tool_depth > 0:
    return  # Skip subagent internal messages
```

This prevents Anthropic API errors: "tool_use without tool_result"

See `docs/05-improvements/SUBAGENT_MESSAGE_FILTERING_FIX.md` for detailed explanation.

### Modifying Subagent Behavior

**v1-v3**: Modify subagent execution logic in respective files
**v4**: Edit `config.py` SUBAGENTS dict (no code changes needed!)

### Testing Changes

```bash
# Interactive testing
uv run python launcher.py

# Automated version tests
uv run python test_v2.1_basic.py        # v2.1 basic features
uv run python test_v2.1_subagents.py    # v2.1 subagent filtering

# Full test suite
pytest tests/
```

## Environment Configuration

Required environment variables in `.env`:
```bash
# For v1, v2, v2.1 (using OpenAI-compatible endpoint with Anthropic)
OPENAI_API_KEY=sk-ant-api03-...
OPENAI_BASE_URL=https://api.anthropic.com/v1/

# For v3 (actual OpenAI API)
OPENAI_API_KEY_V3=sk-proj-...

# For v4 (native Claude SDK)
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1/
```

**Key Points**:
- v1, v2, v2.1 use OpenAI SDK but point to Anthropic API via base URL override
- v2/v2.1 support multiple models via `models.py` factory (OpenAI, Claude, Gemini)
- v3 uses actual OpenAI API (OpenAI-only)
- v4 uses native Anthropic Claude SDK

## Documentation Structure

All documentation is in Korean but follows clear patterns:
- `docs/01-architecture/`: High-level system design
- `docs/02-components/`: Detailed component analysis
- `docs/03-interactions/`: Interaction flow patterns
- `docs/04-implementation/`: Implementation guides
- `docs/05-improvements/`: v2.1 improvements and fixes

Key English-readable files:
- All code files (Python)
- `pyproject.toml`
- JSON schemas in `examples/`
- This CLAUDE.md
- `docs/05-improvements/SUBAGENT_MESSAGE_FILTERING_FIX.md` (critical for v2.1)

## Code Style

- **Line length**: 100 characters (Black/Ruff configured)
- **Type hints**: Used throughout (Pydantic models for tool inputs)
- **Async/await**: All I/O operations are async
- **Error handling**: Try/except with informative error messages
- **Comments**: Minimal in code (self-documenting function names), extensive in docs

## Important Constraints

1. **Do not modify Korean documentation** without explicit request - it's a reference implementation
2. **Maintain backward compatibility** - All 5 versions should remain functional
3. **Test across versions** - Changes to common patterns should work in all applicable versions
4. **Preserve system prompt structure** - It mirrors actual Claude Code prompts
5. **Keep subagent recursion depth limited** - max_depth=5 prevents infinite loops
6. **v2.1 subagent filtering is critical** - Don't remove tag/depth filtering in EventHandler

## Performance Considerations

- **Prompt Caching**: Critical for v1/v2/v3 (system prompts are large)
- **Streaming**: All versions support streaming responses
- **Async I/O**: All file/network operations are non-blocking
- **Tool execution**: Independent tools can run in parallel (v2 with LangGraph handles this automatically)

## Troubleshooting

### Import Errors
Run `uv sync` to ensure all dependencies are installed

### API Key Issues
Check `.env` file has correct keys for the version being tested

### Missing Dependencies
```bash
# v2/v2.1 LangGraph dependencies
uv add langchain-openai langchain-anthropic langchain-google-genai

# v2.1 web tools
uv add httpx beautifulsoup4 ddgs
```

### Consecutive AIMessages Error (v2.1) ✅ FIXED
If you see "tool_use without tool_result" or "messages: roles must alternate" error:
- **Fixed in v2.1** - Tag + depth-based filtering prevents duplicate AIMessages
- **Root cause**: `astream_events()` captures ALL nested graph events including subagents
- **Solution**: EventHandler filters by tags (`seq:step:1`, `graph:step:1`) and tracks `task_tool_depth`
- **Verification**: Run `uv run python test_v2.1_subagents.py` to confirm fix
- See `docs/05-improvements/SUBAGENT_MESSAGE_FILTERING_FIX.md` for detailed explanation

### v2.1 EventHandler Not Filtering Subagents
Check that these patterns are present in `main.py`:
```python
# In handle_chat_model_stream and handle_chat_model_end
tags = event.get("tags", [])
if not any(tag in ["seq:step:1", "graph:step:1"] for tag in tags):
    return  # Critical: Skip subagent events

# In handle_chat_model_end
if self.task_tool_depth > 0:
    return  # Critical: Skip messages inside subagent execution
```

### Version-Specific Issues
Check version-specific README.md files for detailed guidance
