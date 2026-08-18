import { Fragment, useEffect, useMemo, useState, type FormEvent } from 'react'
import { PERMISSIONS, can } from '../auth/permissions'
import { useAuth } from '../auth/useAuth'
import { EmptyState, ErrorState, LoadingState, useAsync } from '../opportunities/States'
import {
  SOURCE_UPDATE,
  createSource,
  deleteSource,
  describeWriteError,
  fetchSources,
  formatStamp,
  patchSource,
} from './api'
import type { WriteFailure } from './api'
import {
  SOURCE_SCOPES,
  SOURCE_TYPES,
  type Provenance,
  type Source,
  type SourceCreate,
  type SourceRole,
} from './types'

/**
 * The sources swept each week: where opportunities are meant to come from.
 *
 * FOUR TRAPS LIVE ON THIS SCREEN, all of them already caught once:
 *
 * 1. READING THIS LIST IS GATED ON BEING SIGNED IN, NOT ON `source:read`.
 *    The endpoint never checks that codename. member.foundation holds NO
 *    source permission whatsoever and receives all 15 rows — verified live.
 *    Gate the list on `source:read` and a member gets an empty screen for data
 *    the API is willingly serving. Only the WRITE controls are gated, on the
 *    write codenames.
 *
 * 2. PATCH IS NARROWER THAN POST. Creation takes type, category and scope;
 *    the edit endpoint accepts only name, url and active, and silently ignores
 *    the other three (verified: PATCH {"category":"ZZZ"} returns 200 with the
 *    original category). So the edit form does not offer them and says so.
 *
 * 3. `scope` IS A STALE VOCABULARY — takeout | foundation | both — from before
 *    the five-unit model. Three of the five units cannot be expressed in it.
 *    It is shown as the raw string and never mapped onto business units.
 *
 * 4. THE CRAWL FIELDS ARE MOSTLY NULL and `lastCheckedAt` is null on EVERY
 *    row, including rows that carry a status. A blank or a dash there reads as
 *    a failed render, so both cases are said in words.
 *
 * The list is built for ~85 rows, not the 15 there are today: deliverable #4
 * imports the client's 81 platforms into this same endpoint. Hence search and
 * the three filters. There is no pagination because the API has none, and
 * faking it client-side over a bare array buys nothing.
 */

/** The three PATCH-able keys, named for a save confirmation. */
const PATCH_LABEL = { name: 'name', url: 'URL', active: 'state' } as const

/** Column count, so the expanding edit/confirm rows can span the table. */
function columnCount(canWrite: boolean): number {
  return canWrite ? 7 : 6
}

export function SourcesSection() {
  const { user } = useAuth()
  const permissions = user?.permissions ?? []

  /*
    Controls only. The LIST above is never gated on any of these — see trap 1.
    Only director and admin hold these three; lead and member get a 403 from
    the endpoints, which is why they are not offered the buttons at all.
  */
  const canCreate = can(permissions, PERMISSIONS.sourceCreate)
  const canUpdate = can(permissions, SOURCE_UPDATE)
  const canDelete = can(permissions, PERMISSIONS.sourceDelete)

  const request = useAsync(() => fetchSources(), [])

  return (
    <section className="tm-prof__section" aria-labelledby="tm-prof-sources">
      <div className="tm-prof__sectionhead">
        <h2 className="tm-prof__sectiontitle" id="tm-prof-sources">
          Sources
        </h2>
        <span className="tm-prof__sectioncount">
          {request.state === 'ready'
            ? `${request.data.length} ${request.data.length === 1 ? 'source' : 'sources'}`
            : ''}
        </span>
      </div>

      <p className="tm-prof__sectionlede">
        The sites and feeds the weekly sweep walks. Everyone signed in can read this list, whatever
        their role.{' '}
        {canCreate || canUpdate || canDelete
          ? 'You can change it.'
          : 'Changing it needs a director or an administrator.'}
      </p>

      {request.state === 'loading' ? <LoadingState label="Loading sources…" /> : null}
      {request.state === 'error' ? <ErrorState error={request.error} retry={request.reload} /> : null}
      {request.state === 'ready' ? (
        <SourceTable
          loaded={request.data}
          canCreate={canCreate}
          canUpdate={canUpdate}
          canDelete={canDelete}
        />
      ) : null}
    </section>
  )
}

