import { Link } from 'react-router-dom'
import { fetchPriorityActions, fetchRadar, formatMoney } from './api'
import { EmptyState, ErrorState, LoadingState, useAsync } from './States'
import type { PriorityAction, RadarSummary } from './types'
import './radar.css'

/**
 * The Radar — the /app landing screen. Three things, in order: the weekly
 * sweep as tiles, the pipeline those tiles add up to, and the actions the week
 * actually asks for.
 *
 * THE THING THIS SCREEN EXISTS TO GET RIGHT: several of these counts are
 * legitimately 0 and will be 0 in front of a client. A bare "0" is
 * indistinguishable from a failed fetch, so every zero here is labelled with
 * WHY it is zero, and the two kinds of zero are said differently:
 *
 *   'no-source'  — nothing generates this data yet. emergingTrends and
 *                  competitorMovements need IndustrySignal rows, which do not
 *                  exist. These will be 0 until that pipeline is built.
 *   'none-yet'   — the data exists and is being scanned, nothing qualified.
 *                  organisationsWorthApproaching is this today; it can move
 *                  next week without a line of code changing.
 *
 * Zero tiles are muted but never hidden. Hiding them would make the dashboard
 * a different shape per user and per week, which reads as arbitrary and loses
 * the information that we ARE watching for the thing.
 */

/** Why a zero on this tile is a fact rather than a fault. */
type ZeroKind = 'no-source' | 'none-yet'

interface Tile {
  key: string
  label: string
  count: number
  zeroKind: ZeroKind
  /** Shown only at zero — the sentence that stops it reading as a broken tile. */
  zeroNote: string
}

const ZERO_TAG: Record<ZeroKind, string> = {
  'no-source': 'Not tracked yet',
  'none-yet': 'None this week',
}

function buildTiles(radar: RadarSummary): Tile[] {
  return [
    {
      key: 'opportunities',
      label: 'Opportunities worth pursuing',
      count: radar.opportunitiesWorthPursuing,
      zeroKind: 'none-yet',
      zeroNote: 'Nothing cleared the bar in this sweep.',
    },
    {
      key: 'organisations',
      label: 'Organisations worth approaching',
      count: radar.organisationsWorthApproaching,
      zeroKind: 'none-yet',
      zeroNote: 'Scanned, but no organisation qualified this week.',
    },
    {
      key: 'partnerships',
      label: 'Potential partnerships',
      count: radar.potentialPartnerships,
      zeroKind: 'none-yet',
      zeroNote: 'No opportunity scored 60+ for two units at once.',
    },
    {
      key: 'trends',
      label: 'Emerging trends',
      count: radar.emergingTrends,
      zeroKind: 'no-source',
      zeroNote: 'No industry signals yet — nothing feeds this.',
    },
    {
      key: 'competitors',
      label: 'Competitor movements',
      count: radar.competitorMovements,
      zeroKind: 'no-source',
      zeroNote: 'No competitor tracking yet — nothing feeds this.',
    },
  ]
}

function SummaryTile({ tile }: { tile: Tile }) {
  const isZero = tile.count === 0

  return (
    <div
      className={
        isZero
          ? `tm-radar__tile tm-radar__tile--zero tm-radar__tile--${tile.zeroKind}`
          : 'tm-radar__tile'
      }
    >
      <div className="tm-radar__tilelabel">{tile.label}</div>
      <div className="tm-radar__tilevalue">{tile.count}</div>
      {isZero ? (
        <>
          <div className="tm-radar__tiletag">{ZERO_TAG[tile.zeroKind]}</div>
          <p className="tm-radar__tilenote">{tile.zeroNote}</p>
        </>
      ) : null}
    </div>
  )
}

/**
 * The pipeline figure. The API sends whole naira as an integer plus an ISO
 * code, so it goes through formatMoney rather than being printed raw — the
 * raw value is eleven digits and reads as a phone number.
 */
function PipelineTile({ radar }: { radar: RadarSummary }) {
  const isZero = radar.estimatedPipelineValue === 0

  return (
    <div
      className={
        isZero
          ? 'tm-radar__pipeline tm-radar__pipeline--zero'
          : 'tm-radar__pipeline'
      }
    >
      <div className="tm-radar__tilelabel">Estimated pipeline value</div>
      <div className="tm-radar__pipelinevalue">
        {formatMoney(radar.estimatedPipelineValue, radar.estimatedPipelineCurrency)}
      </div>
      <p className="tm-radar__pipelinenote">
        {isZero
          ? 'Nothing on the radar carries a confirmed value yet.'
          : `Across everything currently on the radar, in ${radar.estimatedPipelineCurrency}.`}
      </p>
    </div>
  )
}

