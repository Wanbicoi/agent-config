---
name: grilling
description: Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, or uses any 'grill' trigger phrases.
---

GRL-01: Interview the user relentlessly until you reach a shared understanding. Map this as a **design tree**: every decision branches into the decisions that hang off it.

GRL-02: Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask _now_ without guessing at answers you haven't heard yet. Ask the whole frontier in one round with the `AskUserQuestion` tool, at most 4 questions per call (an agent without it asks the same questions as a numbered list, each with its recommendation), then wait for the answers before the next round.

GRL-03: One question per decision: the title in `header`, the context the user needs in `question`, your recommendation as the first option labelled `(Recommended)`, so picking it is the "yes".

GRL-04: Close every round with one more question, `header` "Anything else?": the user adds input the frontier missed (a constraint, a correction, a new branch) through "Other"; the first option, `(Recommended)`, is "Nothing to add". An answer reshapes the tree.

GRL-05: A frontier beyond 4 questions goes out as consecutive calls, all before you recompute the tree: still one round.

GRL-06: Each round the user answers reshapes the tree: settled decisions push the frontier outward and unblock questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a _later_ round, not this one.

GRL-07: Finding _facts_ is your job, never the user's. When a frontier question needs a fact from the environment (filesystem, tools, etc.), dispatch a sub-agent to find it; don't ask the user for anything you could look up yourself. Don't block on it: a running exploration is an unsettled prerequisite, so only the questions downstream of it wait for the sub-agent to report; ask the rest of the frontier now. The _decisions_ are the user's: put each to them and wait.

GRL-08: The session is done when the frontier is empty: every branch of the design tree visited, nothing left silently assumed. Do not act on it until the user confirms you have reached a shared understanding.
