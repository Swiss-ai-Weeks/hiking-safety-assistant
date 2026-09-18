import { useState } from 'react'
import { Button } from '../components/Button'
import { SectionTitle } from '../components/Card'
import { ChoiceGroup } from '../components/ChoiceGroup'
import { ScreenHeader } from '../components/ScreenHeader'
import type { Lang } from '../domain/types'
import { useT } from '../i18n'
import { usePlan } from '../store/plan'

const LANGUAGES: { value: Lang; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'Français' },
]

export function SettingsScreen() {
  const { t, lang } = useT()
  const setLang = usePlan((s) => s.setLang)
  const resetData = usePlan((s) => s.resetData)
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

        <section className="flex flex-col gap-2">
          <Button
            variant="secondary"
            size="md"
            onClick={() => {
              resetData()
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
