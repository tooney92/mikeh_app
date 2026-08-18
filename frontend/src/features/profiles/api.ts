import { ApiError, apiGet, apiSend } from '../../lib/api'
import { PERMISSIONS } from '../auth/permissions'
import type {
  ProfileField,
  ProfileUpdate,
  ScanState,
  Source,
  SourceCreate,
  SourcePatch,
  UnitProfile,
} from './types'
import { PROFILE_FIELDS, SCAN_TERMINAL } from './types'

/**
 * The todo #3 endpoints, plus the small amount of translation that keeps the
 * wire vocabulary out of the screens. Same rule as the todo #2 api module: no
 * component spells a path, a method or a status code.
 *
 * Everything here goes through apiGet/apiSend, which attach the bearer token —
 * every endpoint on the service except GET /api/health requires one.
 */

/**
 * `source:update` was missing from PERMISSIONS while `source:create` and
 * `source:delete` were both there. It has been added, so this re-export exists
 * only to keep the three write codenames legible side by side at the point they
 * are used — it is the same string, not a second definition.
 */
export const SOURCE_UPDATE = PERMISSIONS.sourceUpdate

/* ------------------------------------------------------------ profiles --- */

/**
 * ALWAYS five rows, one per business unit, for every caller. This endpoint is
 * never scoped: a Takeout Media lead and a Foundation member both receive all
 * five. Only `canEdit` differs between callers.
 *
 * That is deliberate — seeing a peer unit's positioning is how a joint pitch
 * gets spotted — so nothing downstream may filter this list by membership.
 */
export function fetchProfiles(): Promise<UnitProfile[]> {
  return apiGet<UnitProfile[]>('/api/profiles')
}

/**
 * PARTIAL update. Pass only the fields that changed; omitted fields are left
 * alone server-side.
 *
 * The path takes the PROFILE id (`profile.id`), NOT `profile.businessUnitId`.
 * The two are equal on all five seeded rows, so a mix-up would work today and
 * silently write to the wrong unit the moment a profile is ever recreated.
 *
 * The response is the FULL updated profile, including minFitPercent and
 * canEdit. Callers must render from that response — see applied() for why a
 * 200 on its own proves nothing.
 */
export function updateProfile(profileId: number, changes: ProfileUpdate): Promise<UnitProfile> {
  return apiSend<UnitProfile>('PUT', `/api/profiles/${profileId}`, changes)
}

/**
 * The fields whose value differs between the form and the profile on record.
 *
 * This exists because an empty body `{}` returns 200 and changes nothing, so
 * "the request succeeded" and "something was written" are different questions.
 * Sending only real changes means an empty diff can be caught before a request
 * is made at all, instead of being mistaken for a successful save.
 */
export function diffProfile(current: UnitProfile, draft: ProfileUpdate): ProfileUpdate {
  const changes: ProfileUpdate = {}

  for (const field of PROFILE_FIELDS) {
    if (field === 'minFitPercent') {
      if (draft.minFitPercent !== undefined && draft.minFitPercent !== current.minFitPercent) {
        changes.minFitPercent = draft.minFitPercent
      }
      continue
    }
    const next = draft[field]
    if (next !== undefined && next !== current[field]) changes[field] = next
  }

  return changes
}

/**
 * Which of the fields we SENT actually came back changed in the response.
 *
 * A 200 is not evidence that a write happened — PUT with `{}` returns 200 and
 * an untouched profile — so the confirmation shown to the user is built from
 * comparing the returned object against what was sent, never from the status
 * code. If this ever returns fewer fields than were sent, the server accepted
 * the request and did not apply it, which is worth saying out loud.
 */
export function applied(sent: ProfileUpdate, returned: UnitProfile): ProfileField[] {
  return (Object.keys(sent) as ProfileField[]).filter((field) => returned[field] === sent[field])
}

/** How each writable field is named to the reader, for save confirmations. */
export const FIELD_LABEL: Record<ProfileField, string> = {
  positioning: 'Positioning',
  priorities: 'Priorities',
  capabilities: 'Capabilities',
  credentials: 'Credentials',
  neverShow: 'Never show',
  minFitPercent: 'Fit bar',
}

/* ------------------------------------------------- newline-string edges --- */

