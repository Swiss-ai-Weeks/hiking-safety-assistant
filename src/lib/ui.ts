import type { StopSeverity } from '../domain/types'

export type ButtonVariant = 'primary' | 'secondary' | 'accent' | 'field' | 'danger'
export type ButtonSize = 'lg' | 'md'

const BUTTON_SIZES: Record<ButtonSize, string> = {
  lg: 'h-[54px] rounded-button px-5 text-[17px]',
  md: 'h-12 rounded-control px-4 text-[15px]',
}

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-plum text-white hover:bg-plum-hover hover:text-white disabled:bg-line disabled:text-faint',
  secondary: 'border-[1.5px] border-line text-ink-2 hover:border-muted disabled:opacity-55',
  accent: 'border-[1.5px] border-plum text-plum hover:bg-plum/5 disabled:opacity-55',
  field: 'bg-field-button text-white hover:bg-field-control hover:text-white',
  danger: 'bg-sev-high text-white hover:brightness-95 hover:text-white',
}

export function buttonClass(variant: ButtonVariant = 'primary', size: ButtonSize = 'lg', extra = ''): string {
  return [
    'inline-flex items-center justify-center gap-2 text-center font-semibold no-underline transition-colors select-none disabled:cursor-not-allowed',
    BUTTON_SIZES[size],
    BUTTON_VARIANTS[variant],
    extra,
  ].join(' ')
}

export const pillClass =
  'flex h-9 shrink-0 items-center rounded-full border-[1.5px] border-line px-3.5 text-sm font-semibold text-plum hover:border-plum disabled:opacity-55'

export const SEVERITY_BG: Record<StopSeverity, string> = {
  none: 'bg-sev-none',
  mod: 'bg-sev-mod',
  high: 'bg-sev-high',
  unknown: 'border-[1.5px] border-dashed border-sev-none bg-transparent',
}

/** Stroke colours for Leaflet polylines (from the spec's map prototype). */
export const SEVERITY_STROKE: Record<StopSeverity, string> = {
  none: '#8f8a83',
  mod: '#d9a038',
  high: '#d4623a',
  unknown: '#8f8a83',
}
