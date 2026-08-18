import { useState, type FormEvent } from 'react'
import { EmptyState, ErrorState, LoadingState, useAsync } from '../opportunities/States'
import {
  FIELD_LABEL,
  applied,
  describeWriteError,
  diffProfile,
  fetchProfiles,
  linesOf,
  normaliseLines,
  updateProfile,
} from './api'
import type { ProfileUpdate, UnitProfile } from './types'
import type { WriteFailure } from './api'

/**
 * The five unit profiles — what the matching engine scores opportunities
 * against, and the one place they can be changed.
 *
 * THE RULE THIS FILE EXISTS TO FOLLOW: the edit affordance comes from
 * `profile.canEdit` and from nothing else. Not from `user.permissions`, not
 * from `user.businessUnits`, not from the role name. `canEdit` is produced by
 * the same server function that the PUT enforces, so the button and the write
 * cannot disagree. Every client-side re-derivation of the same question has
 * been a fail-open bug, which is why the backend removed the last one.
 *
 * Three things here look wrong and are correct:
 *
 * 1. ALL FIVE profiles are shown to EVERYONE. The endpoint is never scoped.
 *    A member of TM Foundation sees Takeout Media's positioning, on purpose —
 *    reading what a peer unit is chasing is how a joint pitch gets spotted.
 *    Rows the caller cannot edit are visibly read-only, never hidden.
 *
 * 2. Three of the five are effectively blank. That is the state of the data,
 *    it is WHY those units return no opportunities, and it must read as work
 *    to do rather than as a failed load. See UnfilledNotice.
 *
 * 3. `neverShow` is NOT a filter. Nothing consults it. See NeverShowBlock.
 */

/** The four newline-separated list fields, in reading order. */
const LIST_FIELDS = [
  {
    key: 'priorities',
    label: 'Priorities',
    hint: 'What this unit is actively chasing.',
  },
  {
    key: 'capabilities',
    label: 'Capabilities',
    hint: 'What it can deliver. The strongest signal the matching engine has.',
  },
  {
    key: 'credentials',
    label: 'Credentials',
    hint: 'Work already done that proves the capability.',
  },
] as const satisfies readonly { key: keyof UnitProfile; label: string; hint: string }[]

/**
 * Whether this profile has never really been filled in.
 *
 * Derived from the CONTENT, deliberately not from a list of unit ids: Design
 * Teem, Ingene Studios and TM Labs are the three today, and the moment somebody
 * fills one in this notice must stop appearing for it without a code change.
 *
 * Priorities and credentials are the test because they are exactly what the
 * seed had nothing to put in — those three units were created from their
 * one-line description alone, which is why they carry a positioning and a
 * token capability or two and nothing else.
 */
function isUnfilled(profile: UnitProfile): boolean {
  return linesOf(profile.priorities).length === 0 && linesOf(profile.credentials).length === 0
}

export function UnitProfilesSection() {
  const request = useAsync(() => fetchProfiles(), [])

  return (
    <section className="tm-prof__section" aria-labelledby="tm-prof-profiles">
      <div className="tm-prof__sectionhead">
        <h2 className="tm-prof__sectiontitle" id="tm-prof-profiles">
          Unit profiles
        </h2>
        <span className="tm-prof__sectioncount">
          {request.state === 'ready' ? `${request.data.length} units` : ''}
        </span>
      </div>

      <p className="tm-prof__sectionlede">
        Every opportunity is scored against these. A unit with a thin profile scores badly, and a
        unit with an empty one scores nothing at all — so this screen is where the Radar gets its
        answers, not just a settings page.
      </p>

      {request.state === 'loading' ? <LoadingState label="Loading unit profiles…" /> : null}
      {request.state === 'error' ? <ErrorState error={request.error} retry={request.reload} /> : null}
      {/*
        Mounted only once the fetch is ready, so the list below owns its rows
        from that point and can replace one from a PUT response without a
        second request and without a loading flash across the whole section.
      */}
      {request.state === 'ready' ? <ProfileList loaded={request.data} /> : null}
    </section>
  )
}

