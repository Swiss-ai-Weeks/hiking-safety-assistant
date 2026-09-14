import type { GapKind } from '../domain/types'
import { useT } from '../i18n'

/** "What we can't see": gaps are named, never hidden. */
export function GapsList({ gaps }: { gaps: GapKind[] }) {
  const { t, tr } = useT()
  if (gaps.length === 0) return null

  return (
    <section className="flex flex-col gap-2 rounded-card bg-subtle p-4">
      <h2 className="text-[15px] font-semibold">{t('gaps.title')}</h2>
      <ul className="flex flex-col gap-1.5 text-sm leading-normal text-ink-2">
        {gaps.map((gap) => (
          <li key={gap} className="flex gap-2">
            <span aria-hidden="true" className="text-faint">
              –
            </span>
            <span>
              {gap === 'warnings'
                ? tr('gap.warnings', {
                    link: (
                      <a href="https://www.meteoswiss.admin.ch/weather/weather-and-climate-from-a-to-z/weather-warnings.html" target="_blank" rel="noreferrer">
                        {t('common.meteoswiss')}
                      </a>
                    ),
                  })
                : t(`gap.${gap}` as const)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
