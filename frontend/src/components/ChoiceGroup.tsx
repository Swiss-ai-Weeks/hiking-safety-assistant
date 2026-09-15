interface Props<T extends string> {
  label: string
  options: { value: T; label: string }[]
  value: T | null
  onChange: (value: T) => void
  disabled?: boolean
}

export function ChoiceGroup<T extends string>({ label, options, value, onChange, disabled = false }: Props<T>) {
  return (
    <div role="radiogroup" aria-label={label} className="flex gap-2">
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onChange(option.value)}
            className={`h-[46px] min-w-0 flex-1 rounded-control border-[1.5px] px-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${
              selected ? 'border-plum bg-plum text-white' : 'border-line text-ink-2 enabled:hover:border-muted'
            } ${disabled && !selected ? 'opacity-55' : ''}`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
