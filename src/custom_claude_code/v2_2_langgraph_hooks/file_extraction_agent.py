"""
File Path Extraction Agent

PostToolUse Hook을 통해 Bash 명령어 출력에서 파일 경로를 자동으로 추출합니다.
"""

from typing import Any, Optional
import re
from langchain_core.messages import HumanMessage, SystemMessage
from .models import get_chat_model
from .hooks import HookCallback, HookContext


FILE_EXTRACTION_PROMPT = """Extract any file paths that this command reads or modifies.
For commands like "git diff" and "cat", include the paths of files being shown.
Use paths verbatim -- don't add any slashes or try to resolve them.
Do not try to infer paths that were not explicitly listed in the command output.

IMPORTANT: Commands that do not display the contents of the files should not return any filepaths.
For eg. "ls", "pwd", "find". Even more complicated commands that don't display the contents should not be considered.

First, determine if the command displays the contents of the files.
If it does, then <is_displaying_contents> tag should be true. If it does not, then <is_displaying_contents> tag should be false.

Format your response as:
<is_displaying_contents>
true
</is_displaying_contents>

<filepaths>
path/to/file1
path/to/file2
</filepaths>

If no files are read or modified, return empty filepaths tags:
<filepaths>
</filepaths>

Do not include any other text in your response."""


async def call_file_extraction_agent(command: str, output: str) -> dict[str, Any]:
    """
    File Extraction Agent 호출 (별도 LLM 호출)

    Args:
        command: 실행된 Bash 명령어
        output: 명령어 실행 결과

    Returns:
        dict:
            - is_displaying_contents: bool
            - filepaths: list[str]
    """
    try:
        llm = get_chat_model()

        # 출력이 너무 길면 앞부분만 사용
        max_output_len = 5000
        truncated_output = output[:max_output_len]
        if len(output) > max_output_len:
            truncated_output += f"\n\n[... truncated {len(output) - max_output_len} chars ...]"

        messages = [
            SystemMessage(content=FILE_EXTRACTION_PROMPT),
            HumanMessage(content=f"Command: {command}\nOutput: {truncated_output}")
        ]

        response = await llm.ainvoke(messages, temperature=1.0)  # 높은 온도로 창의적 추출

        content = response.content.strip()

        # XML 파싱
        is_displaying = _parse_bool_tag(content, 'is_displaying_contents')
        filepaths = _parse_list_tag(content, 'filepaths')

        return {
            'is_displaying_contents': is_displaying,
            'filepaths': filepaths
        }

    except Exception as e:
        print(f"[File Extraction Agent Error] {type(e).__name__}: {str(e)}")
        return {
            'is_displaying_contents': False,
            'filepaths': []
        }


def _parse_bool_tag(content: str, tag: str) -> bool:
    """XML 태그에서 boolean 값 추출"""
    pattern = f"<{tag}>\\s*(true|false)\\s*</{tag}>"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).lower() == 'true'
    return False


def _parse_list_tag(content: str, tag: str) -> list[str]:
    """XML 태그에서 리스트 값 추출"""
    pattern = f"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        paths_text = match.group(1).strip()
        if not paths_text:
            return []
        # 줄바꿈으로 분리하고 공백 제거
        paths = [p.strip() for p in paths_text.split('\n') if p.strip()]
        return paths
    return []


class FilePathExtractor:
    """
    Bash 출력에서 파일 경로 추출

    PostToolUse Hook으로 등록되어 Bash 실행 후 파일 경로를 자동으로 추출합니다.
    """

    def __init__(self, enable_extraction: bool = True, auto_read_files: bool = False):
        """
        Args:
            enable_extraction: File Extraction Agent 사용 여부
            auto_read_files: 추출된 파일을 자동으로 읽을지 여부 (현재 미구현)
        """
        self.enable_extraction = enable_extraction
        self.auto_read_files = auto_read_files

    async def extract_hook(
        self,
        input_data: dict[str, Any],
        tool_use_id: Optional[str],
        context: HookContext
    ) -> dict[str, Any]:
        """
        PostToolUse Hook 콜백

        Args:
            input_data: {'tool_name': str, 'tool_result': dict, ...}
            tool_use_id: 도구 사용 ID
            context: Hook 컨텍스트

        Returns:
            dict: Hook 실행 결과
        """
        tool_name = input_data.get('tool_name', '')

        # Bash 도구가 아니면 통과
        if tool_name != 'Bash':
            return {}

        if not self.enable_extraction:
            return {}

        # 명령어 및 출력 추출
        tool_input = input_data.get('tool_input', {})
        tool_result = input_data.get('tool_result', {})

        command = tool_input.get('command', '')
        output = tool_result.get('output', '')

        if not output:
            return {}

        # File Extraction Agent 호출
        extraction_result = await call_file_extraction_agent(command, output)

        is_displaying = extraction_result['is_displaying_contents']
        filepaths = extraction_result['filepaths']

        # Hook 출력
        hook_output = {
            'hookEventName': 'PostToolUse',
            'is_displaying_contents': is_displaying,
            'filepaths': filepaths,
            'command': command
        }

        # 파일 경로가 있고 컨텐츠를 표시하는 경우
        if is_displaying and filepaths:
            hook_output['suggestion'] = f"Files mentioned: {', '.join(filepaths)}"

            # TODO: auto_read_files=True인 경우 자동으로 Read 도구 호출
            # 이는 LangGraph state에 접근해야 하므로 나중에 구현
            if self.auto_read_files:
                hook_output['auto_read_requested'] = True

        return {
            'hookSpecificOutput': hook_output
        }


def create_file_extraction_hook(
    enable_extraction: bool = True,
    auto_read_files: bool = False
) -> HookCallback:
    """
    파일 경로 추출 Hook 콜백 생성

    Args:
        enable_extraction: File Extraction Agent 사용 여부
        auto_read_files: 추출된 파일을 자동으로 읽을지 여부

    Returns:
        HookCallback: PostToolUse Hook에 등록할 콜백 함수

    Example:
        from .hooks import register_hook
        from .file_extraction_agent import create_file_extraction_hook

        extraction_hook = create_file_extraction_hook(enable_extraction=True)
        register_hook('PostToolUse', extraction_hook, matcher='Bash')
    """
    extractor = FilePathExtractor(
        enable_extraction=enable_extraction,
        auto_read_files=auto_read_files
    )
    return extractor.extract_hook
