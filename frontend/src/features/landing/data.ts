/**
 * Landing page content, transcribed from the design prototype.
 *
 * This is presentation copy, not product data — the radar figures below are the
 * designed placeholders. Once the backend is live the radar strip should read
 * from the API instead; everything else here is static marketing copy.
 */

export interface RadarStat {
  value: string
  label: string
  accent: boolean
}

export const radarStats: RadarStat[] = [
  { value: '6', label: 'Opportunities to pursue', accent: true },
  { value: '8', label: 'Organisations to approach', accent: false },
  { value: '10', label: 'Emerging trends', accent: false },
  { value: '3', label: 'Competitor movements', accent: false },
  { value: '4', label: 'Potential partnerships', accent: true },
  { value: '₦740M', label: 'Estimated pipeline', accent: true },
]

export interface Unit {
  initials: string
  name: string
  desc: string
  services: string[]
}

export const units: Unit[] = [
  {
    initials: 'TM',
    name: 'Takeout Media',
    desc: 'Communications, brand strategy and campaigns across development and financial sectors.',
    services: [
      'Brand strategy',
      'Development communications',
      'Digital marketing',
      'Brand consultancy',
      'Events and activations',
      'Public relations',
    ],
  },
  {
    initials: 'DT',
    name: 'Design Teem',
    desc: 'Design, identity and creative production for brands, institutions and programmes.',
    services: ['Brand design', 'Motion and animation'],
  },
  {
    initials: 'IS',
    name: 'Ingene Studios',
    desc: 'Film, documentary and content production for broadcast, donors and brands.',
    services: ['Production'],
  },
  {
    initials: 'TL',
    name: 'TM Labs',
    desc: 'Technology, product and creative-tech builds for clients and internal ventures.',
    services: ['Tech contracts', 'Partnerships'],
  },
  {
    initials: 'TF',
    name: 'TM Foundation',
    desc: 'Creative economy intelligence, research and ecosystem development.',
    services: ['Grants', 'Fellowships'],
  },
]

export const orgChips: string[] = [
  'UNDP',
  'World Bank',
  'GIZ',
  'Jaiz Bank',
  'TAJBank',
  'NNPC',
  'ITF',
  'NCAC',
]

export interface Layer {
  glyph: string
  title: string
  desc: string
}

export const layers: Layer[] = [
  {
    glyph: '◎',
    title: 'Opportunity Tracker',
    desc: 'Grants, RFPs, tenders and fellowships ranked by fit, value and probability of winning — plus who to co-pitch them with.',
  },
  {
    glyph: '▤',
    title: 'Nigerian Industry Insight',
    desc: 'Weekly trend, regulation and funding signals across every industrial sector in Nigeria — not just the ones we work in today.',
  },
  {
    glyph: '◈',
    title: 'Existing Client Intelligence',
    desc: 'Tracks UNDP, World Bank, Jaiz, TAJBank, SON, ITF, NNPC, GIZ and more — what they are launching and where we can upsell.',
  },
  {
    glyph: '✉',
    title: 'Weekly Email Update',
    desc: 'The full briefing lands in the team’s inbox every Monday morning — no one has to log in to stay current.',
  },
  {
    glyph: '◐',
    title: 'Opportunity Radar',
    desc: 'One internal dashboard: pipeline value, live counts and priority actions the moment the team logs in.',
  },
  {
    glyph: '↻',
    title: 'Learning Loop',
    desc: 'Every Pursue, Watch, Partner or Reject decision sharpens how the next opportunity is scored.',
  },
  {
    glyph: '▣',
    title: 'Unit Profiles & Sources',
    desc: 'A profile per business unit — Takeout Media, Design Teem, Ingene Studios, TM Labs, TM Foundation — plus the 101 sources swept each week.',
  },
  {
    glyph: '⌁',
    title: 'Business Development Copilot',
    desc: 'Instant briefs, bid/no-bid calls, proposal outlines and capability statements per opportunity.',
  },
]

export interface Step {
  num: string
  title: string
  desc: string
}

export const steps: Step[] = [
  {
    num: '01',
    title: 'Each unit profiles itself',
    desc: 'Positioning, capabilities and no-go filters for all five TM Global units.',
  },
  {
    num: '02',
    title: 'The scanner sweeps',
    desc: 'Donor portals, tenders, client newsrooms, industry feeds — 101 sources weekly.',
  },
  {
    num: '03',
    title: 'AI scores per unit',
    desc: 'Every finding matched against all five profiles for fit, value and probability.',
  },
  {
    num: '04',
    title: 'Monday email lands',
    desc: 'Each unit acts — Pursue, Watch, Partner or Reject — and the system learns.',
  },
]

export const briefingPoints: string[] = [
  'Ranked opportunities with a recommended next action, not just a list',
  'Existing-client movements worth an upsell conversation this week',
  'Industry shifts across Nigerian sectors we’d otherwise miss',
]

export interface BriefingRow {
  num: string
  title: string
  text: string
}

export const briefingRows: BriefingRow[] = [
  {
    num: '01',
    title: 'Great African Museum Initiative',
    text: 'Draft a concept note before the tender opens.',
  },
  {
    num: '02',
    title: 'UNDP Nigeria',
    text: 'Scaling livelihoods programming — position for 2027 tender.',
  },
  {
    num: '03',
    title: 'Creative Economy sector',
    text: 'Streaming platforms raising local content budgets.',
  },
  {
    num: '04',
    title: 'Competitor movement',
    text: 'Rival agency won a regional comms framework.',
  },
]

export interface Faq {
  q: string
  a: string
}

export const faqs: Faq[] = [
  {
    q: 'How often does the scan run?',
    a: 'Weekly, ahead of the Monday briefing. The team can also trigger an on-demand scan from the Radar at any time.',
  },
  {
    q: 'Which sources are swept?',
    a: '101 registered sources — donor portals, procurement notices, foundation feeds, client newsrooms and Nigerian industry publications. The list is editable under Profile & Sources.',
  },
  {
    q: 'Who receives the Monday email?',
    a: 'Business development and leadership across all five units — Takeout Media, Design Teem, Ingene Studios, TM Labs and TM Foundation — each seeing findings scored for their own profile.',
  },
  {
    q: 'How do decisions feed the scoring?',
    a: 'Every Pursue, Watch, Partner or Reject is logged against the opportunity. The Learning layer aggregates those calls and adjusts how future findings are ranked.',
  },
  {
    q: 'Does it cover industries we don’t work in yet?',
    a: 'Yes. Industry insight spans all Nigerian sectors, so the team sees adjacent markets worth entering, not just current accounts.',
  },
  {
    q: 'Can units pitch together?',
    a: 'Yes — that is the point of one shared radar. When a finding scores well for more than one unit, the system flags it as a joint pitch with a suggested split of the work.',
  },
  {
    q: 'Is this available outside TM Global?',
    a: 'No. This is an internal system across the five TM Global business units. Any external release would be a separate decision.',
  },
]

export const navLinks = [
  { href: '#units', label: 'SBU' },
  { href: '#layers', label: 'Platform' },
  { href: '#how', label: 'How it works' },
  { href: '#radar', label: 'Radar' },
  { href: '#faq', label: 'FAQ' },
]

export const weekOf = 'Week of 12 August 2026'