function ActionRow({ action }: { action: PriorityAction }) {
  const isPartnership = action.type === 'Partnership'

  /*
    NOT every action has an opportunity behind it. An Organisation row — what
    the "Organisations worth approaching" tile counts — carries a null
    opportunityId, and interpolating that produced /app/opportunities/null,
    which 404s. The tile reads 0 today only because nobody has flagged an org
    approach-now yet; the first time someone does in the back office, every
    such row would have broken.

    So a row is a link only when there is somewhere to go, and plain content
    otherwise. A dead-end link is worse than no link.
  */
  const body = (
    <>
      <span className="tm-radar__actiontype">{action.type}</span>
      <span className="tm-radar__actionbody">
        <span className="tm-radar__actiontitle">{action.title}</span>
        <span className="tm-radar__actiondesc">{action.description}</span>
      </span>
      {action.opportunityId ? (
        <span className="tm-radar__actiongo" aria-hidden="true">
          →
        </span>
      ) : null}
    </>
  )

  return (
    <li
      className={
        isPartnership
          ? 'tm-radar__action tm-radar__action--partnership'
          : 'tm-radar__action tm-radar__action--opportunity'
      }
    >
      {action.opportunityId ? (
        <Link
          className="tm-radar__actionlink"
          to={`/app/opportunities/${encodeURIComponent(action.opportunityId)}`}
        >
          {body}
        </Link>
      ) : (
        <div className="tm-radar__actionlink tm-radar__actionlink--static">{body}</div>
      )}
    </li>
  )
}

export function RadarPage() {
  // Two independent fetches on purpose: the radar failing must not blank the
  // actions list, and vice versa. One dead panel is far better than a dead page.
  const radar = useAsync(() => fetchRadar(), [])
  const actions = useAsync(() => fetchPriorityActions(), [])

  return (
    <main className="tm-page tm-radar">
      <div className="tm-page__kicker">
        <span className="tm-page__dash" aria-hidden="true" />
        Opportunity Radar
      </div>
      <h1 className="tm-page__title">Your business development radar</h1>
      <p className="tm-page__lede">
        The weekly sweep, what needs attention, and the pipeline it adds up to.
      </p>

      <section className="tm-radar__section" aria-labelledby="tm-radar-sweep">
        <div className="tm-radar__sectionhead">
          <h2 className="tm-radar__sectiontitle" id="tm-radar-sweep">
            This week&rsquo;s sweep
          </h2>
        </div>

        {radar.state === 'loading' ? <LoadingState label="Loading the radar…" /> : null}
        {radar.state === 'error' ? (
          <ErrorState error={radar.error} retry={radar.reload} />
        ) : null}
        {radar.state === 'ready' ? (
          <>
            <PipelineTile radar={radar.data} />
            <div className="tm-radar__tiles">
              {buildTiles(radar.data).map((tile) => (
                <SummaryTile key={tile.key} tile={tile} />
              ))}
            </div>
            <p className="tm-radar__legend">
              A muted tile is a real zero, not a failed load.{' '}
              <strong>None this week</strong> means we looked and nothing qualified;{' '}
              <strong>Not tracked yet</strong> means the feed behind that count
              doesn&rsquo;t exist yet.
            </p>
          </>
        ) : null}
      </section>

      <section className="tm-radar__section" aria-labelledby="tm-radar-actions">
        <div className="tm-radar__sectionhead">
          <h2 className="tm-radar__sectiontitle" id="tm-radar-actions">
            This week&rsquo;s priority actions
          </h2>
          {actions.state === 'ready' && actions.data.length > 0 ? (
            <span className="tm-radar__sectioncount">
              {actions.data.length} {actions.data.length === 1 ? 'action' : 'actions'}
            </span>
          ) : null}
        </div>

        {actions.state === 'loading' ? (
          <LoadingState label="Loading priority actions…" />
        ) : null}
        {actions.state === 'error' ? (
          <ErrorState error={actions.error} retry={actions.reload} />
        ) : null}
        {actions.state === 'ready' ? (
          actions.data.length === 0 ? (
            <EmptyState
              title="No priority actions this week"
              explain="The sweep ran and nothing rose to the top. This list fills itself from the opportunities and joint pitches already on the radar, so it will repopulate on the next sweep."
            />
          ) : (
            <>
              <ul className="tm-radar__actions">
                {actions.data.map((action, index) => (
                  /*
                    Index is part of the key because opportunityId is NULL on
                    Organisation rows — keying on type+id alone would collide
                    across every such row and React would reuse the wrong one.
                    The list is server-ordered and re-fetched whole, never
                    reordered in place, so an index is stable here.
                  */
                  <ActionRow
                    key={`${action.type}-${action.opportunityId ?? 'none'}-${index}`}
                    action={action}
                  />
                ))}
              </ul>
              <p className="tm-radar__legend">
                <strong>Partnership</strong> rows are the joint-pitch signal: two or
                more units both scored 60+ on the same thing.
              </p>
            </>
          )
        ) : null}
      </section>
    </main>
  )
}
