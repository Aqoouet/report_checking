# BUGS CAVEMAN LIST

Project hurt. Many sharp rock.  
Below big bug list. Caveman words, but deep detail.

## Git check (last 20 commits) — bug status

- ✅ #1 fixed in `909d71b` (cooperative cancel checks in pipeline)
- ✅ #2 fixed in `909d71b` (set `CANCELLED` flow)
- ✅ #3 fixed in `f047a90` (model from config snapshot, no hardcoded default)
- ✅ #4 fixed in `aaf7322` (config snapshot at job creation)
- 🟡 #5 open (no commit in last 20 explicitly wiring `chunk_size_tokens` into chunker runtime path)
- ℹ️ #6 operational rule, not code defect
- ✅ #7 fixed in `bd27d30` (`get_job()` snapshot copy, no live mutable reference leak)
- ✅ #8 fixed in `ba1cda6` (single queue path, dead `_get_queue` removed)
- ✅ #9 fixed/mitigated in `1edfb4e` (legacy checkpoints marked as legacy/non-active)
- 🟡 #10 open (no commit in last 20 that routes `/config` through `validate_preflight()`)
- 🟡 #11 open (no explicit guardrails hard-cap commit for range AI path)
- 🟡 #12 open (no explicit fail-fast or `DONE_WITH_WARNINGS` policy commit)
- 🟡 #13 open/partial (base cancel fixed by #1, but deep network-call cancellation policy still not explicitly completed)
- ✅ #14 fixed in `f047a90` (+ related config-snapshot cleanup in `aaf7322`)
- ✅ #15 fixed in `b57dd87` (worker exception now handled, avoid stuck job)
- ✅ #16 fixed in `8a5ca7c` (`mkdir` and logger init moved inside `try`)

## 1) Cancel button lie (very bad)

User press cancel.  
Backend set `job.cancelled = true`.  
But pipeline no check this flag in real work phases.  
Work keep run: convert, check, validate, summary.  
User think stop. Machine keep burn CPU and model time.

Why bad:
- User trust broken.
- Resources waste.
- Can write output after user asked stop.

Caveman fix:
- Put cancel check before each big phase (`convert/check/validate/summary`).
- Put cancel check inside long loops.
- If cancelled: stop now, set status `CANCELLED`, save partial only if policy says.
- Make one helper: `ensure_not_cancelled(job)`.

Fix estimate:
- Size: M
- Time: 4-8h

## 2) Status can show done after cancel (very bad)

Cancel flag set, but no hard stop flow.  
Job can still end with `DONE`, not `CANCELLED`.  
UI and reality fight each other.

Why bad:
- Audit/history wrong.
- Ops cannot know if job truly cancelled.

Caveman fix:
- After cancel event, never allow final status `DONE`.
- Add strict status transition map:
  - `PENDING -> PROCESSING -> DONE/ERROR/CANCELLED`
  - `CANCELLED` is terminal, no more changes.
- Add tests for status transitions.