function ProfileList({ loaded }: { loaded: UnitProfile[] }) {
  const [profiles, setProfiles] = useState(loaded)

  /**
   * How many rows this caller may edit, counted from the SERVER's flags rather
   * than worked out from their permissions. It is stated up front because
   * "four of these five are read-only for me" should be a fact the reader is
   * given, not a conclusion they draw from greyed-out buttons.
   */
  const editable = profiles.filter((profile) => profile.canEdit).length

  if (profiles.length === 0) {
    return (
      <EmptyState
        title="No unit profiles came back"
        explain="This endpoint always returns one profile per business unit — five of them — for every account, so an empty list means the profiles are missing from the database rather than that anything was filtered out. Nothing on this screen can fix that; it needs someone with database access."
      />
    )
  }

  return (
    <>
      <p className="tm-prof__scopenote">
        {editable === profiles.length
          ? 'You can edit all five.'
          : editable === 0
            ? 'All five are read-only for your account. You can read every one of them — that is deliberate, not a permission fault.'
            : `You can edit ${editable} of these ${profiles.length}. The rest are read-only for you and shown in full anyway.`}
      </p>

      <div className="tm-prof__cards">
        {profiles.map((profile) => (
          <ProfileCard
            key={profile.id}
            profile={profile}
            onSaved={(updated) =>
              setProfiles((rows) => rows.map((row) => (row.id === updated.id ? updated : row)))
            }
          />
        ))}
      </div>
    </>
  )
}

/* --------------------------------------------------------------- card --- */

/** What the last save attempt produced, in the words shown to the reader. */
type SaveNotice =
  | { kind: 'none' }
  /** The request was never made — the form matched the profile on record. */
  | { kind: 'unchanged' }
  | { kind: 'saved'; fields: string[] }
  /** 200, but the returned profile does not match what was sent. Never quiet. */
  | { kind: 'mismatch'; fields: string[] }
  | { kind: 'failed'; failure: WriteFailure }

