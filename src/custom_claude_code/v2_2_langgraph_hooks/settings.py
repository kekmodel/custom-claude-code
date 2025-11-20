"""
Settings and CLAUDE.md Loader

Setting Sources를 통해 파일시스템에서 설정 및 CLAUDE.md를 로드합니다.
"""

from pathlib import Path
from typing import Optional, Literal
import json

# Setting Source 타입
SettingSource = Literal["user", "project", "local"]


class SettingsLoader:
    """설정 및 CLAUDE.md 로더"""

    def __init__(self, cwd: Optional[Path] = None):
        """
        Args:
            cwd: 현재 작업 디렉토리 (None이면 Path.cwd() 사용)
        """
        self.cwd = cwd or Path.cwd()

    def load_settings(self, sources: Optional[list[SettingSource]] = None) -> dict:
        """
        파일시스템에서 설정 로드

        Args:
            sources: 로드할 Setting Source 목록
                     None이면 아무것도 로드하지 않음 (SDK 기본 동작)

        Returns:
            dict: 병합된 설정
                - settings: dict (설정 데이터)
                - claude_md: str | None (CLAUDE.md 내용)
        """
        if sources is None:
            return {'settings': {}, 'claude_md': None}

        result = {
            'settings': {},
            'claude_md': None
        }

        # 우선순위: local > project > user
        # 역순으로 로드하여 덮어쓰기
        for source in ['user', 'project', 'local']:
            if source not in sources:
                continue

            settings_data = self._load_source(source)
            if settings_data:
                result['settings'].update(settings_data)

        # CLAUDE.md 로드 ("project" source가 있을 때만)
        if 'project' in sources:
            claude_md = self._load_claude_md()
            if claude_md:
                result['claude_md'] = claude_md

        return result

    def _load_source(self, source: SettingSource) -> Optional[dict]:
        """특정 source에서 settings.json 로드"""
        if source == 'user':
            # ~/.claude/settings.json
            settings_path = Path.home() / ".claude" / "settings.json"
        elif source == 'project':
            # .claude/settings.json (cwd 기준)
            settings_path = self.cwd / ".claude" / "settings.json"
        elif source == 'local':
            # .claude/settings.local.json (cwd 기준)
            settings_path = self.cwd / ".claude" / "settings.local.json"
        else:
            return None

        if not settings_path.exists():
            return None

        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Settings Warning] Failed to load {settings_path}: {e}")
            return None

    def _load_claude_md(self) -> Optional[str]:
        """CLAUDE.md 로드 (cwd 기준)"""
        claude_md_path = self.cwd / "CLAUDE.md"

        if not claude_md_path.exists():
            return None

        try:
            with open(claude_md_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"[Settings Warning] Failed to load CLAUDE.md: {e}")
            return None


def inject_claude_md_context(claude_md: Optional[str], cwd: Path) -> str:
    """
    CLAUDE.md 내용을 system-reminder 형태로 변환

    Args:
        claude_md: CLAUDE.md 내용
        cwd: 현재 작업 디렉토리

    Returns:
        str: system-reminder 형태의 컨텍스트
    """
    if not claude_md:
        return ""

    return f"""<system-reminder>
As you answer the user's questions, you can use the following context:
# claudeMd
Codebase and user instructions are shown below. Be sure to adhere to these instructions. IMPORTANT: These instructions OVERRIDE any default behavior and you MUST follow them exactly as written.

Contents of {cwd}/CLAUDE.md (project instructions, checked into the codebase):

{claude_md}


      IMPORTANT: this context may or may not be relevant to your tasks. You should not respond to this context unless it is highly relevant to your task.
</system-reminder>
"""


# 편의 함수
def load_project_settings(cwd: Optional[Path] = None) -> dict:
    """
    프로젝트 설정 로드 (편의 함수)

    Args:
        cwd: 현재 작업 디렉토리

    Returns:
        dict: settings 및 claude_md
    """
    loader = SettingsLoader(cwd=cwd)
    return loader.load_settings(sources=["project"])


def get_claude_md_context(cwd: Optional[Path] = None) -> str:
    """
    CLAUDE.md 컨텍스트 가져오기 (편의 함수)

    Args:
        cwd: 현재 작업 디렉토리

    Returns:
        str: system-reminder 형태의 컨텍스트
    """
    loader = SettingsLoader(cwd=cwd)
    result = loader.load_settings(sources=["project"])
    claude_md = result.get('claude_md')

    if not claude_md:
        return ""

    return inject_claude_md_context(claude_md, cwd or Path.cwd())
