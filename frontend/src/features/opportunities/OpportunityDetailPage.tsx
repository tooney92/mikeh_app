import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchOpportunity } from './api'
import { EmptyState, ErrorState, LoadingState, NullValue, useAsync } from './States'
import type { OpportunityDetail, OpportunityScore } from './types'
import './detail.css'

/**
 * One opportunity, in full.
 *
 * This screen is NOT the list row expanded. It exists to make a JOINT PITCH
 * visible: GET /api/opportunities/{id} returns EVERY business unit's score
 * regardless of the caller's own scope, so a lead deliberately sees other
 * units' numbers here. You cannot spot that another unit also fits if you
 * cannot see their score, so `scores` is the centrepiece of the page and
 * everything else is context around it.
 *
 * Four realities the contract flags, all of them correct behaviour that reads
 * as a bug unless it is labelled:
 *
 *  - `scores` OMITS units with no score. Five units exist; two rows is the
 *    normal answer. Nothing here indexes by unit id or assumes a row count —
 *    it iterates exactly what arrives, in the order it arrives, because the
 *    server has already sorted best first.
 *  - `winProbability` is null on every score today. Only the matching engine
 *    will ever set it and it does not exist yet, so 0% would be a lie.
 *  - `yourFitPercent` is null for admin and director, who belong to no unit.
 *  - `decision` is null on every opportunity — nothing has ever been logged.
 *
 * Decisions are READ-ONLY here. There is deliberately no Pursue/Watch/Reject
 * control: writing a decision is the Learning deliverable, it is not
 * contracted yet, and its endpoint requires a permission codename most callers
 * will not hold. A button that 403s is worse than no button.
 */
export function OpportunityDetailPage() {
  // A SLUG string like "gam-au" — never an integer, never parsed.
  const { opportunityId } = useParams<{ opportunityId: string }>()
  const id = opportunityId ?? ''

  // `id` is in the deps so moving between two opportunities refetches rather
  // than leaving the previous one on screen under the new URL.
  const result = useAsync(() => fetchOpportunity(id), [id])

  return (
    <main className="tm-page tm-opdetail">
      <Link className="tm-opdetail__back" to="/app/opportunities">
        ← All opportunities
      </Link>

      {result.state === 'loading' ? <LoadingState label="Loading opportunity…" /> : null}

      {result.state === 'error' ? (
        <>
          <ErrorState error={result.error} retry={result.reload} />
          <p className="tm-opdetail__stranded">
            If this address was typed or pasted, the slug may not exist —{' '}
            <Link to="/app/opportunities">go back to the list</Link> and pick from there.
          </p>
        </>
      ) : null}

      {result.state === 'ready' ? <Detail opportunity={result.data} /> : null}
    </main>
  )
}

/* ------------------------------------------------------------------------- */

function Detail({ opportunity }: { opportunity: OpportunityDetail }) {
  const jointPitch = opportunity.scores.filter((score) => score.isJointPitchCandidate)

  return (
    <>
      <div className="tm-page__kicker">
        <span className="tm-page__dash" aria-hidden="true" />
        {CATEGORY_LABEL[opportunity.category] ?? opportunity.category} · {opportunity.relevance} relevance
      </div>

      <h1 className="tm-page__title">{opportunity.title}</h1>
      <p className="tm-page__lede">{opportunity.desc}</p>

      <Facts opportunity={opportunity} />

      {jointPitch.length > 0 ? <JointPitchBanner scores={jointPitch} /> : null}

      <Scores scores={opportunity.scores} />

      <Narrative opportunity={opportunity} />

      <Lists opportunity={opportunity} />

      <Decision opportunity={opportunity} />

      <Source opportunity={opportunity} />
    </>
  )
}

/** The at-a-glance band. `value` is a display band and `deadline` is free text. */
function Facts({ opportunity }: { opportunity: OpportunityDetail }) {
  return (
    <section className="tm-opdetail__section" aria-label="Opportunity facts">
      <dl className="tm-opdetail__facts">
        <Fact label="Organisation" value={opportunity.org} />
        {/* A BAND ("$$$$"), not money — never formatted as currency. */}
        <Fact label="Value band" value={opportunity.value} />
        {/* FREE TEXT ("No deadline stated"), never parsed as a date. */}
        <Fact label="Deadline" value={opportunity.deadline} />
        <Fact label="Geography" value={opportunity.geography} />
        <Fact label="Beneficiary" value={opportunity.beneficiary} />
        <Fact label="Source" value={opportunity.source} />
        <Fact
          label="Your fit"
          value={
            opportunity.yourFitPercent === null ? (
              <NullValue reason="You belong to no business unit — admin and director accounts have no unit, so there is no “your fit” figure. Every unit's score is in the table below." />
            ) : (
              `${opportunity.yourFitPercent}%`
            )
          }
        />
        <Fact
          label="Best fit, any unit"
          value={
            opportunity.topFitPercent === null ? (
              <NullValue reason="No business unit has been scored against this opportunity yet." />
            ) : (
              `${opportunity.topFitPercent}%`
            )
          }
        />
      </dl>
    </section>
  )
}

