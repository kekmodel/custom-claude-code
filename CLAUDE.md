# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **research and educational project** that analyzes Claude Code's internal architecture and provides 4 different implementations demonstrating how to build AI coding assistants. The project is written in Korean but code and technical concepts are universal.

**Key Purpose**: Understand Claude Code's 50k+ token system prompt, 16 tools, DAG-based workflow, and multi-agent architecture through complete implementations.

### Recent Updates

**v2 LangGraph Refactoring & Fixes** (2025-01):
- ✅ **Code refactoring** - Simplified comments to essential core concepts only (~54% reduction)
- ✅ **main.py restructuring** - Extracted LivePanelManager and EventHandler classes for better separation of concerns
- ✅ **AIMessage duplication fix** - Resolved consecutive AIMessage errors by filtering subagent events
- ✅ **Message structure validation** - All tests pass: no consecutive AIMessages, proper User/Assistant alternation
- 📝 **Documentation** - Added AIMESSAGE_DUPLICATION_FIX.md explaining the issue and solution
- 📝 **Test coverage** - Created test_aimessage_fix.py and test_integration_fix.py for regression testing
- ⚠️ **Known limitation** - Graph still executes twice (astream_events + ainvoke) for state management; future optimization planned with astream()

## Project Structure

```
custom-claude-code/
├── src/custom_claude_code/    # 4 implementation versions
│   ├── v1_openai/              # OpenAI API direct (~1,891 lines)
│   ├── v2_langgraph/           # LangGraph StateGraph (~450 lines)
│   ├── v3_openai_agents/       # OpenAI Agents SDK (~280 lines)
│   └── v4_claude_agent/        # Claude Agent SDK (~302 lines)
├── docs/                       # Architecture documentation (Korean)
│   ├── 01-architecture/        # System overview, DAG structure
│   ├── 02-components/          # System prompt, tools, agents
│   ├── 03-interactions/        # Interaction patterns
│   └── 04-implementation/      # Implementation guides
├── examples/                   # Interaction simulations (JSON)
├── references/                 # Captured Claude Code data
└── test files/launcher/demos   # Testing and demonstration scripts
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

# v2 - LangGraph StateGraph implementation
uv run python -m custom_claude_code.v2_langgraph.main

# v3 - OpenAI Agents SDK implementation
uv run python -m custom_claude_code.v3_openai_agents.main

# v4 - Claude Agent SDK implementation
uv run python -m custom_claude_code.v4_claude_agent.main
```

### Testing

```bash
# Test all versions
uv run python test_all_versions.py

# Test specific version
uv run python test_v1_only.py
uv run python test_v2_korean.py
uv run python test_v4_korean.py

# Quality testing
uv run python test_claude_code_quality.py

# Live conversation test
uv run python live_conversation_test.py
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

### Version 2: LangGraph
- **Core Pattern**: StateGraph with automatic tool use loop
- **Key Concept**: Nodes (agent, tools) + Conditional edges (should_continue)
- **Subagent Implementation**: Independent StateGraph per subagent
- **Key Files**:
  - `graph.py`: StateGraph construction with custom tool node
  - `nodes.py`: execute_subagent() creates nested graphs
- **Strengths**: Visual workflow, automatic state management

### Version 3: OpenAI Agents SDK
- **Core Pattern**: Agent + Runner.run() - highest abstraction
- **Key Concept**: `Agent.as_tool()` converts agents to tools
- **Strengths**: Minimal code (~280 lines total), SQLiteSession for history
- **Limitation**: OpenAI-only

### Version 4: Claude Agent SDK (Refactored)
- **Core Pattern**: ClaudeSDKClient with agents as configuration parameters
- **Revolutionary Feature**: Subagents defined in `agents` parameter (not code!)
- **Refactoring**: Config separation - moved 72 lines to `config.py`
- **Key Files**:
  - `config.py`: SUBAGENTS dict with explore/plan/general/statusline agents
  - `main.py`: ~50 lines of core logic (was ~122 lines before config split)
- **Strengths**: Native MCP, hook system, official Anthropic SDK, preset system prompts

## Core Concepts

### DAG Structure (Directed Acyclic Graph)
All versions implement a one-way flow:
```
Main Agent
  → [Optional] Task(Explore) - Research
  → [Optional] Task(Plan) - Planning
  → Action - Write/Edit files
  → Verify - Bash tests
     → On failure: Fix → Re-verify (conditional loop only here)
     → On success: Done
