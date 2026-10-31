# Agent Guidelines

## UI, UX, and Design Directives
When planning, implementing, reviewing, or modifying any user interface, user experience, copy, or styling in this project, consult the following source-of-truth documents:

1. **Visual Direction & Tokens**: [DESIGN.md](DESIGN.md)
   - Visual identity, design priorities, design tokens (colors, typography, spacing, elevation).
   - Anti-slop visual rules and aesthetic anti-patterns.
2. **UI Implementation**: [UI.md](UI.md)
   - Frontend stack, component patterns, styling approach, and accessibility standards.
   - Form validation, responsive behavior, and interface state handling.
3. **UX & Interaction Behavior**: [UX.md](UX.md)
   - Primary user journeys, evidence-based UX principles, and HCI heuristics (Fitts's Law, Hick's Law).
   - 14-state comprehensive inventory (Idle, Loading, Submitting, Success, Empty, Errors, etc.) and microcopy guidelines.

<!-- antislop:start -->
## antislop
For UI, copy, people, mobile layout, or code comments work, read `.agents/skills/antislop/SKILL.md` (core) and then the skill for the task:
- UI / visual: `.agents/skills/antislop-ui/SKILL.md`
- Copy & text: `.agents/skills/antislop-copywriting/SKILL.md`
- People: `.agents/skills/antislop-human/SKILL.md`
- Mobile / responsive: `.agents/skills/antislop-layoutmobile/SKILL.md`
- Code comments: `.agents/skills/antislop-code/SKILL.md`
Before starting, follow the core's "Two Usage Modes" section in strict order: explicit session instruction first, then global preference, then ask. A session instruction always wins. For a resolved mode, say `antislop active: <mode> (session override).` or `antislop active: <mode> (global preference).` once before presenting findings or making edits, using the actual mode and source. Acknowledging the user's request without naming the source does not replace this notice.
Only an explicit choice of antislop during or after selects a session mode. A request to review, audit, or avoid file edits does not select a mode; read the global preference in that case. Another skill's mode does not select antislop's mode.
If the mode is unresolved, ask during/after and end the response; wait for the answer before any UI review, planning, or concept. For read-only tasks, put the active-mode notice only at the start of the final answer, never in progress messages. For editing tasks, announce before the first edit and omit it from the final answer.
To update antislop later: download `antislop.md` again, or run `npx antislop-ai --update` if it was installed as skill folders.
<!-- antislop:end -->