/**
 * A newline-separated API string to the lines it represents.
 *
 * `priorities`, `capabilities`, `credentials` and `neverShow` arrive as ONE
 * string with newlines in it, not as arrays. Blank lines are dropped so a
 * trailing newline — which a textarea produces constantly — does not render an
 * empty bullet.
 */
export function linesOf(value: string): string[] {
  return value
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
}

/**
 * A textarea's value on its way back to the API.
 *
 * The string is sent broadly as typed — the API stores it verbatim — with only
 * CRLF normalised to LF, so a value round-tripped through a browser that
 * inserts carriage returns does not come back differing from what the user
 * saw, and does not register as a change when nothing was edited.
 */
export function normaliseLines(value: string): string {
  return value.replace(/\r\n/g, '\n')
}

/* ------------------------------------------------------------- sources --- */

/**
 * Bare array, 15 rows today, ordered by name. Deliverable #4 imports the
 * client's 81 platforms into this same endpoint, so ~85 rows is the size the
 * list is built for.
 *
 * READ IS GATED ON BEING SIGNED IN, NOT ON `source:read`. The endpoint never
 * checks that codename: member.foundation holds NO source permission at all
 * and receives all 15 rows (verified live). Gating the list on `source:read`
 * would hand a member an empty screen for data the API is willingly serving.
 */
export function fetchSources(): Promise<Source[]> {
  return apiGet<Source[]>('/api/sources')
}

/** Returns 201 — not 200 — with the created row. Requires `source:create`. */
export function createSource(input: SourceCreate): Promise<Source> {
  return apiSend<Source>('POST', '/api/sources', input)
}

/**
 * Requires `source:update`, and accepts ONLY name, url and active. Anything
 * else in the body is dropped without complaint, which is why SourcePatch is
 * typed narrowly and the edit form offers nothing more.
 */
export function patchSource(id: number, changes: SourcePatch): Promise<Source> {
  return apiSend<Source>('PATCH', `/api/sources/${id}`, changes)
}

/** 204 with no body — apiSend resolves to undefined. Requires `source:delete`. */
export function deleteSource(id: number): Promise<void> {
  return apiSend<void>('DELETE', `/api/sources/${id}`)
}

/* ---------------------------------------------------------------- scan --- */

/**
 * Fire and forget: 202 Accepted, with the freshly started ScanState as the
 * body, so the panel can show "running" without an extra round trip.
 *
 * Requires `scan:run`, which EVERY seeded role holds, member included — no
 * role gets a 403 here today.
 *
 * Each call writes a ScanRun row, so this is never triggered automatically or
 * on mount. It happens only when somebody presses the button.
 */
export function startScan(): Promise<ScanState> {
  return apiSend<ScanState>('POST', '/api/scan')
}

export function fetchScanStatus(): Promise<ScanState> {
  return apiGet<ScanState>('/api/scan/status')
}

/**
 * Whether a scan is still in flight — i.e. has NOT reached a terminal status.
 *
 * This used to read `!== 'idle' && !== 'complete'`, which made `failed` count
 * as running: the Run button disabled itself forever, and nothing could
 * recover it because polling only happens inside the handler that the disabled
 * button can no longer fire. Terminal statuses are enumerated in one place now
 * so adding another cannot reintroduce that.
 */
export function scanInFlight(state: ScanState): boolean {
  return !SCAN_TERMINAL.includes(state.status)
}

/** A sweep that stopped because it broke, rather than because it finished. */
export function scanFailed(state: ScanState): boolean {
  return state.status === 'failed'
}

/**
 * A backend timestamp, rendered.
 *
 * THE TRAP: these strings are naive UTC with NO trailing Z —
 * "2026-08-17T06:15:12.749340". JavaScript parses a date-time without an
 * offset as LOCAL time, so `new Date(raw)` reads 06:15 as 06:15 WAT when the
 * server meant 07:15 WAT. Verified: a login recorded at 06:10 in the API
 * happened at 07:10 on the wall clock here. So the Z is appended before
 * parsing, and it is appended only when the string does not already carry an
 * offset — in case the backend starts sending one.
 */