function ProfileCard({
  profile,
  onSaved,
}: {
  profile: UnitProfile
  onSaved: (updated: UnitProfile) => void
}) {
  const [editing, setEditing] = useState(false)
  const [notice, setNotice] = useState<SaveNotice>({ kind: 'none' })
  const unfilled = isUnfilled(profile)

  function openEditor() {
    setNotice({ kind: 'none' })
    setEditing(true)
  }

  return (
    <article
      className={[
        'tm-prof__card',
        profile.canEdit ? 'tm-prof__card--editable' : 'tm-prof__card--readonly',
        unfilled ? 'tm-prof__card--unfilled' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      aria-labelledby={`tm-prof-unit-${profile.id}`}
    >
      <header className="tm-prof__cardhead">
        <span className="tm-prof__initials" aria-hidden="true">
          {profile.initials}
        </span>
        <div className="tm-prof__cardtitles">
          <h3 className="tm-prof__unit" id={`tm-prof-unit-${profile.id}`}>
            {profile.businessUnitName}
          </h3>
          {/*
            positioning is never null — it is "" when unset — so an empty one is
            said in words rather than left as a gap that reads as a render fault.
          */}
          <p className="tm-prof__positioning">
            {profile.positioning.trim() || (
              <span className="tm-prof__blank">No positioning statement written yet.</span>
            )}
          </p>
        </div>

        {/*
          THE ONE INPUT TO THIS DECISION IS profile.canEdit. Anything else here
          — a permissions lookup, a unit-membership test — would be a second,
          drift-prone copy of a rule the server already answered.
        */}
        <div className="tm-prof__cardaction">
          {profile.canEdit ? (
            editing ? null : (
              <button className="tm-prof__edit" type="button" onClick={openEditor}>
                Edit
              </button>
            )
          ) : (
            <span
              className="tm-prof__lock"
              title="The server decides this per profile and per account; the form is only offered where it would actually be accepted."
            >
              Read-only
            </span>
          )}
        </div>
      </header>

      {unfilled ? <UnfilledNotice profile={profile} onStart={openEditor} /> : null}

      <SaveNoticeBlock notice={notice} />

      {editing ? (
        <ProfileEditor
          profile={profile}
          onCancel={() => setEditing(false)}
          onResult={(result, updated) => {
            if (updated) onSaved(updated)
            setNotice(result)
            // The editor stays open on anything short of a clean save, so the
            // typed values are still there to correct or retry.
            if (result.kind === 'saved' || result.kind === 'unchanged') setEditing(false)
          }}
        />
      ) : (
        <ProfileBody profile={profile} />
      )}
    </article>
  )
}

/**
 * The single most important empty state on this screen.
 *
 * Three of five units land here. It is NOT a loading failure and it is NOT a
 * permission problem — it is unstarted work with a visible consequence, and it
 * says which consequence, because "Design Teem has no opportunities" is
 * otherwise read as the Opportunities screen being broken.
 */
function UnfilledNotice({ profile, onStart }: { profile: UnitProfile; onStart: () => void }) {
  return (
    <div className="tm-prof__todo">
      <div className="tm-prof__todotitle">Not filled in yet</div>
      <p className="tm-prof__todotext">
        {profile.businessUnitName} has only the one-line description it was set up with. Opportunities
        are scored against the priorities, capabilities and credentials below, so while those are
        blank this unit scores <strong>nothing</strong> — which is exactly why it has no rows on the
        Radar or in the opportunity list. Nothing failed to load here; this is work waiting to be
        done, and doing it is what switches the unit on.
      </p>
      {profile.canEdit ? (
        <button className="tm-prof__todostart" type="button" onClick={onStart}>
          Fill in {profile.businessUnitName}
        </button>
      ) : (
        <p className="tm-prof__todotext tm-prof__todotext--muted">
          Your account cannot edit this one, so it needs somebody on {profile.businessUnitName} who
          can.
        </p>
      )}
    </div>
  )
}

function ProfileBody({ profile }: { profile: UnitProfile }) {
  return (
    <div className="tm-prof__body">
      <FitBar profile={profile} />

      <div className="tm-prof__lists">
        {LIST_FIELDS.map((field) => (
          <ListBlock
            key={field.key}
            label={field.label}
            hint={field.hint}
            /* NEWLINE-SEPARATED STRING, not an array — split, never mapped. */
            lines={linesOf(profile[field.key])}
            unitName={profile.businessUnitName}
          />
        ))}
        <NeverShowBlock profile={profile} />
      </div>
    </div>
  )
}

function ListBlock({
  label,
  hint,
  lines,
  unitName,
}: {
  label: string
  hint: string
  lines: string[]
  unitName: string
}) {
  return (
    <div className="tm-prof__list">
      <div className="tm-prof__listlabel">{label}</div>
      {lines.length === 0 ? (
        <p className="tm-prof__blank">
          Nothing listed for {unitName} yet — this one is blank on the server, not missing from the
          page.
        </p>
      ) : (
        <ul className="tm-prof__items">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <p className="tm-prof__listhint">{hint}</p>
    </div>
  )
}

/**
 * `neverShow` gets its own block because it must NOT read as an active filter.
 *
 * Nothing in the service consults this field. Takeout Media's already says
 * "Opportunities under roughly NGN 20m" and opportunities under NGN 20m are
 * shown to Takeout Media regardless — no query touches it. Presenting it as an
 * exclusion rule would leave the client believing a rule is running when it is
 * not, which is worse than not showing it at all.
 *
 * So it is labelled as guidance for a matching engine that does not exist yet,
 * every time, including on the units where it has content.
 */
function NeverShowBlock({ profile }: { profile: UnitProfile }) {
  const lines = linesOf(profile.neverShow)

  return (
    <div className="tm-prof__list tm-prof__list--never">
      <div className="tm-prof__listlabel">
        Never show <span className="tm-prof__tag">Not applied</span>
      </div>
      {lines.length === 0 ? (
        <p className="tm-prof__blank">Nothing written down for {profile.businessUnitName} yet.</p>
      ) : (
        <ul className="tm-prof__items tm-prof__items--never">
          {lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <p className="tm-prof__listhint tm-prof__listhint--warn">
        This filters nothing today. It is guidance being recorded for the matching engine that will
        eventually use it — no query consults it, so anything written here is still shown in the
        opportunity list and on the Radar.
      </p>
    </div>
  )
}

/**
 * The fit bar, with the consequence of changing it stated next to the number.
 *
 * This is not an innocuous setting: it decides what an entire team sees. An
 * opportunity scoring below it is hidden from that unit's list AND its radar,
 * for every member of the unit, not just for whoever changed it.
 */
function FitBar({ profile }: { profile: UnitProfile }) {
  return (
    <div className="tm-prof__bar">
      <div className="tm-prof__barhead">
        <span className="tm-prof__barlabel">Fit bar</span>
        <span className="tm-prof__barvalue">{profile.minFitPercent}%</span>
      </div>
      <div className="tm-prof__bartrack" aria-hidden="true">
        <span className="tm-prof__barfill" style={{ width: `${profile.minFitPercent}%` }} />
      </div>
      <p className="tm-prof__barnote">
        Anything scoring under {profile.minFitPercent}% for {profile.businessUnitName} is hidden from
        the opportunity list and the Radar for <strong>everyone on that team</strong>, not just for
        you. Raise it and the whole unit sees less; lower it and weaker matches come back.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------- editor --- */

interface Draft {
  positioning: string
  priorities: string
  capabilities: string
  credentials: string
  neverShow: string
  /** Kept as text: a number input hands back a string, and "" is a real state. */
  minFit: string
}

function draftFrom(profile: UnitProfile): Draft {
  return {
    positioning: profile.positioning,
    priorities: profile.priorities,
    capabilities: profile.capabilities,
    credentials: profile.credentials,
    neverShow: profile.neverShow,
    minFit: String(profile.minFitPercent),
  }
}

function ProfileEditor({
  profile,
  onCancel,
  onResult,
}: {
  profile: UnitProfile
  onCancel: () => void
  onResult: (result: SaveNotice, updated: UnitProfile | null) => void
}) {
  const [draft, setDraft] = useState<Draft>(() => draftFrom(profile))
  const [saving, setSaving] = useState(false)
  const [barError, setBarError] = useState<string | null>(null)

  const id = (field: string) => `tm-prof-${profile.id}-${field}`

  function set<K extends keyof Draft>(field: K, value: Draft[K]) {
    setDraft((current) => ({ ...current, [field]: value }))
  }

  async function submit(event: FormEvent) {
    event.preventDefault()

    /*
      Client-side check first. The range is INCLUSIVE 0-100; -1 and 101 both
      return 422, and a 422 body is an array of validation objects rather than
      a sentence, so catching it here gives the reader something readable. The
      server check is still the real one — see describeWriteError.
    */
    const bar = draft.minFit.trim()
    if (!/^\d{1,3}$/.test(bar) || Number(bar) > 100) {
      setBarError('The fit bar must be a whole number from 0 to 100.')
      return
    }
    setBarError(null)

    const wanted: ProfileUpdate = {
      positioning: normaliseLines(draft.positioning),
      priorities: normaliseLines(draft.priorities),
      capabilities: normaliseLines(draft.capabilities),
      credentials: normaliseLines(draft.credentials),
      neverShow: normaliseLines(draft.neverShow),
      minFitPercent: Number(bar),
    }

    /*
      Only what actually changed goes on the wire. PUT is partial, and an empty
      body returns 200 having done nothing — so an unchanged form is answered
      here instead of being sent and mistaken for a successful save.
    */
    const changes = diffProfile(profile, wanted)
    if (Object.keys(changes).length === 0) {
      onResult({ kind: 'unchanged' }, null)
      return
    }

    setSaving(true)
    try {
      const updated = await updateProfile(profile.id, changes)

      /*
        The confirmation is built from the RETURNED OBJECT, never from the 200.
        If the server accepted the request but the response does not carry the
        values that were sent, that is reported as a mismatch rather than as a
        save — silently claiming success there is precisely how a screen tells
        the client a change landed when it did not.
      */
      const done = applied(changes, updated)
      const labels = done.map((field) => FIELD_LABEL[field])
      const sent = Object.keys(changes).length

      if (done.length === sent) {
        onResult({ kind: 'saved', fields: labels }, updated)
      } else {
        onResult({ kind: 'mismatch', fields: labels }, updated)
      }
    } catch (error) {
      onResult({ kind: 'failed', failure: describeWriteError(error, 'profile') }, null)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="tm-prof__form" onSubmit={submit}>
      <div className="tm-prof__field">
        <label className="tm-prof__fieldlabel" htmlFor={id('positioning')}>
          Positioning
        </label>
        <textarea
          id={id('positioning')}
          className="tm-prof__textarea"
          rows={2}
          value={draft.positioning}
          onChange={(event) => set('positioning', event.target.value)}
        />
        <p className="tm-prof__fieldhint">One or two lines on what this unit is.</p>
      </div>

      {/*
        Textareas, because these four fields are NEWLINE-SEPARATED STRINGS on
        the wire and go back as newline-separated strings. There is no array
        anywhere in this exchange and no delimiter to build.
      */}
      {LIST_FIELDS.map((field) => (
        <div className="tm-prof__field" key={field.key}>
          <label className="tm-prof__fieldlabel" htmlFor={id(field.key)}>
            {field.label}
          </label>
          <textarea
            id={id(field.key)}
            className="tm-prof__textarea"
            rows={5}
            value={draft[field.key]}
            onChange={(event) => set(field.key, event.target.value)}
          />
          <p className="tm-prof__fieldhint">One per line. {field.hint}</p>
        </div>
      ))}

      <div className="tm-prof__field">
        <label className="tm-prof__fieldlabel" htmlFor={id('neverShow')}>
          Never show
        </label>
        <textarea
          id={id('neverShow')}
          className="tm-prof__textarea"
          rows={4}
          value={draft.neverShow}
          onChange={(event) => set('neverShow', event.target.value)}
        />
        <p className="tm-prof__fieldhint tm-prof__fieldhint--warn">
          One per line. Saved, but <strong>not applied to anything</strong> — nothing filters on this
          field yet. Writing a rule here will not hide a single opportunity.
        </p>
      </div>

      <div className="tm-prof__field tm-prof__field--bar">
        <label className="tm-prof__fieldlabel" htmlFor={id('minFit')}>
          Fit bar (%)
        </label>
        <input
          id={id('minFit')}
          className="tm-prof__number"
          type="number"
          min={0}
          max={100}
          step={1}
          inputMode="numeric"
          value={draft.minFit}
          aria-describedby={id('minFit-hint')}
          aria-invalid={barError ? true : undefined}
          onChange={(event) => set('minFit', event.target.value)}
        />
        <p className="tm-prof__fieldhint tm-prof__fieldhint--warn" id={id('minFit-hint')}>
          0 to 100. This changes what <strong>the whole {profile.businessUnitName} team</strong>{' '}
          sees: every opportunity scoring below it disappears from their list and their Radar.
        </p>
        {barError ? <p className="tm-prof__fielderror">{barError}</p> : null}
      </div>

      <div className="tm-prof__formactions">
        <button className="tm-prof__save" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save changes'}
        </button>
        <button className="tm-prof__cancel" type="button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
        <span className="tm-prof__formnote">Only the fields you changed are sent.</span>
      </div>
    </form>
  )
}

/**
 * The outcome of the last save. Four distinct things are said differently on
 * purpose — "nothing to save", "saved these", "the server did not apply what
 * it accepted", and "it failed" are four different pieces of news, and folding
 * any of them into a generic green tick would misinform.
 */
function SaveNoticeBlock({ notice }: { notice: SaveNotice }) {
  if (notice.kind === 'none') return null

  if (notice.kind === 'unchanged') {
    return (
      <div className="tm-prof__notice tm-prof__notice--flat" role="status">
        <strong>Nothing to save.</strong> The form matched what is already on record, so no request
        was sent.
      </div>
    )
  }

  if (notice.kind === 'saved') {
    return (
      <div className="tm-prof__notice tm-prof__notice--ok" role="status">
        <strong>Saved.</strong> {notice.fields.join(', ')} updated — confirmed against the profile
        the server sent back, not just the response code.
      </div>
    )
  }

  if (notice.kind === 'mismatch') {
    return (
      <div className="tm-prof__notice tm-prof__notice--loud" role="alert">
        <strong>The server accepted the change but did not apply all of it.</strong>{' '}
        {notice.fields.length > 0
          ? `Only ${notice.fields.join(', ')} came back with the new value.`
          : 'None of the fields came back with the new value.'}{' '}
        What is shown above is what the server actually holds. Worth reporting — this should not
        happen.
      </div>
    )
  }

  return (
    <div
      className={
        notice.failure.loud
          ? 'tm-prof__notice tm-prof__notice--loud'
          : 'tm-prof__notice tm-prof__notice--warn'
      }
      role="alert"
    >
      <strong>{notice.failure.title}.</strong> {notice.failure.message}
    </div>
  )
}