function Fact({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="tm-opdetail__fact">
      <dt className="tm-opdetail__factlabel">{label}</dt>
      <dd className="tm-opdetail__factvalue">{value}</dd>
    </div>
  )
}

/**
 * The joint-pitch signal, above the table so it is the first thing read.
 * Two or more units scoring 60+ is the thing this whole screen exists to
 * surface, so it gets the loudest treatment on the page.
 */
function JointPitchBanner({ scores }: { scores: OpportunityScore[] }) {
  /**
   * DISTINCT notes only.
   *
   * The API gives every flagged score the SAME sentence by construction — it
   * is the one string priority-actions also uses, so one rule produces one
   * wording. Listing it per score therefore printed the identical sentence
   * once per unit, which reads as a rendering fault rather than emphasis.
   *
   * Empty string, not null, is the "nothing to say" value here, so both are
   * filtered out.
   */
  const notes = [
    ...new Set(scores.map((score) => score.jointPitchNote).filter((note) => !!note)),
  ]

  return (
    <section className="tm-opdetail__joint" aria-label="Joint pitch signal">
      <div className="tm-opdetail__jointflag">Joint pitch candidate</div>
      <p className="tm-opdetail__jointlede">
        {scores.length === 1
          ? `${scores[0].businessUnitName} is flagged for a joint pitch on this opportunity.`
          : `${scores.length} units score high enough here to go in together: ${scores
              .map((score) => score.businessUnitName)
              .join(', ')}.`}
      </p>

      {/* Only rendered when a note actually exists — never an empty element. */}
      {notes.length > 0 ? (
        <ul className="tm-opdetail__jointnotes">
          {notes.map((note) => (
            <li className="tm-opdetail__jointnote" key={note}>
              {note}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}

/**
 * The centrepiece. Every unit that HAS a score, in the server's order.
 *
 * Units with no score are absent from the array rather than present with null,
 * so there is no placeholder row for them — inventing five rows would imply
 * scores that were never calculated.
 */
function Scores({ scores }: { scores: OpportunityScore[] }) {
  return (
    <section className="tm-opdetail__section" aria-labelledby="tm-opdetail-scores">
      <h2 className="tm-opdetail__heading" id="tm-opdetail-scores">
        Every unit's score
      </h2>
      <p className="tm-opdetail__subhead">
        Not filtered to your unit. This is the whole point of the detail screen: you cannot spot
        that another unit also fits unless you can see their number.
      </p>

      {scores.length === 0 ? (
        <EmptyState
          title="No unit has been scored on this opportunity"
          explain="Scoring runs per unit against its profile, and none has produced a score here yet. Units that have not been scored are left out entirely rather than shown as zero."
        />
      ) : (
        <>
          <ol className="tm-opdetail__scores">
            <li className="tm-opdetail__scorehead" aria-hidden="true">
              <span className="tm-opdetail__col tm-opdetail__col--unit">Business unit</span>
              <span className="tm-opdetail__col tm-opdetail__col--fit">Fit</span>
              <span className="tm-opdetail__col tm-opdetail__col--win">Win probability</span>
            </li>

            {scores.map((score) => (
              <ScoreRow key={score.businessUnitId} score={score} />
            ))}
          </ol>

          <p className="tm-opdetail__note">
            Showing {scores.length} scored {scores.length === 1 ? 'unit' : 'units'}. Units with no
            score against this opportunity are not listed.
          </p>
        </>
      )}
    </section>
  )
}

function ScoreRow({ score }: { score: OpportunityScore }) {
  const fit = Math.max(0, Math.min(100, score.fitPercent))

  return (
    <li
      className={
        score.isJointPitchCandidate
          ? 'tm-opdetail__score tm-opdetail__score--joint'
          : 'tm-opdetail__score'
      }
    >
      <div className="tm-opdetail__col tm-opdetail__col--unit">
        <span className="tm-opdetail__initials" aria-hidden="true">
          {score.initials}
        </span>
        <span className="tm-opdetail__unit">
          <span className="tm-opdetail__unitname">{score.businessUnitName}</span>
          {score.isJointPitchCandidate ? (
            <span className="tm-opdetail__jointtag">Joint pitch</span>
          ) : null}
        </span>
      </div>

      <div className="tm-opdetail__col tm-opdetail__col--fit">
        <span className="tm-opdetail__collabel">Fit</span>
        <span className="tm-opdetail__fitvalue">{score.fitPercent}%</span>
        <span className="tm-opdetail__bar">
          <span className="tm-opdetail__barfill" style={{ width: `${fit}%` }} />
        </span>
      </div>

      <div className="tm-opdetail__col tm-opdetail__col--win">
        <span className="tm-opdetail__collabel">Win probability</span>
        {/* Null on EVERY score today. 0% would be a lie; a blank cell reads as
            a rendering fault, so it is an explained em dash. */}
        {score.winProbability === null ? (
          <NullValue reason="Win probability is set by the matching engine, which is not built yet. No opportunity has one today." />
        ) : (
          <span className="tm-opdetail__winvalue">{score.winProbability}%</span>
        )}
      </div>

      {/*
        The note is NOT repeated per row. Every flagged score carries the same
        sentence by construction, and the banner above already states it once —
        printing it again under each row was the same text three times on one
        screen. The row keeps its "Joint pitch" tag, which is the per-row fact;
        the explanation belongs to the opportunity, not to each unit.
      */}
    </li>
  )
}

/** The written case. All four fields are plain strings on the contract. */
function Narrative({ opportunity }: { opportunity: OpportunityDetail }) {
  const blocks: { label: string; text: string }[] = [
    { label: 'Positioning', text: opportunity.positioning },
    { label: 'Why it matters', text: opportunity.whyItMatters },
    { label: 'Why now', text: opportunity.whyNow },
    { label: 'Recommendation', text: opportunity.recommendation },
  ].filter((block) => block.text.trim().length > 0)

  if (blocks.length === 0) return null

  return (
    <section className="tm-opdetail__section" aria-labelledby="tm-opdetail-case">
      <h2 className="tm-opdetail__heading" id="tm-opdetail-case">
        The case
      </h2>
      <div className="tm-opdetail__prose">
        {blocks.map((block) => (
          <div className="tm-opdetail__block" key={block.label}>
            <div className="tm-opdetail__blocklabel">{block.label}</div>
            <p className="tm-opdetail__blocktext">{block.text}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

/** Four arrays that may each be empty. An empty one renders nothing at all. */
function Lists({ opportunity }: { opportunity: OpportunityDetail }) {
  const lists: { label: string; items: string[] }[] = [
    { label: 'Credentials', items: opportunity.credentials },
    { label: 'Partners', items: opportunity.partners },
    { label: 'Themes', items: opportunity.themes },
    { label: 'Approach', items: opportunity.approach },
  ].filter((list) => list.items.length > 0)

  if (lists.length === 0) return null

  return (
    <section className="tm-opdetail__section" aria-labelledby="tm-opdetail-what">
      <h2 className="tm-opdetail__heading" id="tm-opdetail-what">
        What we bring
      </h2>
      <div className="tm-opdetail__lists">
        {lists.map((list) => (
          <div className="tm-opdetail__list" key={list.label}>
            <div className="tm-opdetail__listlabel">{list.label}</div>
            <ul className="tm-opdetail__listitems">
              {list.items.map((item) => (
                <li className="tm-opdetail__listitem" key={item}>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  )
}

/**
 * The latest logged decision, READ-ONLY.
 *
 * Null on every opportunity today because none has ever been logged, which is
 * a different thing from "failed to load" — so it says so in words. There is
 * no control to set one: that is the Learning deliverable and it is not
 * contracted yet.
 */
function Decision({ opportunity }: { opportunity: OpportunityDetail }) {
  return (
    <section className="tm-opdetail__section" aria-labelledby="tm-opdetail-decision">
      <h2 className="tm-opdetail__heading" id="tm-opdetail-decision">
        Decision
      </h2>

      {opportunity.decision === null ? (
        <EmptyState
          title="No decision logged yet"
          explain="Nobody has recorded a Pursue, Partner, Watch or Reject against this opportunity. Logging one is part of the Learning screen, which is not built yet, so this page only reads decisions — it cannot make one."
        />
      ) : (
        <div className="tm-opdetail__decision">
          <div className="tm-opdetail__decisionvalue">{opportunity.decision}</div>
          {opportunity.decisionReason ? (
            <p className="tm-opdetail__decisionreason">{opportunity.decisionReason}</p>
          ) : (
            <p className="tm-opdetail__decisionreason tm-opdetail__decisionreason--none">
              No reason was recorded with this decision.
            </p>
          )}
          <p className="tm-opdetail__note">
            Read-only here. Decisions are logged on the Learning screen.
          </p>
        </div>
      )}
    </section>
  )
}

function Source({ opportunity }: { opportunity: OpportunityDetail }) {
  if (!opportunity.sourceUrl) return null

  return (
    <section className="tm-opdetail__section" aria-label="Source">
      <a
        className="tm-opdetail__source"
        href={opportunity.sourceUrl}
        target="_blank"
        rel="noreferrer"
      >
        Open the original listing ↗
      </a>
      <span className="tm-opdetail__sourceurl">{opportunity.sourceUrl}</span>
    </section>
  )
}

/**
 * `category` is the row vocabulary ('bid' | 'watch' | 'partnership' | 'bd'),
 * NOT the filter vocabulary — the two differ, so this maps only what it is
 * given and falls back to the raw value for anything new.
 */
const CATEGORY_LABEL: Record<string, string> = {
  bid: 'Bid now',
  watch: 'Watch',
  partnership: 'Partnership',
  bd: 'BD lead',
}
