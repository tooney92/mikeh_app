import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { fetchBusinessUnits, fetchOpportunities, fetchProfiles } from './api'
import { EmptyState, ErrorState, LoadingState, NullValue, useAsync } from './States'
import { FILTERS, type OpportunityCategory, type OpportunityFilter, type OpportunitySummary } from './types'
import './list.css'

/**
 * The ranked opportunity list.
 *
 * Two things on this screen are easy to get wrong and expensive when wrong:
 *
 * 1. The unit filter goes through fetchOpportunities(), never a hand-built
 *    query string. The wire parameter is snake_case `business_unit_id` and an
 *    unrecognised parameter is SILENTLY IGNORED — a camelCase spelling returns
 *    the full unfiltered list with a 200, which is a wrong answer that looks
 *    right. The helper owns that spelling so this file never repeats it.
 *
 * 2. The chips come from FILTERS, not from the rows' `category` values. The
 *    two vocabularies differ (chip "bid-now" -> category "bid", chip
 *    "bd-leads" -> category "bd", chip "international" is a GEOGRAPHY test and
 *    no category at all), and the filter enum is closed, so a derived value
 *    is a 400.
 *
 * Everything else on the screen exists to stop correct emptiness from reading
 * as breakage — see explainEmpty().
 */

/** Row categories are a display vocabulary of their own, separate from the chips. */
const CATEGORY_LABEL: Record<OpportunityCategory, string> = {
  bid: 'Bid',
  watch: 'Watch',
  partnership: 'Partnership',
  bd: 'BD lead',
}

/**
 * Units whose profile is still empty, so the matching engine has scored
 * nothing for them and filtering to one legitimately returns zero rows. Listed
 * by id because the API exposes no "has been scored" flag; if a profile gets
 * filled in, the worst that happens is the empty state stops being reachable
 * for that unit and this list goes stale in a harmless direction.
 */
const UNSCORED_UNIT_IDS = [2, 3, 4]

/** No option element can carry a number, so "no unit" is the empty string. */
const ALL_UNITS = ''

