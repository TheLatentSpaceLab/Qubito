---
name: cron
description: Manage scheduled tasks
---

Manage cron jobs that run on a schedule.

Usage:
  /cron list                                              — list all cron jobs
  /cron add 0 8 * * * morning-summary :: summarize inbox  — add a job
  /cron remove <id>                                       — remove a job
  /cron enable <id>                                       — enable a job
  /cron disable <id>                                      — disable a job
