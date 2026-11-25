# TaskFlow API - Claude Code Instructions

@AGENTS.md

## Claude Code Specific Guidelines

### General Workflow

- Read and follow `AGENTS.md` before making code changes.
- Inspect relevant implementation files and tests before modifying them.
- Prefer small, focused and reviewable changes.
- Explain the implementation plan before starting complex tasks.
- Do not modify unrelated files.
- Preserve existing architecture and established project decisions.
- Ask for approval before making architectural changes or introducing new dependencies.

### Implementation and Testing

- Follow the project's coding standards and architectural conventions.
- Add or update tests alongside implementation changes.
- Run relevant tests after each implementation.
- Run all required validation checks before considering a task complete.
- Never assume a test or validation command passes without executing it.
- Report executed checks and their actual results.

### Agent Usage

- Use specialized agents when their expertise is relevant to the assigned task.
- Avoid delegating simple tasks that can be completed directly.
- Review and validate all changes produced by specialized agents before accepting them.