export function formatStamp(raw: string | null): string | null {
  if (!raw) return null

  const hasZone = /[Zz]$|[+-]\d{2}:?\d{2}$/.test(raw)
  const parsed = new Date(hasZone ? raw : `${raw}Z`)
  if (Number.isNaN(parsed.getTime())) return null

  return parsed.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/* -------------------------------------------------------- write errors --- */

/** A write failure, in words worth showing. `loud` means it should not be quiet. */
export interface WriteFailure {
  title: string
  message: string
  /**
   * True for failures that should be UNREACHABLE through this UI and therefore
   * indicate something is actually wrong, rather than the user doing something
   * the screen already told them they could not do.
   */
  loud: boolean
}

/**
 * Turns an ApiError into something a person can act on.
 *
 * Two cases are handled specially and both would otherwise be shown as
 * gibberish or as a shrug:
 *
 * 1. 422. FastAPI's validation `detail` is an ARRAY of objects, not a string.
 *    lib/api.ts passes it straight to the Error constructor, which stringifies
 *    it to "[object Object]". So 422 never uses error.message — it gets its own
 *    wording from here.
 *
 * 2. 403 on a profile PUT. With canEdit driving the edit affordance this is
 *    unreachable through the UI, so it is a real fault rather than an expected
 *    outcome, and it is reported loudly. Its two causes are separable by the
 *    detail string and are said differently, because the fixes differ: one
 *    needs a permission granted, the other needs a different person to do it.
 */
/**
 * Failures from POST /api/scan and GET /api/scan/status.
 *
 * Separate from describeWriteError because that one speaks about rows in a
 * table — a sweep failing is not a row failing to save, and borrowing that copy
 * produced "A source needs both a name and a URL" when a sweep 422'd.
 */
export function describeScanError(error: unknown): WriteFailure {
  if (!(error instanceof ApiError)) {
    return {
      title: 'Could not reach the server',
      message: 'The sweep may or may not have started. Reload to see the current status.',
      loud: false,
    }
  }

  if (error.status === 403) {
    return {
      title: 'The server refused to start a sweep',
      message:
        'You do not hold scan:run. Every seeded role holds it today, so reaching this ' +
        'means the permission grid has changed — worth reporting rather than retrying.',
      loud: true,
    }
  }

  return {
    title: 'The sweep did not start',
    message: `The server answered ${error.status}. Nothing was swept, and no sources were changed.`,
    loud: false,
  }
}

export function describeWriteError(error: unknown, what: 'profile' | 'source'): WriteFailure {
  if (!(error instanceof ApiError)) {
    return {
      title: 'Could not reach the server',
      message: 'Nothing was saved. Check the connection and try again.',
      loud: false,
    }
  }

  if (error.status === 422) {
    return {
      title: 'The server rejected those values',
      message:
        what === 'profile'
          ? 'Nothing was saved. The fit bar must be a whole number between 0 and 100 inclusive.'
          : 'Nothing was saved. A source needs both a name and a URL.',
      loud: false,
    }
  }

  if (error.status === 403 && what === 'profile') {
    // The detail strings are the contract's, verbatim and verified live.
    if (error.message.includes('another business unit')) {
      return {
        title: 'The server refused: this profile is not yours to edit',
        message:
          'You hold profile:update, but not for this unit — and the screen should never have offered you the form. ' +
          'Nothing was saved. This is a bug worth reporting: the edit control is meant to follow the server’s own canEdit flag, ' +
          'so reaching this message means the two have come apart.',
        loud: true,
      }
    }
    return {
      title: 'The server refused: you do not hold profile:update',
      message:
        'Your account has no profile-editing permission at all, so this form should not have been offered to you. ' +
        'Nothing was saved. This is a bug worth reporting rather than a permission to request — the edit control follows ' +
        'the server’s own canEdit flag, so reaching this message means the two have come apart.',
      loud: true,
    }
  }

  if (error.status === 403) {
    return {
      title: 'The server refused that change',
      message: `${error.message} Nothing was saved.`,
      loud: true,
    }
  }

  if (error.status === 404) {
    return {
      title: 'That row is gone',
      message: 'The server no longer has it — somebody else may have deleted it. Reload the list.',
      loud: false,
    }
  }

  return {
    title: 'That did not save',
    message: `${error.message} (${error.status})`,
    loud: false,
  }
}
