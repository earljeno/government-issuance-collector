# Design System and Visual Direction

> Owns visual direction, design principles, design tokens, and aesthetic anti-patterns—not component code or workflow behavior. Use `UI.md` for interface implementation and accessibility, `UX.md` for user goals and interaction rules, and `COMPONENTS.md` for component architecture. Use for projects with a distinct visual language or custom design system; document existing tokens and rules rather than inventing unsupported facts.

## Purpose and visual direction

- **Visual identity:** [Purposeful, restrained, modern, dense, editorial, etc.]
- **Design priorities:** [e.g., Clarity > Hierarchy > Density > Consistency > Visual Polish]
- **Target environment:** [Desktop-first, mobile-responsive, embedded, kiosk, dark-mode default, etc.]

## Design tokens and foundations

Document where tokens are defined and how they are consumed:

- **Token source:** [Path to CSS variables, theme file, Tailwind config, design tokens JSON]
- **Color roles:**
  - Surface & background: [Roles/tokens for page, card, modal, subtle surfaces]
  - Text & foreground: [Primary, secondary, muted, disabled]
  - Primary / Brand: [Action colors, hover/active variants]
  - Feedback / Status: [Success, warning, danger/error, info]
  - Borders & dividers: [Default, subtle, focused]
- **Typography:**
  - Font families: [Primary, mono, heading fonts]
  - Scale & weights: [Scale convention: headings, body, captions, code]
  - Line height & letter spacing: [Verified conventions]
- **Spacing & sizing scale:** [Base unit e.g. 4px/8px, sizing tokens]
- **Elevation & radii:** [Shadow levels, corner radius tokens]

## Anti-slop visual rules

Guidelines to ensure the interface looks human-crafted and intentional, avoiding generic AI-generated aesthetics:

- **No decorative clutter:** Every element must serve information hierarchy or task completion. Avoid floating background blurs, gratuitous gradients, and decorative borders.
- **Respect contrast standards:** Ensure text meets WCAG AA contrast (4.5:1 for normal text, 3:1 for large text) against all backgrounds. Never sacrifice legibility for subtle aesthetic gray tones.
- **Avoid AI palette clichés:** Do not introduce unrequested purple/violet gradients or neon glows unless explicitly specified in brand guidelines.
- **Information density over empty space:** Do not inflate whitespace simply to fill screens. Present data efficiently with clear scannability.
- **Consistent visual weight:** Primary actions must stand out clearly. Secondary actions must not compete with primary buttons for attention.

## Layout and hierarchy

- **Page layouts:** [Layout structures: sidebar, top nav, multi-column, centered canvas]
- **Navigation:** [Placement, active item indication, breadcrumbs]
- **Content hierarchy:** [Heading progression, card layouts, table density]
- **Responsive behavior:** [Breakpoints and layout adaptation strategy]

## Anti-patterns

- **Token drift:** Hardcoding arbitrary hex values, margins, or font sizes instead of existing tokens.
- **Styling sprawl:** Introducing a second CSS framework or utility system when one is already in place.
- **Inaccessible subtle text:** Using low-contrast gray text on light/dark backgrounds that fails readability checks.
- **Inconsistent radii & spacing:** Mixing 4px, 8px, and 24px roundings arbitrarily across adjacent components.
- **Status communicated solely by color:** Showing red/green status dots without accompanying text, icons, or accessible labels.

## See also

- [UI.md](UI.md) — Implementation details, state handling, and component integration
- [COMPONENTS.md](COMPONENTS.md) — Component architecture, reuse hierarchy, and abstraction thresholds
- [UX.md](UX.md) — User journeys, interaction mechanics, and accessibility requirements
