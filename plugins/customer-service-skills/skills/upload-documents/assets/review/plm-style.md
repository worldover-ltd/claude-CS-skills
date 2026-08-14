# Worldover Design Language (Tailwind)

A portable description of how our product looks, written in Tailwind terms.
No component library, no React, no icon package assumed — just utilities, tokens,
and the raw values behind them so you can port this anywhere.

Read the four principles first; they explain why the numbers are what they are.

---

## 1. Principles

**Dark chrome, light work surface.** Navigation and app frame are `bg-slate-900`.
The content area is `bg-white`, sitting on top of the dark frame with its
top-left corner rounded (`rounded-tl-2xl`), so the white surface reads as a page
laid over the shell. Never invert this: content is always white, chrome is
always dark.

**One neutral ramp, one accent.** Almost every surface, border, and text colour
is `slate-*`. Blue is the only accent and it means exactly one thing: this is
interactive, selected, or the primary action. Colour outside slate + blue is
reserved for status and for data-identity tags.

**Borders do the work, shadows whisper.** Structure comes from 1px hairlines,
not elevation. Where shadow is used it is very soft and tinted blue-grey, never
black. Only true overlays (modal, dropdown, tooltip, pinned table columns) get a
shadow you can notice.

**Compact type, generous air.** Body copy is 15px, dropping to 13px in dense
areas and 11px for meta, but line lengths are short and gaps are consistent.
Reads dense-but-calm rather than cramped.

---

## 2. Tailwind setup

### 2.1 Semantic colour tokens

Colours are exposed as CSS custom properties in HSL triplets and wired into the
theme as `hsl(var(--x))`, so surfaces can be restyled in one place. Put these on
`:root` in your base layer:

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --card: 0 0% 100%;
  --card-foreground: 222.2 84% 4.9%;
  --popover: 0 0% 100%;
  --popover-foreground: 222.2 84% 4.9%;
  --primary: 221 83% 53%;
  --primary-foreground: 210 40% 98%;
  --secondary: 210 40% 96%;
  --secondary-foreground: 222 47% 11%;
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
  --accent: 210 40% 96%;
  --accent-foreground: 222 47% 11%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 210 40% 98%;
  --border: 214 32% 91%;
  --input: 214 32% 91%;
  --ring: 221 83% 53%;
  --radius: 0.5rem;
}
```

Resolved: `primary` is blue-600 `#2563eb`, `muted`/`secondary`/`accent` are
slate-100 `#f1f5f9`, `muted-foreground` is slate-500 `#64748b`,
`border`/`input` are slate-200 `#e2e8f0`, `destructive` is red-500 `#ef4444`,
base radius 8px.

Apply the border token globally so nothing has to name it:

```css
@layer base {
  * { @apply border-border; }
  body { @apply bg-background text-foreground font-primary; }
  html {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
  }
}
```

### 2.2 Theme extension

