/**
 * Puriy brand palette — the Cochabamba *micro* colors (crimson red, golden
 * yellow, royal blue) on a clean off-white canvas. Single source of truth for
 * brand color across the app.
 *
 * Roles (SBB-style discipline — color earns its place):
 *   blue   — brand, transit, bus lines, the journey line
 *   red    — primary actions, emphasis, brand mark, destructive
 *   yellow — fares / money
 *   green  — confirmation (approve / confirmed)
 *
 * Each ramp has: `soft` (light fill), `DEFAULT` (the color), `ink` (text on a
 * soft fill). The Tailwind equivalents live in tailwind.config.js under
 * `brand-*` and must mirror these hexes.
 */

export const palette = {
  blue: { soft: '#E7EEF7', DEFAULT: '#3D6CB4', ink: '#1E3A66' },
  red: { soft: '#FBE7E9', DEFAULT: '#D62F3F', ink: '#8A1A26' },
  yellow: { soft: '#FCF3D0', DEFAULT: '#F2C200', ink: '#4A3A00' },
  green: { soft: '#E3F5EA', DEFAULT: '#1F9D57', ink: '#0F6E3A' },

  bg: '#F4F6F7',
  surface: '#FFFFFF',
  ink: '#1A1C1E',
  muted: '#5F6368',
  hint: '#9AA0A6',
  line: '#E4E7EA',
} as const;

/** Semantic roles — prefer these over raw palette entries in components. */
export const brand = {
  primary: palette.blue.DEFAULT,
  accent: palette.red.DEFAULT,
  fare: palette.yellow.DEFAULT,
  confirm: palette.green.DEFAULT,
  danger: palette.red.DEFAULT,
  background: palette.bg,
  surface: palette.surface,
  text: palette.ink,
  muted: palette.muted,
  hint: palette.hint,
  line: palette.line,
} as const;
