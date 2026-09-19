# Thai Car Intelligence — Design System

**Version:** 1.0
**Date:** 2026-09-19
**Aesthetic:** Editorial automotive intelligence — restrained, technical, information-dense, calm.

## Design Principles

1. **Editorial hierarchy** — inspired by automotive research databases and technical magazines, not SaaS templates
2. **Information density over decoration** — every pixel carries meaning
3. **Thai-first** — typography, spacing, and copy optimized for Thai script
4. **Evidence over badges** — provenance looks like research metadata, not AI sparkle
5. **Calm confidence** — no visual urgency, no gradient hero sections

## Color Roles

| Role | Token | Value | Usage |
|------|-------|-------|-------|
| Surface | `--surface` | `#fafafa` | Page background |
| Card | `--card` | `#ffffff` | Card backgrounds |
| Border | `--border` | `#e5e5e5` | Dividers, card edges |
| Text primary | `--text` | `#171717` | Headings, body |
| Text secondary | `--text-secondary` | `#525252` | Labels, metadata |
| Text muted | `--text-muted` | `#a3a3a3` | Timestamps, empty states |
| Accent | `--accent` | `#1d4ed8` | Links, active states, verified indicators |
| Verified | `--verified` | `#15803d` | Verified data, success |
| Qualified | `--qualified` | `#d97706` | Partial confidence, warning |
| Insufficient | `--insufficient` | `#737373` | Missing data |
| Research | `--research` | `#7c3aed` | Research-only observations |
| Danger | `--danger` | `#dc2626` | Errors, deletions |

## Typography Scale

| Level | Size | Weight | Line Height | Usage |
|-------|------|--------|-------------|-------|
| Display | 2.25rem | 700 | 1.2 | Page titles (rare) |
| H1 | 1.875rem | 700 | 1.25 | Section headings |
| H2 | 1.5rem | 600 | 1.3 | Subsection headings |
| H3 | 1.125rem | 600 | 1.4 | Card titles, spec group headers |
| Body | 1rem | 400 | 1.5 | Main content |
| Small | 0.875rem | 400 | 1.5 | Labels, metadata |
| Caption | 0.75rem | 400 | 1.5 | Timestamps, provenance |

Thai font stack: `'IBM Plex Sans Thai', 'Noto Sans Thai', -apple-system, sans-serif`

## Spacing Scale (4px base)

4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96

## Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 2px | Inline badges, code |
| `--radius-md` | 4px | Buttons, inputs |
| `--radius-lg` | 6px | Cards, dropdowns |
| `--radius-xl` | 8px | Modals, large cards |

Minimal radius. No pill shapes except for status dots.

## Shadows

| Token | Usage |
|-------|-------|
| None | Default cards (border-separated) |
| `0 1px 3px rgba(0,0,0,0.08)` | Elevated cards (hover only) |

No heavy shadows. Cards separated by borders, not elevation.

## Layout

- Container max-width: 1200px (main content), 1440px (wide)
- Grid: 12-column, 24px gutter
- Sidebar: 320px on detail pages
- Mobile: single column, 16px padding

## Components

### Card
- White background, 1px border (`--border`), 6px radius
- No shadow by default; subtle shadow on hover for interactive cards
- Padding: 24px
- Header: border-bottom separator, not background color change

### Badge (Status)
- 2px radius, small text (12px), uppercase tracking
- Verified: green border + green text
- Qualified: amber border + amber text
- Insufficient: gray border + gray text
- Research: purple border + purple text
- No fill backgrounds — border + text only for subtlety

### Button
- Primary: dark blue fill, white text, 4px radius
- Secondary: white fill, gray border, gray text
- Ghost: no fill, no border, gray text
- No rounded-full buttons

### Spec Table
- Alternating row backgrounds (white / `--surface`)
- Left-aligned labels, right-aligned values
- Thin 1px borders between rows
- Group headers: small caps, muted text, border-top

### Evidence/Provenance
- Inline marker: colored dot (4px) + small text
- Source links: underlined, muted color, open in new tab
- Timestamps: relative (e.g., "3 วันที่แล้ว") + absolute on hover

### Filter Bar
- Horizontal row of compact selects/inputs
- Background: transparent
- Borders: 1px `--border`
- Active filter: accent border

## Responsive Breakpoints

| Name | Width | Columns |
|------|-------|---------|
| Mobile | < 640px | 1 |
| Tablet | 640–1024px | 2 |
| Desktop | > 1024px | 3-4 |

## Loading/Empty/Error States

- **Loading:** subtle pulse animation on skeleton placeholders (gray rectangles)
- **Empty:** centered icon + muted text, no decorative illustrations
- **Error:** red text + retry button, no error details exposed to user

## Thai Copy Conventions

- Use "ครับ/ค่ะ" only in conversational AI responses, not UI labels
- UI labels: noun-first (e.g., "ราคา" not "ราคาเท่าไหร่")
- Empty states: "ยังไม่มีข้อมูล" not "ไม่พบข้อมูล"
- Loading: "กำลังโหลด..." not "กรุณารอ"
