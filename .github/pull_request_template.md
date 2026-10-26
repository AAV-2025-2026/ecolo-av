<!--
The title becomes the commit subject on main. Write what main gains, as a command,
72 characters at most: "Stop the spine when the Orin's heartbeat is stale".
Replace every comment below. How to write each part: CONTRIBUTING.md, section 6.
-->

## What and why

<!-- The problem, and why this is the fix, in 2 to 4 sentences. -->

## Issue / task

<!-- "Closes #12" closes the issue when this merges. Add the proposal's task: "Task: T3.6". -->

Closes #
Task:

## How I tested

<!--
The exact commands you ran and what happened. Say what you did NOT test.
  tools/test.sh: all passed
  pixi run sim, drove the route: stops within 1 m
  Not tested on the car.
-->

## Risk

<!-- What could break, and where: laptop, sim or car. "None" only if it's docs only. -->

## Screenshots

<!-- For the HUD, RViz or anything visual. Delete this section if not. -->

## Checklist

<!-- Tick only what you actually did. -->

- [ ] `tools/test.sh` passes on my laptop
- [ ] Tests cover the change
- [ ] `docs/interfaces.yaml` updated, if a topic, service or message changed
- [ ] `PROVENANCE.md` updated, if I changed inherited code
- [ ] Docs updated, if behaviour or a command changed
- [ ] A new or changed feature has its row in `docs/features.md`
- [ ] Docs changed? `pixi run docs`, and the HTML committed
- [ ] No secrets, build output or large data files
