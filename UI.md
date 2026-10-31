# UI Engineering

> Owns frontend/view implementation, rendering, styling integration, responsive behavior, and accessibility. Use `DESIGN.md` for visual direction and token definitions, `UX.md` for user goals and interaction behavior, and `COMPONENTS.md` for component boundaries and reuse. Use only for projects with a user interface; describe the existing system rather than imposing a new design system.

## UI stack and structure

- **Framework / rendering model:** [Verified stack e.g., React, Vue, Svelte, SSR, SPA, MPA]
- **Component organization:** [Path and composition conventions; see `COMPONENTS.md`]
- **Styling approach:** [Existing CSS, CSS modules, utility classes, tokens, or component library]
- **Form and validation approach:** [Existing client/server validation implementation]

## Design consistency

- Reuse established components, tokens, spacing, typography, and interaction patterns before creating new ones.
- Avoid introducing a second component library or styling system without explicit justification.
- Keep visual changes scoped to the requested experience; do not broadly restyle unrelated pages.
- Use the existing responsive breakpoints and test narrow as well as wide viewports.

## Accessibility

- Prefer semantic HTML and native controls when appropriate.
- Provide labels and accessible names for controls; preserve keyboard operation and visible focus.
- Do not communicate status through color alone.
- Ensure dialogs, menus, forms, and dynamic updates have suitable focus and screen-reader behavior.
- Check contrast and reduced-motion behavior according to the project's existing standards.

## States to account for

For key screens and controls, account for the states that apply to their actual lifecycle (see [UX.md](UX.md) for the 14-state inventory; not every state applies to every control):

- **Loading & submitting:** Skeletons, spinners, button pending states, and click prevention.
- **Empty & first-use:** Guidance when collections contain zero items.
- **Validation & system errors:** Inline field feedback and accessible error alerts.
- **Disabled, unauthorized & offline:** Appropriate visual cues, role gates, and connectivity status.
- **Success & confirmation:** Feedback toasts, banners, and undo mechanics.

## UI validation

- [Verified build, lint, test, or visual-check commands]
- [Browser/device support confirmed by the project]
- [Relevant accessibility checks]

## Anti-patterns

- **Styling sprawl:** Adding arbitrary inline CSS or new utility classes that diverge from existing tokens.
- **Framework fragmentation:** Introducing another UI or component library alongside the established one.
- **Unresponsive layouts:** Developing solely for desktop screen widths and breaking mobile/tablet viewports.
- **Keyboard traps:** Modal dialogs or dropdowns where focus cannot be moved or closed via keyboard (`Esc`/`Tab`).
- **Silent render crashes:** Omitting error boundaries in complex view hierarchies, causing full-page white screens.

## See also

- [DESIGN.md](DESIGN.md) — Visual direction, color tokens, typography, and anti-slop rules
- [COMPONENTS.md](COMPONENTS.md) — Component architecture, reuse hierarchy, and props standards
- [UX.md](UX.md) — User journeys, HCI principles, and complete 14-state specifications
- [TESTING.md](TESTING.md) — Frontend testing, interaction tests, and accessibility verification
