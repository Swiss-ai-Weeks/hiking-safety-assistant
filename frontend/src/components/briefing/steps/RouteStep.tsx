import { useT } from '../../../i18n'
import { formatInt, formatKm } from '../../../lib/format'
import { ElevationProfile } from '../ElevationProfile'
import { easeOut } from '../model'
import type { StepProps } from './types'

export function RoutePanel({ view, model, progress }: StepProps) {
  const { t, lang } = useT()
  const { route } = view
  const k = easeOut(progress)
  const crux = model.keyStops.find((key) => key.role === 'crux')

  const stats = [
    { label: t('brief.distance'), value: `${formatKm(route.distanceKm * k, lang)}`, unit: 'km' },
    { label: t('brief.up'), value: formatInt(route.ascentM * k), unit: 'm' },
    ...(route.descentM !== undefined ? [{ label: t('brief.down'), value: formatInt(route.descentM * k), unit: 'm' }] : []),
    { label: t('brief.grade'), value: route.grade, unit: '' },
  ]

  return (
    <div className="flex flex-col gap-4">
      <dl className="grid grid-flow-col gap-2">
        {stats.map((stat) => (
          <div key={stat.label} className="flex flex-col rounded-control bg-subtle px-3 py-2.5">
            <dt className="text-[11px] text-muted">{stat.label}</dt>
            <dd className="text-xl font-semibold whitespace-nowrap tabular-nums">
              {stat.value}
              {stat.unit && <span className="ml-0.5 text-[13px] font-medium text-muted">{stat.unit}</span>}
            </dd>
          </div>
        ))}
      </dl>
      <ElevationProfile
        profile={model.profile}
        lengthM={model.track.lengthM}
        alongM={progress * model.track.lengthM}
        marks={crux ? [{ alongM: model.stopAlong[crux.index], label: crux.name }] : []}
      />
      <p className="text-[13px] text-muted">{t('brief.outAndBack', { from: route.fromName, to: route.toName })}</p>
    </div>
  )
}
