# What People Can Do With RAD

RAD separates four things: a person states a goal, an LLM proposes a plan, governed engines or
plugins compute over approved data, and deterministic checks decide whether the result passed.
The user does not need to be an AI engineer.

| Person | What they ask | Data they provide | What RAD returns |
|---|---|---|---|
| Small-business owner | Compare staffing or purchasing scenarios | CSV exports, constraints, budget limits | Approved recommendation, assumptions, alternatives, evidence |
| Warehouse manager | Allocate inventory to priority orders | Bin stock, SKUs, order quantities, priorities, distances | Pick allocation, shortages, travel comparison, evidence dossier |
| Finance team | Review a capital allocation | Current approved return/risk snapshot and policy limits | Non-transactional weights, risk measures, baseline comparison |
| Software team | Build or repair an application | Repository, requirements, tests, deployment constraints | Plan, bounded edits, test results, verification evidence |
| Researcher | Analyze a question | Papers, datasets, methods, hypotheses | Source-grounded plan, deterministic analysis, limitations |
| Teacher | Prepare or assess material | Curriculum, rubric, learner level, source material | Reviewable lesson/assessment plan and checked artifacts |
| Healthcare administrator | Analyze operations—not diagnose patients | De-identified schedules, capacity and policy constraints | Operational scenarios with explicit safety boundaries |
| Manufacturer | Plan production or maintenance | Orders, machines, capacity, downtime and due dates | Feasible schedule recommendations and constraint failures |
| Cloud/platform engineer | Compare bounded compute placements | Workload sizes, regions, budgets, latency/carbon policies | Placement scenarios; no cloud deployment without another approval |

## After connecting an LLM

Connecting Ollama, OpenAI, Anthropic, or another supported provider gives RAD a reasoning engine.
The LLM can interpret natural language and propose structured work, but it does not receive blanket
authority. A normal session is:

1. The user states an outcome: “allocate today’s stock to urgent orders.”
2. The user attaches or references allowed data: JSON, CSV, documents, or a repository.
3. RAD asks the LLM to produce a constrained plan and validates its schema.
4. RAD shows the exact inputs, assumptions, operations, risks, permissions, cost bounds, and tests.
5. A person approves that exact digest.
6. Qualified deterministic engines or sandboxed plugins process the structured data.
7. RAD verifies acceptance criteria and produces results plus tamper-evident evidence.
8. Any real-world write—WMS update, trade, email, deployment, purchase—requires its own qualified
   connector, policy decision, and separate approval.

The data depends on the job. Text helps the model understand intent; structured snapshots feed
engines; files and repositories feed bounded tools. Secrets are supplied only as opaque references,
never pasted into prompts or packages.
