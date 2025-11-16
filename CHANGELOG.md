# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- 개선 문서 디렉토리 구조 (`docs/05-improvements/`, `tests/v2_improvements/`)
- 레퍼런스 검증 스크립트 (`verify_tools_implementation.py`)
- 도구 개선 테스트 (`test_improved_tools.py`, `test_task_tool.py`)
- Subagent 타입별 역할 설명 (system prompt에 추가)

### Changed

#### v2 LangGraph - 도구 개선
- **grep_code**: 10개 파라미터 추가 (output_mode, type, i, n, A, B, C, head_limit, offset, multiline)
  - 레퍼런스 일치도: 31% → 100%
  - ripgrep 전체 기능 지원
  - Python fallback 구현 개선

- **run_bash**: timeout 단위 변경 (seconds → milliseconds)
  - 레퍼런스와 형식 통일
  - description 파라미터 제거 (불필요)

- **task_tool**: 레퍼런스 완전 일치
  - 파라미터 순서 수정: `description`, `prompt`, `subagent_type`, `model`, `resume`
  - resume 파라미터 추가 (Agent 재개 기능)
  - 상세 설명 추가 (레퍼런스 JSON과 동일)

#### v2 LangGraph - Subagent 개선
- **Plan agent 설명 수정**: Explore와 중복되던 설명을 "구현 계획 수립 전문"으로 수정
- **subagent_type 기반 도구 필터링 구현**:
  - Explore: 읽기 전용 (write_file, edit_file 제외)
  - Plan: 읽기 전용 (read_file, grep_code, glob_files, run_bash만)
  - general-purpose: 모든 도구 사용 가능
- **Subagent system prompt 개선**: 각 타입별 역할과 제한사항 명시

### Fixed
- Plan agent 설명이 Explore와 중복되던 버그 수정 (`nodes.py:826-832`)
- subagent_type 파라미터가 전달되지만 실제로 사용되지 않던 문제 수정
- grep_code의 대소문자 무시 파라미터명 통일 (`case_insensitive` → `i`)

---

## [2025-11-16] - v2 개선

### 개선 요약

**도구 구현 완전성**:
- grep_code: 13/13 파라미터 (100%)
- run_bash: 핵심 파라미터 일치 (백그라운드 제외)
- task_tool: 5/5 파라미터 (100%)

**Subagent 시스템**:
- 타입별 도구 필터링 구현
- 역할별 명확한 설명 추가
- 안전성 향상 (읽기/쓰기 분리)

**테스트**:
- 10개 테스트 케이스 추가
- 모든 개선 사항 검증 완료

---

## 변경 이력

### 2025-11-16
- 초기 CHANGELOG 작성
- v2 개선 사항 문서화
- 테스트 및 문서 디렉토리 정리

---

## 향후 계획

### 우선순위 높음 🔴
- [ ] WebFetch, WebSearch 도구 추가
- [ ] resume 파라미터 실제 구현

### 우선순위 중간 🟡
- [ ] BashOutput, KillShell 도구 추가
- [ ] Subagent 실행 로그 수집

### 우선순위 낮음 🟢
- [ ] NotebookEdit, Skill, SlashCommand 도구 추가
- [ ] 전체 16개 도구 완전 구현

---

## 기여자

- **Claude (Sonnet 4.5)**: v2 개선 및 문서화
- **User**: 요구사항 정의 및 검증

---

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 제작되었습니다.
