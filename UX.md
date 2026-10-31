# User Experience Requirements

> Owns user goals, journeys, interaction behavior, system states, and recovery paths—not visual tokens or frontend implementation. Use `DESIGN.md` for visual direction and tokens, `UI.md` for interface implementation and accessibility, and `COMPONENTS.md` for component boundaries and reuse.

## Primary user journeys

| User / actor | Goal | Entry point | Successful outcome | Failure / recovery path |
|---|---|---|---|---|
| [Actor] | [Goal] | [Entry path] | [Observable success] | [Clear error & recovery] |

## Evidence-based UX principles

- **Problem before solution:** Identify observable user friction or task failure before altering an existing workflow.
- **Ban subjective redesigns:** Avoid arguments like "this looks cleaner" or "it feels better." Ground UX changes in error reduction, interaction efficiency, or cognitive clarity.
- **Preserve mental models:** Respect user expectations and established conventions. Do not reorder buttons or swap navigation paradigms without concrete rationale.
- **Preserve user work:** Never wipe out form fields, text drafts, or uploaded items when a validation error or network disconnect occurs.

## Key HCI principles for implementation

- **Fitts's Law (Target Accessibility):** Ensure interactive targets are adequately sized (minimum 44×44px for touch) and placed within natural reach zones.
- **Hick's Law (Decision Simplicity):** Reduce cognitive load by limiting the number of choices per view. Use progressive disclosure for advanced or secondary settings.
- **Recognition over Recall:** Show relevant options and context on screen rather than expecting users to remember details from previous screens.
- **Timely Feedback:** Provide prompt acknowledgement for user actions and visible progress for operations that take long enough to create uncertainty. Treat values such as 100ms for acknowledgement or 300ms for loading feedback as heuristics, not universal pass/fail requirements; choose and document thresholds appropriate to the platform, operation, latency, and user expectations. Long-running work should communicate progress or status and, where feasible, allow cancellation or safe recovery.
- **Reversibility & Forgiveness:** Provide confirmation for irreversible or destructive actions, and offer undo options for state changes where feasible.

## Comprehensive state handling

Use this list as a state inventory for critical flows, screens, and compound controls. Select the states that can actually occur in each context; do not force every state onto every control. Document the expected behavior for applicable states, and omit irrelevant states rather than creating empty or misleading UI.

1. **Initial / Idle:** Default resting state before user interaction.
2. **Loading / Fetching:** Initial data retrieval; use skeletons or subtle spinners.
3. **Submitting / Pending:** Form submission or mutation in progress; disable double clicks.
4. **Success / Confirmed:** Explicit feedback acknowledging completion.
5. **Empty (Zero Data):** Helpful guidance when no items exist (call to action to create).
6. **Empty (No Results):** Specific feedback when a search or filter yields zero items.
7. **Validation Error:** Inline feedback adjacent to the input explaining how to fix it.
8. **Server / Network Error:** Actionable message indicating system failure and retry option.
9. **Partial Error:** Clear reporting when batch or multi-step operations partially succeed.
10. **Disabled / Read-Only:** Visual indication of unmodifiable state with tooltip explanation if relevant.
11. **Unauthorized / Forbidden:** Explanation of required role or permissions rather than a blank screen.
12. **Offline / Disconnected:** Indication of network interruption with local persistence if supported.
13. **Stale / Revalidating:** Background refresh while showing existing cached data.
14. **Conflict:** Clear resolution interface when concurrent edits collide.

## Content and microcopy

- **Clarity over jargon:** Use direct, human language. Replace system codes (`ERR_502_BAD_GATEWAY`) with user-friendly recovery instructions.
- **Consistent vocabulary:** Use identical terms for identical concepts across all screens (e.g., do not alternate between "Delete", "Remove", "Erase", and "Trash").
- **Actionable errors:** Every error message must answer two questions: *What happened?* and *What can I do now?*

## Anti-patterns

- **Form wipeout:** Reloading the page on server validation error and clearing all fields the user typed.
- **Invisible errors:** Showing a validation error at the top of a page that is scrolled out of the user's viewport.
- **Double submission traps:** Failing to disable a submit button while an async transaction executes, creating duplicate charges or records.
- **Dead-end errors:** Displaying "An error occurred" with no retry button, help link, or back navigation.
- **Confirmations for trivial actions:** Interrupting users with modal confirmations for non-destructive, easily reversible actions.

## See also

- [DESIGN.md](DESIGN.md) — Visual tokens, layout hierarchy, and design system foundations
- [UI.md](UI.md) — Frontend framework rendering, responsive views, and styling
- [COMPONENTS.md](COMPONENTS.md) — Reusable component architecture and state implementations
