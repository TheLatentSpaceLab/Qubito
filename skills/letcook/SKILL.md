---
name: letcook
description: Run an autonomous producer/evaluator loop on a structured task
---

Usage:
  /letcook init [dir]   — scaffold a new task with specs templates
  /letcook run [dir]    — execute the autonomous loop on a task
  /letcook list         — list existing tasks

Letcook structures a task with explicit goals, success criteria, and quality
constraints, then runs an autonomous producer/evaluator loop until quality
thresholds are met or iterations are exhausted.

Tasks are stored in ~/.qubito/letcook/ by default.