Fix estimate:
- Size: S-M
- Time: 2-4h (after bug #1 fix)

## 3) Wrong model used in pipeline calls (very bad)

Async call function has default model `"local-model"`.  
Orchestrator not pass configured model from runtime config/env.  
Request can go to non-existing model or wrong model.

Why bad:
- Random failures.
- Quality drift.
- Debug hard because config says one model, runtime uses another.

Caveman fix:
- Remove hardcoded `"local-model"` fallback for pipeline path.
- Pass model explicitly from config/snapshot to every AI call.
- Log model name in `run.log` at start of each phase.
- Fail fast if model empty or unknown.

Fix estimate:
- Size: M
- Time: 3-6h

## 4) Queue config race (very bad)

Job created now, but config read later when worker starts.  
If user change config while job waiting, old job run with new config.  
One user action can mutate many queued jobs.

Why bad:
- Non-deterministic results.
- Repro impossible.
- Dangerous in batch workloads.

Caveman fix:
- When job created, copy full config into job snapshot.
- Worker uses only snapshot, not global live config.
- Show snapshot hash/id in logs for reproducibility.
- New config affects only new jobs.

Fix estimate:
- Size: M-L
- Time: 6-12h

## 5) `chunk_size_tokens` from UI ignored (high)

Config has `chunk_size_tokens`.  
Tokenizer module reads env once at import.  
Pipeline never inject per-job chunk size into chunking logic.  
User slider/text change no effect for running behavior.

Why bad:
- UI promise false.
- Context overflow or poor splitting cannot be tuned per job.

Caveman fix:
- Stop using import-time global `_MAX_TOKENS` for runtime decisions.
- Give chunker explicit `chunk_size_tokens` argument from job snapshot.
- Validate min/max once, then use exactly that value in split.
- Log chosen chunk size.

Fix estimate:
- Size: M
- Time: 4-8h

## 6) Cleanup is user duty (not service bug in this setup)

In this project mode, service writes artifacts to mounted user/output directory.  
Service must NOT auto-delete user files.  
User/operator cleans results manually by own policy.

Current behavior is acceptable for your rules:
- service saves output,
- user owns output,
- user cleans when needed.

Note:
- keep this as operational rule in docs,
- do not treat as critical code defect.

Caveman fix:
- Write clear ops rule in README: user owns cleanup.
- Optional: add manual cleanup script command for operator convenience.

Fix estimate:
- Size: XS (docs only)
- Time: 0.5-1h

## 7) Shared mutable job object race (high)

`get_job()` returns live mutable object.  
Many coroutine paths mutate same object fields.  
No snapshot/update transaction boundary per operation.

Why bad:
- Lost updates.
- Progress jumps backward/forward.
- Intermittent ghost states hard to reproduce.

Caveman fix:
- Do not mutate shared job object from many places directly.
- Use one update function with lock and patch/delta model.
- Return immutable snapshots to readers.
- Add monotonic guards for progress fields.

Fix estimate:
- Size: L
- Time: 1-2 days

## 8) Queue API split brain (high)

`jobs.py` has queue wrapper functions (`get_next_job_id`, `complete_active_job`, `task_done`).  
But worker loop uses raw queue directly (`_get_queue().get()` + direct task_done).  
Two queue control styles coexist.

Why bad:
- Dead/unused path.
- Internal `_active_job_id` bookkeeping can desync from real worker flow.
- Maintenance trap.

Caveman fix:
- Choose one queue API only.
- Option A: use wrapper functions everywhere.
- Option B: delete wrappers and keep direct queue usage.
- Remove unused fields/functions after decision.

Fix estimate:
- Size: M
- Time: 4-8h

## 9) Dead code island: legacy checkpoints vs new pipeline (high)

Repo keeps checkpoint framework:
- `checkpoints/*`
- `PerSectionCheckpoint`
- `JobCancelledError` flow

But runtime path uses `pipeline_orchestrator` directly for check/validate/summary.  
Legacy path mostly not driving current execution.

Why bad:
- Team thinks feature exists because code exists.
- Fix can be made in wrong subsystem.
- Bugfix effort split across dead and live paths.

Caveman fix:
- Decide: keep legacy checkpoints or delete.
- If keep: mark clearly `legacy`, not in active flow.
- If delete: remove checkpoint code and old cancel exception path.
- Update docs and architecture diagram same PR.

Fix estimate:
- Size: M-L
- Time: 1-2 days (with regression check)

## 10) `validate_preflight()` exists but runtime not using it (high)

`config_store.validate_preflight()` has richer checks.  
Main `/config` path calls `validate_and_set()` directly, not that preflight function.  
So expected safety checks in one place are bypassed in real flow.

Why bad:
- Drift between intended validation and actual validation.
- Future contributor gets false confidence.

Caveman fix:
- Use one validation entrypoint in runtime.
- Either call `validate_preflight()` from `/config`, or remove function.
- No duplicate validation rules in two places.
- Add tests for config invalid cases.

Fix estimate:
- Size: S-M
- Time: 2-6h

## 11) Range validation can stress model path (high)

Range endpoint may invoke LLM parse for user text.  
No strict hard cap/guardrail path at entry for abusive payloads before AI call.  
Can generate expensive model traffic under spam or bad clients.

Why bad:
- Model resource pressure.
- Latency spikes for normal users.

Caveman fix:
- Add hard input length cap for range text.
- Add cheap regex pre-parse first; call AI only on hard cases.
- Add rate limit/budget for AI range validation path.
- Return friendly error when input too large.

Fix estimate:
- Size: S
- Time: 2-4h

## 12) Partial failure policy weak in parallel check (high)

If one worker/server fails, code records error text and continues.  
Pipeline can still finish as done with mixed-quality sections.  
No clear threshold/fail-fast policy.

Why bad:
- “DONE” may hide degraded result quality.
- Operator cannot quickly distinguish healthy run vs wounded run.

Caveman fix:
- Define policy:
  - fail-fast on worker errors, or
  - mark `DONE_WITH_WARNINGS`.
- Count failed sections and expose in status/result.
- Put clear warning banner in final report.

Fix estimate:
- Size: M
- Time: 4-8h

## 13) Cancellation semantics not propagated to deep tasks (high)

Even if top-level wants cancel, long network/model call may continue until timeout/response.  
No cooperative cancellation points around every expensive step.

Why bad:
- Slow stop behavior.
- User waits long after cancel click.

Caveman fix:
- Add cooperative cancellation around network calls.
- Use smaller call timeouts with retry policy aware of cancel.
- Before each retry, check cancel flag.
- For long phase loops, poll cancel often.

Fix estimate:
- Size: M
- Time: 4-8h (partially covered by #1)

## 14) Runtime behavior not single source of truth (high)

Config/env/default/model-selection split across modules:
- API layer
- Orchestrator
- AI client defaults
- Token chunker import-time state

Pieces not harmonized per job.

Why bad:
- Surprising behavior.
- Hard incident response.

Caveman fix:
- Create one runtime config object as single source of truth.
- Build it once per job snapshot; pass down explicitly.
- Remove hidden defaults scattered in modules.
- Print effective runtime config at job start (safe fields only).

Fix estimate:
- Size: L
- Time: 1-2 days

## 15) ~~Worker swallow exception, job stuck forever~~ ✅ FIXED

`_pipeline_worker` in `main.py` calls `pipeline_orchestrator.run()`.  
If run throws exception: worker logs error but never sets `job.status = ERROR`.  
Job stays `PROCESSING` or `PENDING` in store forever.  
User sees stuck job. Queue blocks. No recovery until restart.

Also: worker uses raw `q.get()` directly, not `job_store.get_next_job_id()`.  
So `_active_job_id` and `_waiting` bookkeeping never updated.  
`complete_active_job()` never called.  
Queue position math broken for all waiting jobs.

Why bad:
- Ghost job blocks queue.
- User cannot know real status.
- No recovery without full container restart.
- Masks all pipeline errors — looks like hang, not crash.

Caveman fix:
```python
try:
    await pipeline_orchestrator.run(job, cfg, servers)
except Exception as exc:
    logger.error("worker unhandled error job %s: %s", job_id, exc, exc_info=True)
    job = job_store.get_job(job_id)
    if job is not None:
        job.status = JobStatus.ERROR
        job.error = str(exc)
        job_store.update_job(job)
finally:
    job_store.complete_active_job()
    q.task_done()
```
Also switch from `q.get()` to `job_store.get_next_job_id()` to keep bookkeeping correct.

Fix estimate:
- Size: S
- Time: 1-2h

## 16) ~~`mkdir` before try block, filesystem error escapes handler~~ ✅ FIXED

`pipeline_orchestrator.py` `run()` calls `artifact_dir.mkdir()` before `try:` block.  
If path is read-only or invalid: `OSError` raised, escapes `try/except`.  
Exception propagates to worker (bug #15 territory).  
Job never marked ERROR by orchestrator itself.  
`ArtifactLogger` never created, `log.close()` in `finally` crashes with `NameError`.

Why bad:
- Filesystem errors completely bypass error reporting.
- User gets no feedback, job hangs.
- `finally: log.close()` throws `NameError` because `log` never assigned.
- Compound failure: two crashes for one bad path.
- Historical incident: read-only filer mount caused stuck pending job (fixed in deployment defaults by writable backend mounts).

Caveman fix:
```python
log: ArtifactLogger | None = None
try:
    artifact_dir.mkdir(parents=True, exist_ok=True)  # ← moved inside try
    log_path = str(artifact_dir / "run.log")
    log = ArtifactLogger(log_path)
    ...
except Exception as exc:
    job.status = JobStatus.ERROR
    job.error = str(exc)
    update_job(job)
finally:
    if log:
        log.close()
```

Fix estimate:
- Size: XS
- Time: 0.5h

## Caveman order (hardest first)

L (hardest, first think hard):
1. #7 Shared mutable job object race.
2. #9 Dead code island: legacy checkpoints vs new pipeline.
3. #14 Runtime behavior not single source of truth.
4. #4 Queue config race.

M (medium hard):
5. #1 Cancel button lie.
6. #8 Queue API split brain.
7. #5 `chunk_size_tokens` from UI ignored.
8. #12 Partial failure policy weak in parallel check.
9. #13 Cancellation semantics not propagated to deep tasks.
10. #3 Wrong model used in pipeline calls.

S (small):
11. #2 Status can show done after cancel.
12. #10 `validate_preflight()` exists but runtime not using it.
13. #11 Range validation can stress model path.

XS (tiny / docs rule):
14. #6 Cleanup is user duty (operational docs only).
15. #16 `mkdir` before try block (0.5h fix, confirmed caused real incident).

S (small, fix fast):
16. #15 Worker swallow exception, job stuck forever.
17. #2 Status can show done after cancel.
18. #10 `validate_preflight()` exists but runtime not using it.
19. #11 Range validation can stress model path.
