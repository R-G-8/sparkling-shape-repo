# Design review: numbawatchd (web)

Run with the `apple-design` skill (`.claude/skills/apple-design`, invoked as
`/apple-design`), November 2026. Scope: `base.html`, home, login, signup,
dashboard, plus the A/B page for regressions. Platform: Django web app on Pico
CSS, viewed in desktop and mobile browsers.

Because this is a web app, Apple's principles and foundations apply
(accessibility, color, typography, layout, writing) but iOS and macOS platform
conventions such as tab bars, the menu bar and sheets do not.

Guideline pages read: `accessibility.md`, `layout.md`, `typography.md`,
`color.md`, `dark-mode.md`, `branding.md`, `buttons.md`, `entering-data.md`,
`text-fields.md`, `writing.md`.

## Summary

**Before: Needs work.** The pages were clean and accessible enough out of the
box, because Pico's defaults pass contrast. They had no point of view, though:
stock Pico blue, a generic layout, and nothing tying the look to a product
about *ranking* what you watched. A few layout and form problems showed up on
real content.

**After: Good.** There are no Critical findings and no open High findings. The
thesis is *"your watch history, ranked"*. The design's signature is the rounded
rank numeral, used only on real sequences.

## Findings and fixes

### High

- **Dashboard title broke mid-word on phones.** The page title was
  "Welcome, member@example.com" at 40px. On a 390px-wide screen it wrapped as
  "member@example.co / m".
  `layout.md › Adaptability`: "Design a layout that adapts gracefully and
  consistently."
  **Fix:** the title is now "Welcome", with "Signed in as …" in a secondary
  line below it. Titles also get `overflow-wrap: anywhere`.
- **Templated, with no point of view.** The colors, type and spacing were
  Pico's defaults, so the app could have been any app.
  `branding.md › Best practices`: "Express your brand with familiar
  components."
  **Fix:** a token system (below). It keeps standard controls and puts the
  identity into one element: rank numerals in the rounded system font, shown in
  the accent color.
- **Signup form put hints between the label and the field.** Django's
  `as_div` output put the username hint, and a four-item password list,
  between each label and its input. As a result, the "Password" label sat
  about 180px above its field.
  `text-fields.md › Best practices`: "leave enough space between them so
  people can easily see which input field belongs with each introductory
  label."
  **Fix:** a new shared `registration/_field.html` renders the label, then the
  field, then errors, then the hint. Hints are footnote-sized secondary text and
  stay linked to the field through `aria-describedby`.

### Medium

- **Text fields and buttons spanned the full 1160px container.**
  `text-fields.md › Best practices`: "match the size of a text field to the
  quantity of anticipated text."
  **Fix:** the auth pages now use a 26rem card, and body copy is held to a
  34rem measure.
- **Body text scaled up to 20px on wide screens** (Pico scales the root size by
  breakpoint).
  `typography.md › Ensuring legibility`: the default text size on mobile is
  17pt.
  **Fix:** the body is a fixed 17px (`106.25%`), so it still follows the
  browser's text-size setting. Headings follow Apple's text styles: Large Title
  34, Title 1 28, Title 2 22.
- **Touch targets were below 44pt on phones.** The nav "Log out" button was
  about 36px tall and the nav links about 40px.
  `accessibility.md › Mobility`: the default control size on iOS is 44x44pt.
  **Fix:** on coarse pointers and phone widths, controls are at least 44px
  tall. On desktop they are 36px or more (the macOS default is 28pt).
- **The hero buttons were 6px apart.**
  `accessibility.md › Mobility`: "about 12 points of padding around elements
  that include a bezel."
  **Fix:** the buttons now sit in an `.actions` row with a 12px gap.
- **The login error looked like body text.**
  `writing.md`: "display it as close to the problem as possible … be clear
  about what someone can do."
  **Fix:** the error is now a tinted callout above the fields. The copy reads
  "That username and password don't match. Check both and try again."

### Low

- **"Coming in Sprint 2" was team jargon on a user-facing page.** It now reads
  "Coming soon" and is shown as a status pill: text, not color alone.
- **Outline buttons and field borders were low-contrast.** Field and outline
  borders now reach at least 3:1 against the card (WCAG non-text contrast).
- **The browser chrome didn't match the page.** Added `color-scheme` and a
  `theme-color` for each appearance.

## Token system

Every color has a light value, a dark value and an Increase Contrast
(`prefers-contrast: more`) value. Each ratio below is measured against the
surface it sits on.

| Token | Light | Dark | Role |
| --- | --- | --- | --- |
| `--nw-surface` | `#f5f5f7` | `#000000` | page background |
| `--nw-card` | `#ffffff` | `#1c1c1e` | cards, fields |
| `--nw-content` | `#1d1d1f` (16.8:1) | `#f5f5f7` (15.6:1) | text |
| `--nw-secondary` | `#6e6e73` (5.1:1) | `#a1a1a6` (6.6:1) | secondary text |
| `--nw-accent` | `#4b44d0` (6.9:1) | `#a09cff` (7.0:1) | links, primary buttons, rank numerals |
| button fill | `#4b44d0`, white text 6.9:1 | `#5552e0`, white text 5.7:1 | primary button |
| `--nw-signal` | `#c4001a` (6.3:1) | `#ff6b6b` (6.1:1) | errors only |

- **Type:** the system font stack (SF Pro on Apple devices) carries all UI and
  body text. `ui-rounded` (SF Pro Rounded) carries only the wordmark and the
  rank numerals.
- **Signature:** `.ranked`, an ordered list with large rounded numerals in the
  accent color. It is used only for real sequences: "How it works" on the home
  page and "Get started" on the dashboard. The list carries `role="list"` so
  Safari keeps list semantics after `list-style: none`.
- **Material:** the sticky header is the only translucent surface, because it
  is the floating, functional layer. With `prefers-reduced-transparency` it
  turns solid.
- **Motion:** there is one press state (`scale(0.98)`), and it is off under
  `prefers-reduced-motion`.
- **Appearance** follows the system setting. There is no in-app toggle
  (`dark-mode.md › Best practices`).

## What works

- **Copy is short and action-oriented:** "Create an account", "Log in", "Go to
  your dashboard".
- **The hero headline already had a thesis.** The redesign only gives it room.
- **Pico's semantic HTML** (`article`, `nav`, real `<button>`s and labels) gives
  correct screen-reader structure without extra work.

## A/B test note

The A/B page (`/e1531ff`) was not edited, but the global theme restyles its
button: it is now a capsule in the accent color. Both variants (`kudos`,
`thanks`) get the identical style, so the comparison between the two arms stays
fair. Clicks recorded before and after this change are not directly comparable,
so deploy it at a clean cut point in the experiment.

## Using the skill

```text
/apple-design Review <template or screenshot>. Django web app with Pico CSS.
/apple-design Make <page> less generic. Keep the tokens in static/css/site.css.
```

New screens should reuse the tokens in `static/css/site.css` rather than raw
hex values. They should reuse `.ranked`, `.status`, `.actions` and
`registration/_field.html`, and keep the accent color for interactive elements
and ranks only.
