"""
Pydantic 타입 모델

OpenAI 최신 패턴: Pydantic 기반 타입 안전성
"""

from typing import Optional, List, Union
from pydantic import BaseModel, Field
from enum import Enum


# ============================================================================
# Tool Input Models - Pydantic 기반 검증
# ============================================================================

class ReadInput(BaseModel):
    """Read tool input schema"""
    file_path: str = Field(description="Absolute path to the file to read")
    offset: Optional[int] = Field(None, description="Line number to start from (1-indexed)")
    limit: Optional[int] = Field(None, description="Number of lines to read")


class WriteInput(BaseModel):
    """Write tool input schema"""
    file_path: str = Field(description="Absolute path to the file to write")
    content: str = Field(description="Content to write")


class EditInput(BaseModel):
    """Edit tool input schema"""
    file_path: str = Field(description="Absolute path to the file to edit")
    old_string: str = Field(description="Exact string to replace")
    new_string: str = Field(description="Replacement string")
    replace_all: bool = Field(False, description="Replace all occurrences")


class BashInput(BaseModel):
    """Bash tool input schema"""
    command: str = Field(description="Bash command to execute")
    timeout: int = Field(30, description="Timeout in seconds")


class GlobInput(BaseModel):
    """Glob tool input schema"""
    pattern: str = Field(description="Glob pattern (e.g., '**/*.ts')")
    path: Optional[str] = Field(None, description="Directory to search in (default: cwd)")


class GrepInput(BaseModel):
    """Grep tool input schema"""
    pattern: str = Field(description="Regex pattern to search for")
    path: Optional[str] = Field(None, description="File or directory to search in")
    glob: Optional[str] = Field(None, description="Glob pattern to filter files")
    case_insensitive: bool = Field(False, description="Case insensitive search")


class TodoStatus(str, Enum):
    """Todo item status"""
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class TodoItem(BaseModel):
    """Todo item"""
    content: str = Field(description="Imperative form (e.g., 'Run tests')")
    status: TodoStatus = Field(description="Current status")
    activeForm: str = Field(description="Present continuous form (e.g., 'Running tests')")


class TodoWriteInput(BaseModel):
    """TodoWrite tool input schema"""
    todos: List[TodoItem] = Field(description="Updated todo list")


class SubagentType(str, Enum):
    """Subagent types"""
    general_purpose = "general-purpose"
    explore = "Explore"
    plan = "Plan"
    statusline_setup = "statusline-setup"


class ModelType(str, Enum):
    """Model types"""
    sonnet = "sonnet"  # gpt-4o
    opus = "opus"      # gpt-4-turbo
    haiku = "haiku"    # gpt-3.5-turbo


class TaskInput(BaseModel):
    """Task tool input schema (Subagent execution)"""
    subagent_type: SubagentType = Field(description="Type of agent to launch")
    description: str = Field(description="Short 3-5 word description")
    prompt: str = Field(description="Detailed instructions for the subagent")
    model: Optional[ModelType] = Field(None, description="Optional model to use")


class ExitPlanModeInput(BaseModel):
    """ExitPlanMode tool input schema"""
    plan: str = Field(description="The finalized plan (supports markdown)")


class QuestionOption(BaseModel):
    """Question option"""
    label: str = Field(description="Display text (1-5 words)")
    description: str = Field(description="Explanation of this option")


class Question(BaseModel):
    """User question"""
    question: str = Field(description="The question to ask")
    header: str = Field(description="Short label (max 12 chars)")
    options: List[QuestionOption] = Field(description="2-4 options")
    multiSelect: bool = Field(False, description="Allow multiple selections")


class AskUserQuestionInput(BaseModel):
    """AskUserQuestion tool input schema"""
    questions: List[Question] = Field(description="1-4 questions to ask")


class NotebookEditInput(BaseModel):
    """NotebookEdit tool input schema"""
    notebook_path: str = Field(description="Absolute path to Jupyter notebook")
    cell_id: Optional[str] = Field(None, description="Cell ID to edit")
    new_source: str = Field(description="New source code for the cell")
    cell_type: Optional[str] = Field(None, description="'code' or 'markdown'")
    edit_mode: Optional[str] = Field("replace", description="'replace', 'insert', or 'delete'")


class BashBackgroundInput(BaseModel):
    """BashBackground tool input schema"""
    command: str = Field(description="Bash command to execute in background")
    description: str = Field("", description="Short description of what this command does")


class BashOutputInput(BaseModel):
    """BashOutput tool input schema"""
    bash_id: str = Field(description="Background bash shell ID")
    filter: Optional[str] = Field(None, description="Regex filter for output")


class KillShellInput(BaseModel):
    """KillShell tool input schema"""
    shell_id: str = Field(description="Background shell ID to kill")


class WebSearchInput(BaseModel):
    """WebSearch tool input schema"""
    query: str = Field(description="Search query")
    allowed_domains: Optional[List[str]] = Field(None, description="Only these domains")
    blocked_domains: Optional[List[str]] = Field(None, description="Block these domains")


class WebFetchInput(BaseModel):
    """WebFetch tool input schema"""
    url: str = Field(description="URL to fetch")
    prompt: str = Field(description="What information to extract from the page")


class SlashCommandInput(BaseModel):
    """SlashCommand tool input schema"""
    command: str = Field(description="Slash command to execute (e.g., '/help')")


# ============================================================================
# Message Types
# ============================================================================

class MessageRole(str, Enum):
    """Message roles"""
    user = "user"
    assistant = "assistant"
    system = "system"
    tool = "tool"


class Message(BaseModel):
    """Chat message"""
    role: MessageRole
    content: Union[str, List[dict]]


# ============================================================================
# Tool Result Types
# ============================================================================

class ToolResult(BaseModel):
    """Tool execution result"""
    tool_name: str
    result: str
    is_error: bool = False
