import { useState } from 'react'
import { Button } from '../components/Button'
import { SectionTitle } from '../components/Card'
import { ChoiceGroup } from '../components/ChoiceGroup'
import { ScreenHeader } from '../components/ScreenHeader'
import type { Lang, Scenario } from '../domain/types'
import { useT } from '../i18n'
import { usePlan } from '../store/plan'

const LANGUAGES: { value: Lang; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'Français' },
]
const SCENARIOS: Scenario[] = ['assessed', 'partial', 'not_assessable', 'stale']

export function SettingsScreen() {
  const { t, lang } = useT()
  const scenario = usePlan((s) => s.scenario)
  const setLang = usePlan((s) => s.setLang)
  const setScenario = usePlan((s) => s.setScenario)
  const resetDemo = usePlan((s) => s.resetDemo)
  const [resetDone, setResetDone] = useState(false)

  return (
    <>
      <ScreenHeader backTo="/" title={t('settings.title')} />
      <main className="flex flex-1 flex-col gap-7 px-[18px] pt-[18px] pb-10">
        <section className="flex flex-col gap-2.5">
          <SectionTitle>{t('settings.language')}</SectionTitle>
          <ChoiceGroup label={t('settings.language')} options={LANGUAGES} value={lang} onChange={setLang} />
          <p className="px-1 text-[13px] text-muted">{t('settings.languageNote')}</p>
        </section>

        <section className="flex flex-col gap-2.5">
          <SectionTitle>{t('settings.scenario')}</SectionTitle>
          <div role="radiogroup" aria-label={t('settings.scenario')} className="overflow-hidden rounded-card border border-line bg-card">
            {SCENARIOS.map((s) => (
              <button
                key={s}
                type="button"
                role="radio"
                aria-checked={scenario === s}
                onClick={() => setScenario(s)}
                className="flex min-h-12 w-full items-center justify-between border-b border-divider px-4 py-3 text-left text-[15px] last:border-0 hover:bg-subtle"
              >
                {t(`scenario.${s}` as const)}
                {scenario === s && (
                  <span aria-hidden="true" className="font-semibold text-plum">
                    ✓
                  </span>
                )}
              </button>
            ))}
          </div>
          <p className="px-1 text-[13px] text-muted">{t('settings.scenarioNote')}</p>
        </section>

        <section className="flex flex-col gap-2">
          <Button
            variant="secondary"
            size="md"
            onClick={() => {
              resetDemo()
              setResetDone(true)
            }}
          >
            {t('settings.reset')}
          </Button>
          {resetDone && (
            <p role="status" className="px-1 text-center text-[13px] text-muted">
              {t('settings.resetDone')}
            </p>
          )}
        </section>
      </main>
    </>
  )
}