```

**Critical**: No automatic re-planning, no circular dependencies, user always in control.

### Subagent System (4 Types)
All versions support 4 subagent types:
- **general-purpose**: Complex multi-step tasks (all tools)
- **Explore**: Codebase exploration (search-focused)
- **Plan**: Implementation planning (outputs plan via ExitPlanMode)
- **statusline-setup**: Config file editing (Read/Edit only)

### 16 Core Tools
- **File**: Read, Write, Edit, NotebookEdit
- **Search**: Glob (file patterns), Grep (content search)
- **Execute**: Bash, BashOutput, KillShell
- **Agent**: Task (launches subagents)
- **Management**: TodoWrite, AskUserQuestion
- **External**: WebSearch, WebFetch
- **Other**: ExitPlanMode, SlashCommand

## Key Implementation Patterns

### Version Selection by Use Case

**For learning Claude Code internals**: Use v1 - Every pattern is explicit

**For production multi-agent systems**: Use v2 - StateGraph scales well

**For rapid prototyping with OpenAI**: Use v3 - Minimal boilerplate

**For Claude-native development**: Use v4 - Official SDK, config-driven

### Common Patterns Across Versions

1. **Conversation Loop**: User input → LLM response → Tool execution → Repeat
2. **Tool Dispatch**: Check tool name → Validate input (Pydantic) → Execute → Return result
3. **Subagent Execution**: Create isolated context → Run independently → Return final message
4. **Error Handling**: Capture tool errors → Return as tool_result → LLM handles recovery

## Working with This Codebase

### Adding a New Tool (v1 example)

1. Define Pydantic input model in `types.py`:
```python
class MyToolInput(BaseModel):
    param1: str
    param2: int = 0
```

2. Implement tool function in `tools.py`:
```python
async def tool_mytool(input_obj: MyToolInput) -> str:
    # Implementation
    return result
```

3. Add to TOOL_REGISTRY in `tools.py`:
```python
TOOL_REGISTRY = {
    # ... existing tools
    "MyTool": (MyToolInput, tool_mytool),
}
```

4. Add OpenAI schema to TOOLS list in `tools.py`

### Modifying Subagent Behavior

**v1-v3**: Modify subagent execution logic in respective files
**v4**: Edit `config.py` SUBAGENTS dict (no code changes needed!)

### Testing Changes

1. Use `simple_demo.py` for quick manual testing
2. Use `test_v*_only.py` for automated version testing
3. Use `launcher.py` for interactive testing

## Environment Configuration

Required environment variables in `.env`:
```bash
# For v1, v2, v3 (using OpenAI-compatible endpoint)
OPENAI_API_KEY=sk-ant-api03-...
OPENAI_BASE_URL=https://api.anthropic.com/v1/

# For v4 (native Claude SDK)
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_BASE_URL=https://api.anthropic.com/v1/
```

Note: v1-v3 use OpenAI SDK but can point to Claude API via base URL override.

## Documentation Structure

All documentation is in Korean but follows clear patterns:
- `docs/01-architecture/`: High-level system design
- `docs/02-components/`: Detailed component analysis
- `docs/03-interactions/`: Interaction flow patterns
- `docs/04-implementation/`: Implementation guides

Key English-readable files:
- All code files (Python)
- `pyproject.toml`
- JSON schemas in `examples/`
- This CLAUDE.md

## Code Style

- **Line length**: 100 characters (Black/Ruff configured)
- **Type hints**: Used throughout (Pydantic models for tool inputs)
- **Async/await**: All I/O operations are async
- **Error handling**: Try/except with informative error messages
- **Comments**: Minimal in code (self-documenting function names), extensive in docs

## Important Constraints

1. **Do not modify Korean documentation** without explicit request - it's a reference implementation
2. **Maintain backward compatibility** - All 4 versions should remain functional
3. **Test across versions** - Changes to common patterns should work in all applicable versions
4. **Preserve system prompt structure** - It mirrors actual Claude Code prompts
5. **Keep subagent recursion depth limited** - max_depth=5 prevents infinite loops

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

### langchain_openai Missing (v2)
```bash
uv add langchain-openai
```

### Consecutive AIMessages Error (v2) ✅ FIXED
If you see "messages: roles must alternate user/assistant" error:
- **Fixed in latest version** - Subagent events are now filtered to prevent duplicate AIMessages
- **Root cause**: EventHandler was collecting AIMessages from both main agent and subagents
- **Solution**: Added tag-based filtering in handle_chat_model_end() to ignore subagent events
- **Verification**: Run `uv run python test_aimessage_fix.py` to confirm fix
- See `docs/05-improvements/AIMESSAGE_DUPLICATION_FIX.md` for detailed explanation

### Version-Specific Issues
Check version-specific README.md files for detailed guidance