/* -------------------------------------------------------------- table --- */

type ActiveFilter = 'all' | 'active' | 'paused'

/** A one-line result of the last write, shown above the table. */
type Banner = { tone: 'ok' | 'warn' | 'loud'; text: string } | null

function SourceTable({
  loaded,
  canCreate,
  canUpdate,
  canDelete,
}: {
  loaded: Source[]
  canCreate: boolean
  canUpdate: boolean
  canDelete: boolean
}) {
  /*
    Rows are held here and updated from each write's RESPONSE — the created row
    from the 201, the updated row from the PATCH, removal on the 204 — rather
    than by refetching. Refetching would blank the whole table behind a loading
    state on every toggle, and at 85 rows that flash is worse than the saving.
  */
  const [rows, setRows] = useState(loaded)
  const [banner, setBanner] = useState<Banner>(null)

  const [search, setSearch] = useState('')
  const [type, setType] = useState('all')
  const [category, setCategory] = useState('all')
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>('all')
  /*
    Provenance is a FIXED two-value filter, not derived from the rows like type
    and category are. The values are a contracted enum rather than free text, so
    deriving them would make the control disappear on a list that happened to
    hold only one — and "show me the ones I sent you" is the first question the
    client asks of a 90-row list she contributed 81 rows to.
  */
  const [from, setFrom] = useState<'all' | Provenance>('all')

  const [creating, setCreating] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  const canWrite = canUpdate || canDelete

  /*
    Filter options are DERIVED FROM THE ROWS, not hardcoded. `category` is free
    text — today's 15 rows carry eight different ones, and deliverable #4 will
    bring more — so a fixed list would go stale the day the import lands. Type
    is derived for the same reason: the server does not validate it either.
  */
  const types = useMemo(
    () => [...new Set(rows.map((row) => row.type))].sort((a, b) => a.localeCompare(b)),
    [rows],
  )
  const categories = useMemo(
    () => [...new Set(rows.map((row) => row.category).filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [rows],
  )

  /*
    Reconcile the SELECTION against the options whenever the rows change.

    Because both lists are derived from the rows, deleting the last source in a
    category removes that option from the dropdown while the state still holds
    it. The select falls back to displaying "All categories" — its value no
    longer matches any option — while the table goes on filtering by the value
    that vanished. The result is "Nothing matches those filters" sitting beside
    a dropdown insisting no filter is set, with no control able to clear it.
  */
  useEffect(() => {
    if (type !== 'all' && !types.includes(type)) setType('all')
  }, [types, type])

  useEffect(() => {
    if (category !== 'all' && !categories.includes(category)) setCategory('all')
  }, [categories, category])

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return rows.filter((row) => {
      if (type !== 'all' && row.type !== type) return false
      if (category !== 'all' && row.category !== category) return false
      if (from !== 'all' && row.provenance !== from) return false
      if (activeFilter === 'active' && !row.active) return false
      if (activeFilter === 'paused' && row.active) return false
      if (!needle) return true
      /*
        Her own words are searchable too. clientOpportunityType is the only
        text on an imported row that describes what the source actually
        carries — "grants, calls for proposals, fellowships" — and our
        `category` is empty on all 75 created rows, so without this a search
        for "grants" across her 81 sources would find almost nothing.
      */
      return (
        row.name.toLowerCase().includes(needle) ||
        row.url.toLowerCase().includes(needle) ||
        row.category.toLowerCase().includes(needle) ||
        row.clientOpportunityType.toLowerCase().includes(needle) ||
        row.clientSectors.toLowerCase().includes(needle)
      )
    })
  }, [rows, search, type, category, from, activeFilter])

  const filtered = visible.length !== rows.length

  function replaceRow(updated: Source) {
    setRows((current) => current.map((row) => (row.id === updated.id ? updated : row)))
  }

  async function toggleActive(row: Source) {
    setBanner(null)
    try {
      const updated = await patchSource(row.id, { active: !row.active })
      replaceRow(updated)
      // Worded from the RETURNED row, not from what was requested: a 200 that
      // came back with the old value would otherwise be announced as a change.
      setBanner({
        tone: 'ok',
        text: `${updated.name} is now ${updated.active ? 'active' : 'paused'}.`,
      })
    } catch (error) {
      const failure = describeWriteError(error, 'source')
      setBanner({ tone: failure.loud ? 'loud' : 'warn', text: `${failure.title}. ${failure.message}` })
    }
  }

  async function remove(row: Source) {
    setBanner(null)
    try {
      await deleteSource(row.id)
      setRows((current) => current.filter((existing) => existing.id !== row.id))
      setConfirmingId(null)
      setBanner({ tone: 'ok', text: `${row.name} deleted. The sweep will no longer visit it.` })
    } catch (error) {
      const failure = describeWriteError(error, 'source')
      setBanner({ tone: failure.loud ? 'loud' : 'warn', text: `${failure.title}. ${failure.message}` })
    }
  }

  const columns = columnCount(canWrite)

  return (
    <>
      <div className="tm-src__controls">
        <div className="tm-src__control tm-src__control--search">
          <label className="tm-src__controllabel" htmlFor="tm-src-search">
            Search
          </label>
          <input
            id="tm-src-search"
            className="tm-src__input"
            type="search"
            placeholder="Name, URL, or what a source carries"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>

        <div className="tm-src__control">
          <label className="tm-src__controllabel" htmlFor="tm-src-type">
            Type
          </label>
          <select
            id="tm-src-type"
            className="tm-src__select"
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            <option value="all">All types</option>
            {types.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>

        <div className="tm-src__control">
          <label className="tm-src__controllabel" htmlFor="tm-src-category">
            Category
          </label>
          <select
            id="tm-src-category"
            className="tm-src__select"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="all">All categories</option>
            {categories.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>

        <div className="tm-src__control">
          <label className="tm-src__controllabel" htmlFor="tm-src-from">
            From
          </label>
          <select
            id="tm-src-from"
            className="tm-src__select"
            value={from}
            onChange={(event) => setFrom(event.target.value as 'all' | Provenance)}
          >
            <option value="all">Everyone&rsquo;s</option>
            <option value="client_import">Your list</option>
            <option value="seed">Ours</option>
          </select>
        </div>

        <div className="tm-src__control">
          <label className="tm-src__controllabel" htmlFor="tm-src-active">
            State
          </label>
          <select
            id="tm-src-active"
            className="tm-src__select"
            value={activeFilter}
            onChange={(event) => setActiveFilter(event.target.value as ActiveFilter)}
          >
            <option value="all">Active and paused</option>
            <option value="active">Active only</option>
            <option value="paused">Paused only</option>
          </select>
        </div>
      </div>

      <div className="tm-src__bar">
        <span className="tm-src__count">
          {filtered
            ? `${visible.length} of ${rows.length} shown`
            : `${rows.length} ${rows.length === 1 ? 'source' : 'sources'}`}
        </span>
        {/* No add button at all without the codename — not a disabled one. */}
        {canCreate ? (
          <button
            className="tm-src__add"
            type="button"
            onClick={() => {
              setCreating((open) => !open)
              setBanner(null)
            }}
          >
            {creating ? 'Cancel' : 'Add a source'}
          </button>
        ) : null}
      </div>

      {banner ? (
        <div className={`tm-src__banner tm-src__banner--${banner.tone}`} role="status">
          {banner.text}
        </div>
      ) : null}

      {creating ? (
        <SourceCreateForm
          categories={categories}
          onCancel={() => setCreating(false)}
          onCreated={(created) => {
            // Inserted in name order because that is the order the API returns,
            // so a new row lands where a reload would put it.
            setRows((current) =>
              [...current, created].sort((a, b) => a.name.localeCompare(b.name)),
            )
            setCreating(false)
            setBanner({
              tone: 'ok',
              text: `${created.name} added. Its type, category and scope are now fixed — the API has no way to change them.`,
            })
          }}
          onFailed={(failure) =>
            setBanner({
              tone: failure.loud ? 'loud' : 'warn',
              text: `${failure.title}. ${failure.message}`,
            })
          }
        />
      ) : null}

      {rows.length === 0 ? (
        <EmptyState
          title="No sources configured"
          explain="The list loaded and came back empty, which means nothing has been set up to sweep rather than that the request failed. Until a source exists, a sweep has nowhere to go."
        />
      ) : visible.length === 0 ? (
        <EmptyState
          title="Nothing matches those filters"
          explain={`All ${rows.length} sources are still there — the search and filters above just exclude every one of them. Clear the search or set the filters back to “All” to see them again.`}
        />
      ) : (
        <div className="tm-src__scroll">
          <table className="tm-src__table">
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">From</th>
                <th scope="col">Role</th>
                <th scope="col">Type</th>
                <th scope="col">Category</th>
                <th scope="col">Scope</th>
                <th scope="col">Last check</th>
                <th scope="col">State</th>
                {canWrite ? (
                  <th scope="col">
                    <span className="tm-src__srhead">Actions</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <Fragment key={row.id}>
                  <tr className={row.active ? 'tm-src__row' : 'tm-src__row tm-src__row--paused'}>
                    <td>
                      <span className="tm-src__name">{row.name}</span>
                      <a
                        className="tm-src__url"
                        href={row.url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        {row.url}
                      </a>
                    </td>
                    <td>
                      {/*
                        Whose list this came from. She asked to see that her own
                        81 arrived intact, and this is the column that answers
                        it — the 6 that reconciled with a source we already had
                        read as hers, because her list is why we know she wants
                        them watched.
                      */}
                      <span
                        className={
                          row.provenance === 'client_import'
                            ? 'tm-src__prov tm-src__prov--client'
                            : 'tm-src__prov'
                        }
                      >
                        {row.provenance === 'client_import' ? 'Your list' : 'Ours'}
                      </span>
                    </td>
                    <td>
                      <RoleCell role={row.sourceRole} />
                    </td>
                    <td>
                      {/*
                        "unknown" is NOT a blank to tidy away. It means nobody
                        has opened this source to see how it publishes, and the
                        crawler will need to find out. Styled as a question so
                        it cannot be mistaken for a finding — the whole reason
                        the contract chose it over defaulting to "html".
                      */}
                      <span
                        className={
                          row.type === 'unknown'
                            ? 'tm-src__type tm-src__type--unknown'
                            : 'tm-src__type'
                        }
                        title={
                          row.type === 'unknown'
                            ? 'Not examined yet — her spreadsheet does not say how this site publishes'
                            : undefined
                        }
                      >
                        {row.type === 'unknown' ? 'not checked' : row.type}
                      </span>
                    </td>
                    <td>
                      {/* FREE TEXT, and "" on rows created without one. */}
                      {row.category ? (
                        row.category
                      ) : (
                        <span className="tm-src__muted">No category</span>
                      )}
                    </td>
                    <td>
                      {/*
                        RAW STRING. Not translated into business units: the
                        vocabulary predates the five-unit model and no mapping
                        from it onto the five units exists.
                      */}
                      <span className="tm-src__scope">{row.scope}</span>
                    </td>
                    <td>
                      <LastCheck source={row} />
                    </td>
                    <td>
                      <span
                        className={
                          row.active ? 'tm-src__state tm-src__state--on' : 'tm-src__state'
                        }
                      >
                        {row.active ? 'Active' : 'Paused'}
                      </span>
                    </td>
                    {canWrite ? (
                      <td className="tm-src__actions">
                        {canUpdate ? (
                          <>
                            <button
                              className="tm-src__action"
                              type="button"
                              onClick={() => toggleActive(row)}
                            >
                              {row.active ? 'Pause' : 'Resume'}
                            </button>
                            <button
                              className="tm-src__action"
                              type="button"
                              onClick={() => {
                                setBanner(null)
                                setConfirmingId(null)
                                setEditingId(editingId === row.id ? null : row.id)
                              }}
                            >
                              Edit
                            </button>
                          </>
                        ) : null}
                        {canDelete ? (
                          <button
                            className="tm-src__action tm-src__action--danger"
                            type="button"
                            onClick={() => {
                              setBanner(null)
                              setEditingId(null)
                              setConfirmingId(confirmingId === row.id ? null : row.id)
                            }}
                          >
                            Delete
                          </button>
                        ) : null}
                      </td>
                    ) : null}
                  </tr>

                  {editingId === row.id ? (
                    <tr className="tm-src__drawerrow">
                      <td colSpan={columns}>
                        <SourceEditForm
                          source={row}
                          onCancel={() => setEditingId(null)}
                          onSaved={(updated, changedLabels) => {
                            replaceRow(updated)
                            setEditingId(null)
                            setBanner({
                              tone: 'ok',
                              text: `${updated.name}: ${changedLabels.join(' and ')} updated, confirmed against the row the server sent back.`,
                            })
                          }}
                          onUnchanged={() => {
                            setEditingId(null)
                            setBanner({
                              tone: 'warn',
                              text: 'Nothing was different, so nothing was sent.',
                            })
                          }}
                          onFailed={(failure) =>
                            setBanner({
                              tone: failure.loud ? 'loud' : 'warn',
                              text: `${failure.title}. ${failure.message}`,
                            })
                          }
                        />
                      </td>
                    </tr>
                  ) : null}

                  {confirmingId === row.id ? (
                    <tr className="tm-src__drawerrow">
                      <td colSpan={columns}>
                        <div className="tm-src__confirm">
                          <p className="tm-src__confirmtext">
                            Delete <strong>{row.name}</strong>? It is removed for everyone and there
                            is no undo — re-adding it means typing the URL, type, category and scope
                            again.
                          </p>
                          <div className="tm-src__confirmactions">
                            <button
                              className="tm-src__danger"
                              type="button"
                              onClick={() => remove(row)}
                            >
                              Delete it
                            </button>
                            <button
                              className="tm-src__cancel"
                              type="button"
                              onClick={() => setConfirmingId(null)}
                            >
                              Keep it
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="tm-src__legend">
        <strong>Scope</strong> is shown exactly as stored. Its takeout / foundation / both vocabulary
        predates the five-unit model and cannot express Design Teem, Ingene Studios or TM Labs at
        all, so it is deliberately not translated into business units — no such mapping exists.
      </p>
    </>
  )
}

/**
 * Discovery platform, publisher, or nobody has decided yet.
 *
 * Every one of the 90 rows reads "unconfirmed" today, and that is correct
 * rather than unfinished: her spreadsheet has no aggregator column, so
 * classifying at import would have been us inventing data on her behalf and
 * presenting it as hers.
 *
 * CRITERION 21 IS THE POINT OF THIS COMPONENT. An unconfirmed value must look
 * like a QUESTION, not a quiet default. If it rendered as plain grey text
 * beside the confirmed ones, nobody would ever go and confirm it — and the
 * entire argument for a three-state enum over a nullable boolean was that a
 * value nobody has decided must stay visible until somebody does.
 */
function RoleCell({ role }: { role: SourceRole }) {
  if (role === 'unconfirmed') {
    return (
      <span
        className="tm-src__role tm-src__role--unconfirmed"
        title="Nobody has classified this source yet. It is not a finding — it is an open question."
      >
        needs a look
      </span>
    )
  }

  return (
    <span className={`tm-src__role tm-src__role--${role}`}>
      {role === 'aggregator' ? 'Lists others' : 'Publishes own'}
    </span>
  )
}

/**
 * When this source was last visited.
 *
 * `lastCheckedAt` is null on EVERY row — including the rows that do carry a
 * status, because the sweep records the outcome without recording the time. So
 * "time not recorded" is the ordinary case here, not an edge case, and a row
 * with no status at all has genuinely never been checked. Neither is rendered
 * as a blank or a dash: a real null must not look like a failed load.
 */
function LastCheck({ source }: { source: Source }) {
  const when = formatStamp(source.lastCheckedAt)

  if (source.lastStatus === null) {
    return (
      <span className="tm-src__never" title="No sweep has ever recorded a result for this source.">
        Never checked
      </span>
    )
  }

  return (
    <span
      className={
        source.lastStatusOk === false
          ? 'tm-src__status tm-src__status--bad'
          : 'tm-src__status tm-src__status--ok'
      }
      /* The status text is the server's own words, so the tooltip carries the
         reading of it rather than a paraphrase that could drift. */
      title={
        source.lastStatusOk === false
          ? 'The last sweep recorded a failure for this source.'
          : 'The last sweep reached this source.'
      }
    >
      {source.lastStatus}
      <span className="tm-src__when">
        {when ?? 'time not recorded'}
      </span>
    </span>
  )
}

/* ------------------------------------------------------------- create --- */

function SourceCreateForm({
  categories,
  onCancel,
  onCreated,
  onFailed,
}: {
  categories: string[]
  onCancel: () => void
  onCreated: (created: Source) => void
  onFailed: (failure: WriteFailure) => void
}) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('')
  const [type, setType] = useState<string>('html')
  const [category, setCategory] = useState('')
  const [scope, setScope] = useState<string>('both')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()

    // Both are required server-side and a miss returns 422, whose body is an
    // array of validation objects rather than a sentence — so it is caught here.
    if (!name.trim() || !url.trim()) {
      setError('A source needs both a name and a URL.')
      return
    }
    setError(null)

    const input: SourceCreate = {
      name: name.trim(),
      url: url.trim(),
      type,
      category: category.trim(),
      scope,
    }

    setSaving(true)
    try {
      onCreated(await createSource(input))
    } catch (failure) {
      onFailed(describeWriteError(failure, 'source'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <form className="tm-src__form" onSubmit={submit}>
      <div className="tm-src__formgrid">
        <div className="tm-src__field">
          <label className="tm-src__controllabel" htmlFor="tm-src-new-name">
            Name
          </label>
          <input
            id="tm-src-new-name"
            className="tm-src__input"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
        </div>

        <div className="tm-src__field">
          <label className="tm-src__controllabel" htmlFor="tm-src-new-url">
            URL
          </label>
          <input
            id="tm-src-new-url"
            className="tm-src__input"
            type="url"
            placeholder="https://"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            required
          />
        </div>

        {/*
          These three are offered HERE AND ONLY HERE. PATCH accepts none of
          them, so once this row exists they can never be changed — which is
          why the edit form does not show them and why this says so out loud.
        */}
        <div className="tm-src__field">
          <label className="tm-src__controllabel" htmlFor="tm-src-new-type">
            Type
          </label>
          <select
            id="tm-src-new-type"
            className="tm-src__select"
            value={type}
            onChange={(event) => setType(event.target.value)}
          >
            {SOURCE_TYPES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>

        <div className="tm-src__field">
          <label className="tm-src__controllabel" htmlFor="tm-src-new-category">
            Category
          </label>
          {/*
            Free text with the existing values offered as suggestions rather
            than as a closed list — it is not an enum, and forcing one would
            block a legitimate new category the day #4's import needs it.
          */}
          <input
            id="tm-src-new-category"
            className="tm-src__input"
            list="tm-src-categories"
            placeholder="e.g. procurement"
            value={category}
            onChange={(event) => setCategory(event.target.value)}
          />
          <datalist id="tm-src-categories">
            {categories.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        </div>

        <div className="tm-src__field">
          <label className="tm-src__controllabel" htmlFor="tm-src-new-scope">
            Scope
          </label>
          <select
            id="tm-src-new-scope"
            className="tm-src__select"
            value={scope}
            onChange={(event) => setScope(event.target.value)}
          >
            {SOURCE_SCOPES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      </div>

      <p className="tm-src__formnote">
        <strong>Type, category and scope can only be set now.</strong> The update endpoint accepts
        name, URL and active state only, so after this source is created those three are fixed for
        good — correcting one means deleting the source and adding it again. Scope&rsquo;s three options are the old vocabulary and cannot name Design Teem, Ingene
        Studios or TM Labs — pick <em>both</em> if none of them fits.
      </p>

      {error ? <p className="tm-src__formerror">{error}</p> : null}

      <div className="tm-src__formactions">
        <button className="tm-src__save" type="submit" disabled={saving}>
          {saving ? 'Adding…' : 'Add source'}
        </button>
        <button className="tm-src__cancel" type="button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  )
}

/* --------------------------------------------------------------- edit --- */

/**
 * Name and URL. Nothing else.
 *
 * PATCH accepts name, url and active. Offering type, category or scope here
 * would produce a control that appears to save and does not: the server takes
 * the request, returns 200, and keeps the old value. That is the precise
 * failure this project has removed twice, so the missing fields are named in
 * the form rather than quietly absent.
 *
 * `active` is the third key PATCH accepts and is still deliberately absent
 * here, because the row already carries a live Pause/Resume button — see the
 * note further down.
 */
function SourceEditForm({
  source,
  onCancel,
  onSaved,
  onUnchanged,
  onFailed,
}: {
  source: Source
  onCancel: () => void
  onSaved: (updated: Source, changed: string[]) => void
  onUnchanged: () => void
  onFailed: (failure: WriteFailure) => void
}) {
  const [name, setName] = useState(source.name)
  const [url, setUrl] = useState(source.url)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()

    if (!name.trim() || !url.trim()) {
      setError('A source needs both a name and a URL.')
      return
    }
    setError(null)

    // Only what changed. A PATCH with an empty body would return 200 having
    // done nothing, which is indistinguishable from a successful save.
    // `active` is deliberately NOT in this diff — see the note in the form.
    const changes: { name?: string; url?: string } = {}
    if (name.trim() !== source.name) changes.name = name.trim()
    if (url.trim() !== source.url) changes.url = url.trim()

    const keys = Object.keys(changes)
    if (keys.length === 0) {
      onUnchanged()
      return
    }

    setSaving(true)
    try {
      const updated = await patchSource(source.id, changes)

      /*
        Confirmed against the RETURNED ROW, not the status code. If the server
        answers 200 without the new values, that is reported as a failure to
        apply rather than announced as a save.
      */
      const landed = keys.filter(
        (key) => updated[key as keyof typeof changes] === changes[key as keyof typeof changes],
      )
      if (landed.length !== keys.length) {
        onFailed({
          title: 'The server accepted the change but did not apply it',
          message:
            'The row it sent back still holds the old values, so nothing here has changed. Worth reporting.',
          loud: true,
        })
        return
      }

      onSaved(
        updated,
        landed.map((key) => PATCH_LABEL[key as keyof typeof PATCH_LABEL]),
      )
    } catch (failure) {
      onFailed(describeWriteError(failure, 'source'))
    } finally {
      setSaving(false)
    }
  }

  const id = (field: string) => `tm-src-${source.id}-${field}`

  return (
    <form className="tm-src__form" onSubmit={submit}>
      <div className="tm-src__formgrid">
        <div className="tm-src__field">
          <label className="tm-src__controllabel" htmlFor={id('name')}>
            Name
          </label>
          <input
            id={id('name')}
            className="tm-src__input"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="tm-src__field">
          <label className="tm-src__controllabel" htmlFor={id('url')}>
            URL
          </label>
          <input
            id={id('url')}
            className="tm-src__input"
            type="url"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
          />
        </div>

      </div>

      {/*
        NO state toggle here, deliberately. The row's own Pause/Resume button is
        the one control for this value and it stays live behind the open drawer.
        A second checkbox seeded once from the row was a snapshot of a value
        that could move underneath it: pause the row with the drawer open, then
        rename and save, and the diff compared a stale `true` against the
        server's `false` and silently un-paused the source while reporting only
        a name change. Two controls for one value is the same trap as two
        systems doing one job — the fix is to have one, not to sync them.
      */}
      <p className="tm-src__formnote">
        State is <strong>{source.active ? 'active' : 'paused'}</strong> and is changed with the{' '}
        {source.active ? 'Pause' : 'Resume'} button on the row, not here.
      </p>

      <p className="tm-src__formnote">
        Type (<strong>{source.type}</strong>), category (
        <strong>{source.category || 'none'}</strong>) and scope (<strong>{source.scope}</strong>) are
        fixed at creation and cannot be edited — the update endpoint does not accept them. Changing
        any of the three means deleting this source and adding it again.
      </p>

      {error ? <p className="tm-src__formerror">{error}</p> : null}

      <div className="tm-src__formactions">
        <button className="tm-src__save" type="submit" disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </button>
        <button className="tm-src__cancel" type="button" onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </form>
  )
}