export function OpportunityListPage() {
  const { user } = useAuth()
  const [filter, setFilter] = useState<OpportunityFilter>('everything')
  const [unitId, setUnitId] = useState<number | ''>(ALL_UNITS)

  /**
   * Weak matches are hidden by default and this reveals them.
   *
   * It is a visible control rather than a buried one on purpose. Once the
   * matching engine is scoring automatically, the low scorers are how anyone
   * notices it scoring BADLY — hide them permanently and a broken engine looks
   * like a quiet week.
   */
  const [includeWeak, setIncludeWeak] = useState(false)

  // All five units, always — NOT user.businessUnits, which is EMPTY for admin
  // and director, exactly the people this filter exists for.
  const units = useAsync(() => fetchBusinessUnits(), [])

  /**
   * Read purely for minFitPercent, so the below-the-bar empty state can name
   * the actual threshold. A failure here is not worth blocking the list over —
   * the wording just falls back to something generic.
   */
  const profiles = useAsync(() => fetchProfiles(), [])

  // Every input is in the deps, so changing any refetches; useAsync drops a
  // slow response that lands after the inputs moved on.
  const list = useAsync(
    () =>
      fetchOpportunities({
        filter,
        businessUnitId: unitId === ALL_UNITS ? undefined : unitId,
        includeWeak,
      }),
    [filter, unitId, includeWeak],
  )

  const allUnits = units.state === 'ready' ? units.data : []

  /**
   * The unit filter is shown ONLY to unscoped users, and it is not shown to a
   * scoped one at all.
   *
   * The server ignores business_unit_id entirely for a scoped caller — it is
   * applied only when the caller is unscoped. Verified: lead.dual gets the
   * identical eight rows and identical fit values whether it asks for Takeout
   * Media, TM Foundation, or nothing.
   *
   * So for a lead or member this control cannot do anything, and every version
   * of showing it lies. Restricting the options to their own units — the
   * previous attempt at this — still left a two-unit lead reading "Takeout
   * Media" above a list that included TM Foundation rows, and made the weak-
   * match threshold name one unit's bar when the server had applied the union
   * of both. A narrower lie is still a lie.
   *
   * Admin and director keep it, because for them it genuinely narrows. They
   * are the audience it was built for.
   */
  const ownUnitIds = new Set(user?.businessUnits.map((unit) => unit.id) ?? [])

  /*
   * READ FROM role.scope, NEVER INFERRED FROM MEMBERSHIP.
   *
   * This used to be `ownUnitIds.size > 0`, which is the same fail-open
   * inference that `canEdit` was added to kill on the profiles screen and that
   * `viewer_scope` removed from the server. The account that defeats it is real
   * and creatable in /admin in one click: a lead or member saved WITHOUT a
   * business unit ticked. They are scoped — the server filters their rows to
   * the empty set — but they have no memberships, so the inference read them as
   * an admin. They got a unit picker the server ignores, and an empty list
   * explained as "nothing has been ingested yet", which is flatly untrue.
   *
   * The server has answered this all along: `role.scope` is "all" or
   * "own_units", it is contracted in todo #1, and RoleScope has been declared
   * in features/auth/types.ts since that deliverable was built. It was typed
   * and then not used. Nothing needed adding to the API — only reading.
   *
   * Note this is NOT the same question as `ownUnitIds.size`, which is why the
   * inference could ever look right: scope says whether the server filters,
   * membership says what it filters TO. A scoped user with no units answers
   * "yes" to the first and "nothing" to the second.
   */
  const isScoped = user?.role.scope === 'own_units'
  const unitOptions = isScoped ? [] : allUnits

  const selectedUnit = unitOptions.find((unit) => unit.id === unitId) ?? null

  /*
   * Whether a personal fit score can exist is a question about MEMBERSHIP, not
   * about scope — so this one deliberately still asks about units. A scoped
   * lead with no unit assigned has no fit score for the same reason an admin
   * has none: nothing of theirs has been scored.
   */
  const nullFitReason =
    ownUnitIds.size > 0
      ? 'No unit of yours has been scored against this opportunity yet'
      : 'You belong to no unit, so there is no personal fit score'

  /**
   * Which unit's bar is filtering this view, if any.
   *
   * A bar applies when the view is unit-specific: either a unit is explicitly
   * selected, or the viewer belongs to units and so is seeing their own. An
   * unscoped admin looking at everything has no bar — they are overseeing
   * rather than being pitched to.
   *
   * Somebody in two units keeps an opportunity that clears EITHER bar, so the
   * effective threshold for them is the lower of the two. Naming the lower one
   * is honest: it is the line rows actually had to clear.
   */
  const profileBars = profiles.state === 'ready' ? profiles.data : []
  const barsInForce = isScoped
    ? // A scoped user is always judged against ALL their own units — the server
      // keeps a row that clears EITHER bar — regardless of any selection,
      // because their selection is ignored.
      profileBars.filter((p) => ownUnitIds.has(p.businessUnitId))
    : selectedUnit
      ? profileBars.filter((p) => p.businessUnitId === selectedUnit.id)
      : []

  const lowestBar = barsInForce.length
    ? barsInForce.reduce((low, p) => (p.minFitPercent < low.minFitPercent ? p : low))
    : null

  /** Whether rows could be hidden right now — drives the escape hatch. */
  const barApplies = lowestBar !== null && !includeWeak

  /*
    Could a bar be in force at all for this viewer, regardless of whether the
    profiles have arrived yet?

    This exists because the two fetches are INDEPENDENT and the list is usually
    the faster one. Without it, an empty list rendered before /api/profiles
    resolved fell through to explainEmpty() and announced "no opportunity has
    been ingested yet" — which is not merely unhelpful but false, since the rows
    exist and are being withheld. If /api/profiles ERRORS, that false
    explanation is permanent and the escape hatch never appears at all.

    So an empty list has three cases, not two: the bar is hiding rows, the bar
    is definitely not (nothing could apply), or we do not yet know. The third
    must not be answered with the first or the second.
  */
  const barCouldApply = !includeWeak && (isScoped || selectedUnit !== null)
  const barsUnresolved = barCouldApply && profiles.state !== 'ready'

  return (
    <div className="tm-page tm-oplist">
      <div className="tm-page__kicker">
        <span className="tm-page__dash" aria-hidden="true" />
        Opportunities
      </div>
      <h1 className="tm-page__title">Everything worth pursuing</h1>
      <p className="tm-page__lede">
        Ranked by fit for your unit. Two units see the same opportunity in a different position.
      </p>

      <div className="tm-oplist__controls">
        <div className="tm-oplist__control">
          <div className="tm-oplist__controllabel" id="tm-oplist-chips">
            Filter
          </div>
          <div className="tm-oplist__chips" role="group" aria-labelledby="tm-oplist-chips">
            {FILTERS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={
                  option.value === filter
                    ? 'tm-oplist__chip tm-oplist__chip--on'
                    : 'tm-oplist__chip'
                }
                aria-pressed={option.value === filter}
                onClick={() => setFilter(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Hidden entirely for a scoped user — the server ignores it for them. */}
        {isScoped ? null : (
        <div className="tm-oplist__control">
          <label className="tm-oplist__controllabel" htmlFor="tm-oplist-unit">
            Business unit
          </label>
          <select
            id="tm-oplist-unit"
            className="tm-oplist__select"
            value={unitId === ALL_UNITS ? '' : String(unitId)}
            disabled={units.state !== 'ready'}
            onChange={(event) =>
              setUnitId(event.target.value === '' ? ALL_UNITS : Number(event.target.value))
            }
          >
            <option value="">All units</option>
            {unitOptions.map((unit) => (
              <option key={unit.id} value={unit.id}>
                {unit.name}
              </option>
            ))}
          </select>
          {units.state === 'error' ? (
            <p className="tm-oplist__controlnote">
              The unit list did not load, so only “All units” is available. The opportunities below
              are unfiltered and still correct.
            </p>
          ) : (
            <p className="tm-oplist__controlnote">
              {selectedUnit
                ? selectedUnit.description
                : 'You belong to no unit, so rows are ranked by the best fit any unit has. Pick a unit to see what its team sees.'}
            </p>
          )}
        </div>
        )}

        {/*
          The escape hatch. Only shown when a bar is actually in force —
          offering it to an unscoped admin, whose view is never filtered, would
          be a control that does nothing.
        */}
        {lowestBar ? (
          <div className="tm-oplist__control">
            <div className="tm-oplist__controllabel">Weaker matches</div>
            <label className="tm-oplist__toggle">
              <input
                type="checkbox"
                checked={includeWeak}
                onChange={(event) => setIncludeWeak(event.target.checked)}
              />
              <span>Show matches below {lowestBar.minFitPercent}%</span>
            </label>
            <p className="tm-oplist__controlnote">
              {includeWeak
                ? `Showing everything, including matches ${lowestBar.businessUnitName} would normally have hidden.`
                : `Hidden by default so weak matches don’t crowd the list. Worth a look if the scoring seems off.`}
            </p>
          </div>
        ) : null}
      </div>

      {list.state === 'loading' ? <LoadingState label="Loading opportunities…" /> : null}

      {list.state === 'error' ? <ErrorState error={list.error} retry={list.reload} /> : null}

      {list.state === 'ready' ? (
        list.data.length === 0 ? (
          barApplies ? (
            /*
              A DIFFERENT KIND OF EMPTY from the other three. Those mean the
              data is absent — nothing scored, nothing at bid stage. This one
              means the data EXISTS and is being deliberately withheld, so
              saying "nothing here" would be false. It names the bar and points
              at the control that reveals what is behind it.
            */
            <EmptyState
              title={`Everything is below ${lowestBar.businessUnitName}’s ${lowestBar.minFitPercent}% bar`}
              explain={`There ARE opportunities here — every one of them just scores under ${lowestBar.minFitPercent}% for ${lowestBar.businessUnitName}, so they are hidden as weak matches. Nothing failed to load and nothing is missing. Tick “Show matches below ${lowestBar.minFitPercent}%” above to see them. If they all look like they should have scored higher, that is worth telling someone — a bad score is how you spot the matching engine going wrong.`}
            />
          ) : barsUnresolved ? (
            profiles.state === 'loading' ? (
              /*
                The list came back empty and we cannot yet say WHY. Saying
                nothing for a moment is the only honest option — both real
                explanations would be a guess until the profiles land.
              */
              <LoadingState label="Checking whether the fit bar is hiding these…" />
            ) : (
              <EmptyState
                title="No opportunities here, and we cannot tell you why"
                explain="The list is empty, but the unit profiles failed to load — so we cannot say whether there is genuinely nothing, or whether everything scored below your unit’s fit bar and is being hidden as a weak match. Those mean opposite things. Reload to find out; if it keeps failing, that is worth reporting."
              />
            )
          ) : (
            <EmptyState {...explainEmpty(filter, selectedUnit?.name ?? null, unitId)} />
          )
        ) : (
          <>
            <div className="tm-oplist__count">
              {list.data.length === 1 ? '1 opportunity' : `${list.data.length} opportunities`}
              <span className="tm-oplist__countnote">
                {/*
                  Three cases, not two. An unscoped viewer who NARROWS to a unit
                  gets rows ordered by THAT unit's fit, because the server sorts
                  on your_fit_percent once a unit is in play — so claiming "the
                  best fit any unit has" here described a sort the server was no
                  longer doing.
                */}
                {isScoped
                  ? ' · ordered by your unit’s fit, best first'
                  : selectedUnit
                    ? ` · ordered by ${selectedUnit.name}’s fit, best first`
                    : ' · ordered by the best fit any unit has, best first'}
              </span>
            </div>

            <ol className="tm-oplist__rows">
              {list.data.map((row, index) => (
                // The id is a SLUG STRING ("gam-au"), never an integer — it is
                // the key and the URL segment exactly as received.
                <li key={row.id} className="tm-oplist__item">
                  <Link className="tm-oplist__row" to={`/app/opportunities/${row.id}`}>
                    <div className="tm-oplist__rank">
                      <span className="tm-oplist__rankno">{index + 1}</span>
                      <FitBlock row={row} nullFitReason={nullFitReason} />
                    </div>

                    <div className="tm-oplist__body">
                      <div className="tm-oplist__orgline">
                        <span className="tm-oplist__org">{row.org}</span>
                        <span className="tm-oplist__cat">{CATEGORY_LABEL[row.category]}</span>
                      </div>
                      <h2 className="tm-oplist__title">{row.title}</h2>
                      <p className="tm-oplist__desc">{row.desc}</p>
                      <dl className="tm-oplist__meta">
                        <div className="tm-oplist__metaitem">
                          <dt>Beneficiary</dt>
                          <dd>{row.beneficiary}</dd>
                        </div>
                        <div className="tm-oplist__metaitem">
                          <dt>Geography</dt>
                          <dd>{row.geography}</dd>
                        </div>
                        <div className="tm-oplist__metaitem">
                          <dt>Source</dt>
                          <dd>{row.source}</dd>
                        </div>
                      </dl>
                    </div>

                    <div className="tm-oplist__side">
                      <div className="tm-oplist__sideitem">
                        <div className="tm-oplist__sidelabel">Value</div>
                        {/* A display BAND ("$$$$", "unconfirmed"): text, never money. */}
                        <div className="tm-oplist__band">{row.value}</div>
                      </div>
                      <div className="tm-oplist__sideitem">
                        <div className="tm-oplist__sidelabel">Deadline</div>
                        {/* FREE TEXT, e.g. "No deadline stated" — never parsed as a date. */}
                        <div className="tm-oplist__sidevalue">{row.deadline}</div>
                      </div>
                      <div className="tm-oplist__sideitem">
                        <div className="tm-oplist__sidelabel">Relevance</div>
                        <div
                          className={`tm-oplist__rel tm-oplist__rel--${row.relevance.toLowerCase()}`}
                        >
                          {row.relevance}
                        </div>
                      </div>
                    </div>
                  </Link>
                </li>
              ))}
            </ol>
          </>
        )
      ) : null}
    </div>
  )
}

/**
 * The two fit numbers. Either can be null and neither may be faked: 0% would
 * read as "scored badly" when the truth is "not scored", so a null renders as
 * NullValue with the reason attached.
 */
function FitBlock({ row, nullFitReason }: { row: OpportunitySummary; nullFitReason: string }) {
  return (
    <div className="tm-oplist__fit">
      <div className="tm-oplist__fitrow">
        <span className="tm-oplist__fitlabel">Your fit</span>
        <span className="tm-oplist__fitvalue">
          {row.yourFitPercent === null ? (
            <NullValue reason={nullFitReason} />
          ) : (
            `${row.yourFitPercent}%`
          )}
        </span>
      </div>
      <div className="tm-oplist__meter" aria-hidden="true">
        <span
          className="tm-oplist__meterfill"
          style={{ width: `${row.yourFitPercent ?? row.topFitPercent ?? 0}%` }}
          data-null={row.yourFitPercent === null ? 'true' : undefined}
        />
      </div>
      <div className="tm-oplist__fitrow tm-oplist__fitrow--muted">
        <span className="tm-oplist__fitlabel">Top fit</span>
        <span className="tm-oplist__fitvalue">
          {row.topFitPercent === null ? (
            <NullValue reason="No unit has been scored against this opportunity yet" />
          ) : (
            `${row.topFitPercent}%`
          )}
        </span>
      </div>
    </div>
  )
}

/**
 * Why this particular combination is empty.
 *
 * Two emptinesses here are CORRECT and both will be read as a fault unless the
 * screen says otherwise: Design Teem, Ingene Studios and TM Labs have empty
 * profiles so nothing has been scored for them, and no opportunity currently
 * carries the "bid" category so the Bid now chip matches nothing. A generic
 * "no results" would leave the reader unable to tell either from a bug.
 */
function explainEmpty(
  filter: OpportunityFilter,
  unitName: string | null,
  unitId: number | '',
): { title: string; explain: string } {
  const filterLabel = FILTERS.find((option) => option.value === filter)?.label ?? 'this filter'
  const unscoredUnit = unitId !== ALL_UNITS && UNSCORED_UNIT_IDS.includes(unitId)
  const unitPhrase = unitName ?? 'this unit'

  // The unit reason comes first when it applies: an unscored unit returns zero
  // rows under EVERY chip, so blaming the chip would send the reader chasing
  // the wrong thing.
  if (unscoredUnit) {
    return {
      title: `${unitPhrase} has nothing scored yet`,
      explain:
        `Fit scores are generated from a unit's profile, and ${unitPhrase} has no profile filled in ` +
        `yet — so it scores zero opportunities no matter which filter is applied. Nothing failed to ` +
        `load. Fill in the unit's profile under Profile & Sources and its rows appear here. Switch ` +
        `the unit back to “All units” to see the full ranked list.`,
    }
  }

  if (filter === 'bid-now') {
    return {
      title: 'Nothing is at bid stage right now',
      explain:
        'The “Bid now” chip selects opportunities in the bid category, and none of the current rows ' +
        'carry it — every one of them is a watch item, a partnership or a BD lead. This is the real ' +
        'answer, not a failed request. Try “Everything” to see the full list.' +
        (unitName ? ` The ${unitName} filter is still applied as well.` : ''),
    }
  }

  if (unitName) {
    return {
      title: `No ${filterLabel.toLowerCase()} rows for ${unitName}`,
      explain:
        `${unitName} has scored opportunities, but none of them match “${filterLabel}”. The filter and ` +
        `the unit narrow the list independently, so widening either one brings rows back — start with ` +
        `“Everything”.`,
    }
  }

  if (filter === 'everything') {
    return {
      title: 'No opportunities yet',
      explain:
        'The list loaded successfully and came back with nothing in it, which means no opportunity has ' +
        'been ingested yet rather than that something went wrong. Rows appear here once a scan has run.',
    }
  }

  return {
    title: `Nothing matches “${filterLabel}”`,
    explain:
      `The request succeeded and returned no rows: no current opportunity falls under “${filterLabel}”. ` +
      `Choose “Everything” to see all of them.`,
  }
}
