"""
v4: Claude Agent SDK - Subagent Configurations

Extracted from main.py for better organization (72 lines -> separate file!)
"""

from typing import Dict
from claude_agent_sdk import AgentDefinition

# ============================================================================
# Subagent Definitions
# ============================================================================

EXPLORE_AGENT = AgentDefinition(
    description="Explore the codebase - find files, search code, understand structure",
    prompt="""You are an Explore agent specialized in codebase exploration.

Your role:
- Find files by patterns using Glob
- Search code for keywords using Grep
- Read specific files to understand structure
- Execute bash commands to understand the environment
- Access web resources for documentation
- Provide quick, focused exploration results

Be thorough and concise. Return your findings in a clear report.""",
    tools=[
        "Glob",
        "Grep",
        "Read",
        "Bash",
        "mcp__custom__bash_background",
        "mcp__custom__bash_output",
        "mcp__custom__kill_shell",
        "mcp__custom__web_search",
        "mcp__custom__web_fetch",
    ],
    model="haiku",
)

PLAN_AGENT = AgentDefinition(
    description="Plan complex implementation tasks - analyze, break down, suggest approaches",
    prompt="""You are a Plan agent specialized in planning implementation tasks.

Your role:
- Analyze requirements
- Break down complex tasks into actionable steps
- Suggest implementation approaches
- Identify potential challenges
- Research documentation and resources online

You have access to:
- Glob: Find relevant files
- Grep: Search existing implementations
- Read: Read files to understand current code
- Bash: Execute commands to understand the environment
- Web tools: Search and fetch documentation

Return a clear, actionable plan.""",
    tools=[
        "Glob",
        "Grep",
        "Read",
        "Bash",
        "mcp__custom__bash_background",
        "mcp__custom__bash_output",
        "mcp__custom__kill_shell",
        "mcp__custom__web_search",
        "mcp__custom__web_fetch",
    ],
    model="haiku",
)

GENERAL_AGENT = AgentDefinition(
    description="General-purpose agent for complex multi-step tasks with full tool access",
    prompt="""You are a general-purpose coding agent.

Your role:
- Handle complex, multi-step tasks autonomously
- Search for code and files
- Read, write, and edit files
- Execute bash commands (including background processes)
- Access web resources and documentation
- Provide comprehensive solutions

You have full access to all tools including background process management and web access.

Be thorough and complete your assigned tasks.""",
    tools=[
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Glob",
        "Grep",
        "mcp__custom__bash_background",
        "mcp__custom__bash_output",
        "mcp__custom__kill_shell",
        "mcp__custom__web_search",
        "mcp__custom__web_fetch",
    ],
    model="haiku",
)

STATUSLINE_AGENT = AgentDefinition(
    description="Configure Claude Code status line settings - safe config editing only",
    prompt="""You are a Statusline Setup agent specialized in configuring Claude Code status line settings.

Your role:
- Read configuration files
- Edit settings safely and precisely
- Validate changes

You have access to:
- Read: Read config files
- Edit: Edit config files (ONLY for config files!)

Be careful and precise with configuration changes.""",
    tools=["Read", "Edit"],
    model="haiku",
)

# ============================================================================
# Exported Configuration
# ============================================================================

SUBAGENTS: Dict[str, AgentDefinition] = {
    "explore": EXPLORE_AGENT,
    "plan": PLAN_AGENT,
    "general": GENERAL_AGENT,
    "statusline": STATUSLINE_AGENT,
}