```js
// tailwind.config
theme: {
  extend: {
    fontFamily: {
      primary: ["Inter", ...defaultTheme.fontFamily.sans],
      sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
      "space-grotesk": ['"Space Grotesk"', "sans-serif"],
      "hanken-grotesk": ['"Hanken Grotesk"', "sans-serif"],
    },
    colors: {
      background: "hsl(var(--background))",
      foreground: "hsl(var(--foreground))",
      card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
      popover: { DEFAULT: "hsl(var(--popover))", foreground: "hsl(var(--popover-foreground))" },
      primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
      secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
      muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
      accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
      destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
      border: "hsl(var(--border))",
      input: "hsl(var(--input))",
      ring: "hsl(var(--ring))",
      dark: "#222222",
      success: "#198754",
      info: "#0dcaf0",
      warning: "#ffc107",
      danger: "#dc3545",
    },
    borderRadius: {
      lg: "var(--radius)",
      md: "calc(var(--radius) - 2px)",
      sm: "calc(var(--radius) - 4px)",
    },
    boxShadow: {
      soft: "0px 3px 8px 0px rgba(172, 182, 195, 0.08)",
      custom:
        "0px 24px 9px rgba(172,182,195,0.01), 0px 13px 8px rgba(172,182,195,0.05), 0px 6px 6px rgba(172,182,195,0.09), 0px 1px 3px rgba(172,182,195,0.1), 0px 0px 0px rgba(172,182,195,0.1)",
      flying: "0px 4px 0px 0px #E2E8F0",
      "chat-bubble": "0px 6px 10px 0px #ACB6C317",
    },
    backgroundImage: {
      radial: "radial-gradient(circle, #F1F5F9 0%, #CDDDE8 100%)",
      "diagonal-stripes":
        "repeating-linear-gradient(45deg, #f1f5f9 0 1px, transparent 1px 4px)",
      "stripe-pattern-backwards":
        "repeating-linear-gradient(-45deg, #fff, #fff 3px, #f1f5f9 3px, #f1f5f9 4px)",
    },
    keyframes: {
      shimmer: { "0%": { backgroundPosition: "-700px 0" }, "100%": { backgroundPosition: "700px 0" } },
      fadeIn: { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
      fadeInUp: {
        "0%": { opacity: "0", transform: "translateY(-16px)" },
        "100%": { opacity: "1", transform: "translateY(0)" },
      },
      float: { "0%, 100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-2px)" } },
    },
    animation: {
      shimmer: "shimmer 1.3s linear infinite",
      fadeIn: "fadeIn 200ms ease-out forwards",
      fadeInUp: "fadeInUp 0.6s ease-out forwards",
      float: "float 1.8s ease-in-out infinite",
    },
  },
},
plugins: [require("@tailwindcss/forms")],
darkMode: ["class"],
```

The forms plugin is the only plugin. `darkMode` is wired but unused — the shell
is permanently dark and the content permanently light, so don't build a
dark-mode variant of the content surface unless you're redesigning the shell too.

### 2.3 Fonts

Self-host as variable fonts, weight range `100 900`:

