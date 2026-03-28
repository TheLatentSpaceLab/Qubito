---
name: autojob
description: Execute an autonomous multi-step job with security guardrails
type: handler
handler: src.skills.autojob.handle_autojob
---

Usage:
  /autojob do <task description>    — generate a program from your description
  /autojob run                      — execute the last generated program
  /autojob --program <path>         — execute a specific program.md

Qubito generates a structured program.md from your task, saves it for review,
then executes it step by step with a guardrail system that asks for approval
on risky actions (file writes, shell commands, deletions).