- **Inter** — everything. `font-display: optional` (it's the body face, no flash).
- **Space Grotesk** — one oversized marketing heading. `font-display: swap`.
- **Hanken Grotesk** — one large lead paragraph. `font-display: swap`.

---

## 3. Colour in practice

### 3.1 Slate ramp

| Class | Hex | Where it's used |
| --- | --- | --- |
| `slate-50` | `#f8fafc` | Hover fill on white/bordered controls |
| `slate-100` | `#f1f5f9` | Page band, table row hairlines, skeleton fill, footer divider |
| `slate-200` | `#e2e8f0` | Default border on inputs, cards, table outer edge |
| `slate-300` | `#cbd5e1` | Visible dividers; hover hint on dashed inline-edit underline |
| `slate-400` | `#94a3b8` | Placeholder text, empty-state icons, muted subtitles, inactive nav icon |
| `slate-500` | `#64748b` | Secondary text, widget icon glyph, default tag text |
| `slate-600` | `#475569` | **Default body text**, secondary button label |
| `slate-700` | `#334155` | Widget/section titles, strong labels, modal titles |
| `slate-800` | `#1e293b` | Sub-navigation panel background |
| `slate-900` | `#0f172a` | App shell canvas, primary headings, dark tooltip fill |

### 3.2 Accent

| Class | Hex | Use |
| --- | --- | --- |
| `blue-600` | `#2563eb` | **Primary.** Buttons, active segment, checked checkbox, progress fill |
| `blue-700` | `#1d4ed8` | Primary hover; focused input border (`focus-within:border-blue-700`) |
| `blue-100` | `#dbeafe` | Selected-row fill |
| `blue-50` | `#eff6ff` | Faintest informational fill |

`bg-primary hover:bg-primary/90` and `bg-blue-600 hover:bg-blue-700` are both in
use and visually equivalent — prefer the token form on anything reusable.

### 3.3 Status

Two vocabularies exist. The theme keeps legacy Bootstrap-ish aliases
(`text-success` `#198754`, `text-warning` `#ffc107`, `text-danger` `#dc3545`,
`text-info` `#0dcaf0`); product surfaces use the Tailwind ramps, which is
what you should build with:

| Meaning | Text | Soft fill | Dark text on fill |
| --- | --- | --- | --- |
| Success | `text-emerald-600` | `bg-emerald-100` | `text-emerald-900` |
| Warning | `text-amber-600` | `bg-amber-100` | `text-amber-900` |
| Danger | `text-red-600` | `bg-red-100` | `text-red-900` |

Status colour never carries meaning alone — pair it with an icon or a word.

### 3.4 AI / machine-generated

Anything produced by an automated agent gets a violet-to-fuchsia gradient. Ship
it as one component class so it stays consistent:

```css
@layer components {
  .ai-badge {
    @apply inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium
           whitespace-nowrap bg-gradient-to-r from-violet-100 to-fuchsia-100
           text-violet-700;
  }
}
```

This is the only gradient allowed on a text element, and it exists so a user can
tell machine output from human input at a glance. Don't reuse violet elsewhere.

### 3.5 Identity tags

Free-form labels (categories, owners, keywords) draw from a fixed 15-step pastel
wheel. Each fill has a hand-picked dark text partner — arbitrary values, not
computed contrast, never white text.

| Fill | Text |
| --- | --- |
| `#FFC2C2` | `#622727` |
| `#FFD1C2` | `#673627` |
| `#FFE3C2` | `#6B4E2C` |
| `#FFF2C2` | `#867536` |
| `#FFFDC2` | `#69662A` |
| `#E8FFC2` | `#465727` |
| `#CEFFC2` | `#3A5E32` |
| `#C2FFE9` | `#2B5F4C` |
| `#C2F8FF` | `#21555C` |
| `#C2EDFF` | `#1C4050` |
| `#C2DBFF` | `#3E5374` |
| `#C2C5FF` | `#1F225E` |
| `#D6C2FF` | `#3A285E` |
| `#ECC2FF` | `#663D7A` |
| `#FFC2FD` | `#5B2959` |

These come from data, so set them inline rather than as classes. Unknown fill
falls back to text `#64748b`.

---

## 4. Typography

Only three weights: `font-normal` (400), `font-medium` (500), `font-semibold`
(600). No bold, no light. Emphasis comes from size and colour more than weight.

Line heights are absolute, not multipliers, so rows align across columns. Define
the scale once as arbitrary values:

| Role | Classes | Size / leading |
| --- | --- | --- |
| Display | `text-[60px] font-medium leading-[72.61px]` | 60 / 72.6 |
| Heading 1 | `text-[42px] font-medium leading-[50.83px]` | 42 / 50.8 |
| Heading 2 | `text-[32px] font-medium leading-[38.73px]` | 32 / 38.7 |
| Heading 3 / page title | `text-[24px] font-medium leading-[29.05px]` | 24 / 29.1 |
| Subtitle | `text-[20px] font-medium leading-[24.2px]` | 20 / 24.2 |
| Large | `text-[18px] leading-[21.78px]` + `font-normal`/`font-medium` | 18 / 21.8 |
| **Body (default)** | `text-[15px] leading-[18.15px]` + weight | 15 / 18.2 |
| Small — dense default | `text-[13px] leading-[15.73px]` + weight | 13 / 15.7 |
| Micro — labels, meta | `text-[11px] leading-[13.31px]` + weight | 11 / 13.3 |
| Tiny | `text-[9px] font-medium leading-[10.89px]` | 9 / 10.9 |
| Extra tiny | `text-[7px] font-medium leading-[8.47px]` | 7 / 8.5 |

Display variants: `font-space-grotesk text-[50px] font-medium` for the marketing
heading, `font-hanken-grotesk text-[18px] font-normal leading-[29.05px]` for a
lead paragraph. Both are exceptions, not product-UI tools.

Italic exists at large / body / small / micro, used only for inferred, quoted,
or provisional values.

### Rules

- Default text colour is `text-slate-600`, not black. Reserve `text-slate-900`
  for headings and for values a user must read exactly.
- Page titles: `text-[24px] font-medium text-slate-900` beside a 36px icon.
- Panel and widget titles: `text-xs font-semibold text-slate-700` —
  deliberately smaller than body, because they label rather than speak.
- Section labels in dark navigation: `text-[11px] font-semibold uppercase
  tracking-wider text-slate-500`.
- Table headers: 12px.
- Truncate by default (`w-full truncate text-ellipsis whitespace-nowrap
  overflow-hidden`). Wrapping is opt-in; when on, preserve author line breaks
  with `whitespace-pre-wrap text-left`.

---

## 5. Geometry

**Radius.** `rounded-lg` is the 8px base (cards, modals). `rounded-md` 6px is
the workhorse: buttons, chips, tooltips, inputs, nav rows. `rounded-sm` 4px for
small controls and checkboxes; `rounded-[3px]` for hairline-tight fields.
Shell radii are bigger and softer: `rounded-xl` (12px) for the navigation panel,
`rounded-tl-2xl` (16px) for the content surface corner. `rounded-full` for pills
and progress segments.

**Spacing.** A 2px ladder — `gap-0.5` through `gap-8`. In practice: `gap-2`
between related controls, `p-3` inside panels, `px-6 py-4` at page edges,
`gap-1.5` between segmented items, `space-y-[2px]` between navigation rows.

**Control heights.** `h-11` (44) large, `h-10` (40) default, `h-9` (36) compact
and navigation rows, `h-7` (28) icon chip, `h-6` (24) inline icon, 16px
checkbox. Icon-only buttons are square: `h-10 w-10`.

**Hairlines.** Always 1px. `border-slate-100` when it must recede,
`border-slate-200` for a real edge, `border-slate-300` for an emphasised
divider. On dark chrome: `border-slate-700/50`.

---

## 6. Elevation

Four tinted shadows, blue-grey rather than black:

| Class | Use |
| --- | --- |
| `shadow-soft` | Resting cards, hovered table rows |
| `shadow-custom` | Floating panels that must lift off the page |
| `shadow-flying` | Hard 4px offset "printed card" edge |
| `shadow-chat-bubble` | Chat and comment bubbles |

Overlays use ordinary neutral shadows because they must read as detached:
`shadow-md` for menus and popovers, `shadow-xl` for modals. Pinned table
columns cast a directional `4px 0 8px -2px rgba(0,0,0,0.06)` (mirrored on the
right-hand side); a pinned totals row casts the same upward into the content.

### The lifted-card treatment

Our signature card is not a shadowed box — it's a 1px gradient outline with a
thicker bottom edge, wrapping a white inner surface. Two nested elements:

- Outer: `rounded-md bg-gradient-to-b from-slate-200/40 to-slate-300/60 p-[1px] pb-[4px]`
- Inner: `rounded-md bg-white overflow-hidden`

The extra 4px at the bottom reads as a physical edge catching light. Use it for
dashboard widgets and grouped content. Don't add a drop shadow on top of it.

### Panel outline on dark

Navigation panels use the same trick in reverse — a masked gradient border plus
an inner glow, so the panel looks lit from within rather than flat. Two absolute
overlays inside a `relative rounded-xl bg-slate-800` container:

```css
/* gradient hairline */
.panel-outline {
  padding: 1px;
  background: linear-gradient(135deg, rgba(148,163,184,0.35) 0%, rgba(71,85,105,0.12) 50%, rgba(148,163,184,0.18) 100%);
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  -webkit-mask-composite: xor;
}
/* inner glow */
.panel-glow {
  background: radial-gradient(circle at 50% 70%, rgba(40,60,100,0.6) 0%, rgba(30,45,69,0.2) 30%, rgba(0,0,0,0.2) 100%);
}
```

Both are `absolute inset-0 rounded-xl pointer-events-none`.

---

## 7. Motion

Short, functional, never bouncy. No springs, no overshoot.

| What | Classes |
| --- | --- |
| Colour / border / background | `transition-colors` (150ms) |
| Fade in | `animate-fadeIn` (200ms ease-out) |
| Content fade-in-up, 16px rise | `animate-fadeInUp` (600ms ease-out, once) |
| Collapse / expand | `transition-all duration-200 ease-in-out` |
| Panel width | `transition-[width] duration-300 ease-in-out` |
| Shimmer loop | `animate-shimmer` (1.3s linear) |
| Idle float, 2px | `animate-float` (1.8s ease-in-out) |
| Tooltip appear | 150ms ease-out, scaled from 0.5, origin at the arrow side |

**Press feedback.** Interactive rows and icon buttons drop 1px while held:
`active:relative active:top-[1px]` (with `disabled:active:top-0`). Cheap,
tactile, never moves layout.

---

## 8. Focus and input states

**Text fields never show a focus ring or outline.** Hard rule, enforced
globally — including glows implemented as box-shadow, which is how Tailwind's
`ring-*` works, so both have to be reset:

```css
@layer base {
  input:focus, input:focus-visible,
  textarea:focus, textarea:focus-visible,
  select:focus, select:focus-visible,
  [contenteditable]:focus, [contenteditable]:focus-visible {
    outline: none !important;
    box-shadow: none !important;
  }
}
```

Focus is communicated by darkening the border instead: `focus:border-slate-400`
for a soft indication, `focus-within:border-blue-700` when a whole field group
should light up.

Non-text controls keep a real keyboard indicator:
`focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
focus-visible:ring-offset-2`. Don't remove it — it's the only accessibility
affordance left once fields opted out.

Disabled: `disabled:opacity-50 disabled:pointer-events-none
disabled:cursor-not-allowed disabled:text-slate-400 disabled:border-slate-200
disabled:bg-slate-50 disabled:shadow-none`.

**Inline editing.** Editable values look like plain text with a transparent
dashed underline:

- Read: `font-semibold text-slate-900 leading-snug border-b border-dashed
  border-transparent hover:border-slate-300 transition-colors cursor-text py-0.5`
- Edit: `w-full bg-white rounded-md border-b border-dashed py-0.5 font-semibold
  text-slate-900 focus:outline-none focus:ring-0 focus:border-slate-500`
- Saving: `opacity-60 cursor-wait`

Save on blur or Enter, cancel on Escape. The point is zero layout shift between
reading and editing.

---

## 9. Application shell

Outside-in:

1. **Canvas** — `h-screen bg-slate-900`, holding a `flex h-full` row.
2. **Icon rail** — `w-[68px] flex-shrink-0 flex flex-col items-center px-2 gap-1
   pb-4`. Targets are `w-10 h-10 rounded-lg` with `text-slate-500
   hover:bg-slate-800 hover:text-white transition-colors`. Top slot is
   `h-[46px]` to align with the header.
3. **Navigation panel** — `w-[200px] pr-2 pb-2` open, `w-0` closed, with
   `transition-[width] duration-300 ease-in-out overflow-hidden`. Inner:
   `relative flex-1 rounded-xl bg-slate-800 min-w-[184px] mt-[46px]
   overflow-hidden flex flex-col`, plus the outline and glow overlays from §6.
   Rows: `flex h-9 w-full items-center rounded-md px-2 py-2 transition-colors
   active:relative active:top-[1px]`, 18px icon with `mr-2`, label
   `text-sm font-semibold`. Active — `bg-slate-600/50` with `text-white`;
   inactive — `text-slate-400 hover:bg-slate-700/40
   group-hover:text-slate-200`. Group separators `border-t border-slate-700/50`,
   `space-y-[2px]` between rows.
4. **Header** — `flex h-[46px] flex-shrink-0 items-center justify-between px-4`,
   transparent over the canvas, content `text-slate-200`, icon targets
   `rounded-full hover:bg-slate-700`.
5. **Content surface** — `flex-1 flex flex-col overflow-hidden bg-white
   rounded-tl-2xl`, scrolling internally (`main` is `flex-1 overflow-y-auto`).
   No outer border; the dark canvas is the border.
6. **Overlay layer** — one `absolute inset-x-0 bottom-0 top-[46px] z-40
   pointer-events-none` layer above the content but below the header, so side
   panels can cover navigation while the header stays reachable.

Persist navigation open/closed state and the selected group to local storage.

**Page band.** Each page opens with `relative bg-slate-100 py-4 px-6` holding a
36px page icon, `text-[24px] font-medium text-slate-900` title, optional search,
and right-aligned actions. Decorative oversized line-art is absolutely
positioned bleeding off the top-right, inside an `absolute inset-0
overflow-hidden` wrapper, with content raised to `relative z-[1]`. The only
ornament in the product.

---

## 10. Component recipes

Class lists you can paste, framework-free.

### Buttons

Base:

```
inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md
text-sm font-medium transition-colors ring-offset-background
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50
```

| Variant | Classes |
| --- | --- |
| Primary | `bg-primary text-primary-foreground hover:bg-primary/90` |
| Secondary | `bg-secondary text-secondary-foreground hover:bg-secondary/80` |
| Outline | `border border-input bg-background hover:bg-accent hover:text-accent-foreground` |
| Ghost | `hover:bg-accent hover:text-accent-foreground` |
| Link | `text-primary underline-offset-4 hover:underline` |
| Destructive | `bg-destructive text-destructive-foreground hover:bg-destructive/90` |

Sizes: default `h-10 px-4 py-2`, small `h-9 px-3`, large `h-11 px-8`, icon
`h-10 w-10`.

**Segmented / micro buttons.** 13px label or `h-4 w-4` icon, `p-[2px]`,
`border border-slate-200` shared between neighbours, only outer corners rounded
(`rounded-l-[6px]` / `rounded-r-[6px]`), `bg-white hover:bg-slate-50`, active
segment `bg-blue-600` with white content. Standalone variant is `rounded-full`.

**Icon buttons.** `inline-flex justify-center items-center` plus
`disabled:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed
disabled:text-slate-400 disabled:border-slate-200 disabled:shadow-none` and the
1px press shift.

### Text fields

```
w-full h-9 px-2 py-1.5 text-sm bg-white border border-slate-200 rounded-md
text-slate-700 placeholder:text-slate-400 focus:outline-none
```

Wrap in a `focus-within:border-blue-700` container when a leading icon and clear
button share the field. Search variant uses `rounded-[3px]` and a
`grid grid-cols-[auto,1fr] px-[7px]` layout with a 24px `text-slate-500` icon.
The clear affordance renders only when there's a value. Debounce search input
~300ms before querying.

### Dashboard widget

Outer / inner from §6, then:

- Header: `flex items-center justify-between px-3.5 py-2.5 flex-none`
- Icon chip: `flex items-center justify-center h-7 w-7 rounded-full
  bg-slate-700/5 border border-slate-900/10` with a `text-slate-500` glyph
- Title: `text-xs font-semibold text-slate-700`, `gap-2.5` from the chip
- Body: `flex-1 overflow-y-auto p-3` — allow opting out of padding for flush
  tables

### Modal

Backdrop `fixed inset-0 z-50` + `absolute inset-0 bg-black/40`, click to
dismiss, Escape dismisses. Sheet: `relative z-10 w-full bg-white rounded-lg
shadow-xl mx-4 flex flex-col`, `min-height: 600px` (auto-sized modals opt out),
`max-height: 90vh`, body scrolls.

Widths: `max-w-[680px]` / `max-w-[780px]` / `max-w-[1024px]` /
`max-w-[1440px]` / `max-w-[95vw]`.

- Header: `flex items-start justify-between gap-3 px-6 py-4 flex-shrink-0`;
  title `text-[20px] font-medium leading-none text-slate-700 truncate`;
  subtitle `text-[13px] font-normal leading-none text-slate-400 truncate`;
  close target `h-10 w-10 text-slate-400 hover:text-slate-600`.
- Step bar directly under the header: `flex w-full gap-1.5 px-6`, segments
  `flex-1 h-[4px] rounded-full transition-colors duration-150`, current
  `bg-blue-600`, rest `bg-slate-200`. Single-step flows show one solid blue bar,
  which doubles as a header underline.
- Footer: `px-7 py-4 border-t border-slate-100`, secondary left, primary right.
  Footer actions: `h-9 min-w-[80px] rounded px-2 text-sm font-medium
  transition-colors flex items-center justify-center gap-1.5
  disabled:opacity-50 disabled:pointer-events-none`; primary `bg-blue-600
  text-white hover:bg-blue-700`; secondary `border border-slate-200
  text-slate-600 bg-white hover:bg-slate-50`. In-flight primary shows a spinner
  before its label and disables both.

### Data table

Density and hairlines carry the structure. No zebra striping.

```css
:root {
  --table-border-color: #e2e8f0;       /* slate-200 */
  --table-border-color-light: #f1f5f9; /* slate-100 */
}
```

- Header row: 12px text, light bottom hairline.
- Rows: light bottom hairline; hover raises `0 1px 3px rgba(0,0,0,0.05)` rather
  than changing fill.
- Columns: light vertical dividers, suppressed on the last column and on
  utility columns (selection, row menu) — those must stay visually clean.
- Bordered mode adds `--table-border-color` on the outer edges only.
- Radius is opt-in: 2 / 6 / 8 / 12 / 16px, clipping corner cells.
- Pinned columns and pinned totals rows use the directional shadows from §6.
- Selection checkbox — `appearance: none`, 16px square, `border-radius: 4px`,
  `1.5px solid #e2e8f0`, white fill; checked `#2563eb` with a white 1.5px tick
  drawn as a rotated border; `border-color: #94a3b8` on hover; 40% opacity
  disabled.
- Row menus and inline actions appear on hover, never permanently.

### Tooltip

```
z-[200] rounded-md px-2.5 py-1.5 text-xs shadow-md
```

Dark (default): `bg-slate-900 border border-slate-600/50 text-white`.
Light: `bg-white border border-slate-200 text-slate-700`.

6px offset from the trigger, ~200ms open delay. The arrow is an 8px rotated
square that inherits fill and border so it reads as one shape:

```css
.tooltip-content::before {
  content: "";
  position: absolute;
  width: 8px; height: 8px;
  box-sizing: border-box;
  background: inherit;
  border: inherit;
  border-radius: 1px;
  transform: rotate(45deg);
}
.tooltip-content[data-side="top"]::before {
  bottom: -3px; left: 50%; margin-left: -4px;
  border-top: 0; border-left: 0;
}
/* mirror for right / left / bottom, zeroing the two borders facing the content */

@keyframes tooltipScaleIn { from { opacity: 0; scale: 0.5; } to { opacity: 1; scale: 1; } }
.tooltip-content[data-side="top"] {
  transform-origin: center bottom;
  animation: tooltipScaleIn 150ms ease-out;
}
```

Tooltips may be interactive (hoverable content), but then must not steal focus
from their trigger.

### Tag / pill

`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium
whitespace-nowrap` — or `rounded-full`. Identity tags set fill and text inline
from §3.5; status pills use the soft-fill pairs from §3.3; machine-generated
markers use `.ai-badge`.

### Loading

- **Skeleton** — `rounded bg-slate-100 animate-pulse` with height matched to the
  text it replaces (`h-4` for body). Use when layout is known.
- **Shimmer** — `animate-shimmer` over a wide light gradient band; use on larger
  surfaces where a pulse looks dead.
- **Spinner** — for in-flight actions inside a button, never for whole pages.

Never swap a populated view for a spinner; skeleton in place.

### Empty state

`my-4 flex flex-col flex-wrap items-center justify-center space-y-2
text-center`: a 32px `stroke-width: 1.5` outline icon in `#94a3b8`, an
18px medium `text-slate-500` headline, a smaller muted explanation, and — if
there's a next step — one primary action. Tone is factual: say what would appear
here and how to create it.

### Scrollbars

Overlay style, invisible until the container is hovered:

```css
.scrollbar-thin { scrollbar-width: thin; scrollbar-color: transparent transparent; }
.scrollbar-thin:hover { scrollbar-color: rgba(100,116,139,0.35) transparent; }
.scrollbar-thin::-webkit-scrollbar { width: 6px; height: 6px; }
.scrollbar-thin::-webkit-scrollbar-track { background: transparent; }
.scrollbar-thin::-webkit-scrollbar-thumb { background-color: transparent; border-radius: 9999px; }
.scrollbar-thin:hover::-webkit-scrollbar-thumb { background-color: rgba(100,116,139,0.35); }
.scrollbar-thin::-webkit-scrollbar-thumb:hover { background-color: rgba(100,116,139,0.55); }

.scrollbar-hide::-webkit-scrollbar { display: none; }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
```

Transparent track matters — no reserved gutter on the edge.

### Divider

`h-[1px] bg-slate-300`, or `bg-slate-200` when it should recede. Optionally
inset from both edges by an equal margin.

---

## 11. Ornament

Two effects, both optional, both sparing.

**Glint.** A wide 60° white band sweeping across a hover-scaled element in
500ms. Reserved for one or two high-value calls to action.

```css
.glint-effect { position: relative; overflow: hidden; cursor: pointer; transition: all .5s; transform: scale(1); }
.glint-effect:hover { transform: scale(1.05); }
.glint-effect::after {
  content: ''; position: absolute; inset: 0 auto auto 0;
  height: 100%; width: 400%;
  background: linear-gradient(60deg,
    rgba(255,255,255,0) 0%, rgba(255,255,255,0) 70%,
    rgba(255,255,255,0.9) 90%, rgba(255,255,255,0) 100%);
  transition: all .5s; pointer-events: none;
}
.glint-effect:hover::after { left: -300%; opacity: .5; }
.glint-effect span { position: relative; z-index: 1; }
```

**Line-art bleed.** Oversized, low-contrast line drawings anchored off the
top-right of a page band and clipped by it. Decoration only — never carries
meaning, never sits under text.

Also available and rarely used: `bg-radial`, `bg-diagonal-stripes`,
`bg-stripe-pattern-backwards` for hatched or "inactive" fills.

---

## 12. Checklist for a new surface

1. `bg-slate-900` chrome, `bg-white` content, one `rounded-tl-2xl` where they meet.
2. Text defaults to `text-slate-600` at 15px, or 13px in dense regions.
3. Every interactive accent is `blue-600`. If something else is blue, it's a bug.
4. Structure with 1px `border-slate-200` before reaching for a shadow.
5. Cards get the gradient outline with `pb-[4px]`, not a drop shadow.
6. No focus ring on text fields — darken the border. Keep rings on buttons.
7. Radius: `rounded-md` controls, `rounded-lg` cards, `rounded-xl`/`2xl` shell.
8. Transitions 150–200ms ease-out. Press states `active:top-[1px]`.
9. Loading is a skeleton in place, not a spinner replacing content.
10. Machine-generated content is marked with `.ai-badge`.
