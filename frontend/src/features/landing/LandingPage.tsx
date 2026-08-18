import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  briefingPoints,
  briefingRows,
  faqs,
  layers,
  navLinks,
  orgChips,
  radarStats,
  steps,
  units,
  weekOf,
} from './data'
import './landing.css'

export function LandingPage() {
  return (
    <div className="tm-landing">
      <Nav />
      <Hero />
      <Units />
      <ClientStrip />
      <Layers />
      <HowItWorks />
      <BriefingShowcase />
      <Quote />
      <Faq />
      <SubscribeCta />
      <Footer />
    </div>
  )
}

function Nav() {
  return (
    <header className="tm-nav">
      <div className="tm-nav__brand">
        <div className="tm-nav__mark">TM</div>
        <div className="tm-nav__wordmark">TM Global BI</div>
      </div>
      <nav className="tm-nav__links">
        {navLinks.map((link) => (
          <a key={link.href} className="tm-nav__link" href={link.href}>
            {link.label}
          </a>
        ))}
      </nav>
      <div className="tm-nav__actions">
        {/*
          Router Link, not an <a href>: a full page reload here would throw away
          the auth context and make the sign-in feel slower than it is.
        */}
        <Link className="tm-nav__login" to="/login">
          Log in
        </Link>
        <a className="tm-btn-gradient tm-nav__cta" href="#cta">
          Open dashboard
        </a>
      </div>
    </header>
  )
}

function Hero() {
  return (
    <section className="tm-hero">
      <div className="tm-hero__glow" aria-hidden="true" />
      <div className="tm-hero__inner">
        <div className="tm-badge">
          <span className="tm-badge__dot" aria-hidden="true" />
          Internal business development system · TM Global
        </div>
        <h1 className="tm-hero__title">
          Where is our <span className="tm-gradient-text">next revenue</span>{' '}
          coming from?
        </h1>
        <p className="tm-hero__sub">
          One AI business development system across all five TM Global business
          units: weekly insight on every industry in Nigeria, a live opportunity
          tracker, intelligence on the clients we already serve and where to
          upsell them — delivered to each unit's inbox every Monday.
        </p>
        <div className="tm-hero__ctas">
          <a className="tm-btn-gradient tm-hero__cta" href="#cta">
            Open this week's radar
          </a>
          <a className="tm-btn-outline" href="#how">
            How the system works →
          </a>
        </div>
      </div>
      <RadarPreview />
    </section>
  )
}

function RadarPreview() {
  return (
    <div className="tm-radar" id="radar">
      <div className="tm-radar__header">
        <div className="tm-radar__kicker">{weekOf}</div>
        <div className="tm-radar__title">Our Business Development Radar</div>
      </div>
      <div className="tm-radar__grid">
        {radarStats.map((stat) => (
          <div className="tm-radar__cell" key={stat.label}>
            <div
              className={
                stat.accent
                  ? 'tm-radar__value tm-radar__value--accent'
                  : 'tm-radar__value'
              }
            >
              {stat.value}
            </div>
            <div className="tm-radar__label">{stat.label}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Units() {
  return (
    <section className="tm-section tm-section--units" id="units">
      <div className="tm-section__inner">
        <div className="tm-units__head">
          <div className="tm-kicker">Five units, one radar</div>
          <h2 className="tm-units__title">
            Every business unit gets its own profile — and its own opportunities
          </h2>
          <p className="tm-units__lede">
            Each unit sets what it does and who it wants to work with. The AI
            scores every finding against all five, and flags the ones worth
            pitching together.
          </p>
        </div>
        <div className="tm-units__grid">
          {units.map((unit) => (
            <article className="tm-unit" key={unit.name}>
              <div className="tm-unit__head">
                <div className="tm-unit__initials">{unit.initials}</div>
                <div className="tm-unit__name">{unit.name}</div>
              </div>
              <div className="tm-unit__desc">{unit.desc}</div>
              <ul className="tm-unit__services">
                {unit.services.map((service) => (
                  <li className="tm-unit__service" key={service}>
                    {service}
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function ClientStrip() {
  return (
    <section className="tm-section--chips">
      <div className="tm-chips">
        <div className="tm-chips__label">
          Client accounts we track for upsell signals
        </div>
        <ul className="tm-chips__row">
          {orgChips.map((org) => (
            <li className="tm-chip" key={org}>
              {org}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

function Layers() {
  return (
    <section className="tm-section--layers" id="layers">
      <div className="tm-section__inner">
        <div className="tm-centered-head">
          <div className="tm-kicker">The system</div>
          <h2 className="tm-h2">
            Eight layers of intelligence, one weekly briefing
          </h2>
          <p className="tm-centered-head__lede">
            Not a database of leads. A system that continuously explains what's
            changing around TM Global — and what the team should do about it.
          </p>
        </div>
        <div className="tm-layers__grid">
          {layers.map((layer) => (
            <article className="tm-layer" key={layer.title}>
              <div className="tm-layer__icon" aria-hidden="true">
                {layer.glyph}
              </div>
              <div className="tm-layer__title">{layer.title}</div>
              <div className="tm-layer__desc">{layer.desc}</div>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function HowItWorks() {
  return (
    <section className="tm-section" id="how">
      <div className="tm-section__inner">
        <div className="tm-how__head">
          <div className="tm-kicker">How it works</div>
          <h2 className="tm-h2">From 101 sources to one Monday briefing</h2>
        </div>
        <div className="tm-how__grid">
          <div className="tm-how__line" aria-hidden="true" />
          {steps.map((step) => (
            <div className="tm-step" key={step.num}>
              <div className="tm-step__num">{step.num}</div>
              <div className="tm-step__title">{step.title}</div>
              <div className="tm-step__desc">{step.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function BriefingShowcase() {
  return (
    <section className="tm-section--showcase">
      <div className="tm-showcase">
        <div>
          <div className="tm-kicker">Weekly email update</div>
          <h2 className="tm-showcase__title">
            The 10 things TM Global needs to know — in your inbox every Monday
          </h2>
          <p className="tm-showcase__lede">
            Opportunities, client movements, industry shifts and competitor
            plays — synthesised into one ranked list with a recommended action
            for each, and emailed to the team so leadership never has to dig for
            it.
          </p>
          <ul className="tm-checklist">
            {briefingPoints.map((point) => (
              <li className="tm-checklist__item" key={point}>
                <span className="tm-checklist__tick" aria-hidden="true">
                  ✓
                </span>
                <span>{point}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="tm-mail">
          <div className="tm-mail__header">
            <div className="tm-mail__kicker">TM Global · All business units</div>
            <div className="tm-mail__title">
              Weekly Business Intelligence Briefing
            </div>
          </div>
          <div className="tm-mail__body">
            {briefingRows.map((row) => (
              <div className="tm-mail__row" key={row.num}>
                <div className="tm-mail__num">{row.num}</div>
                <div className="tm-mail__text">
                  <strong>{row.title}</strong> — {row.text}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}

function Quote() {
  return (
    <section className="tm-quote">
      <div className="tm-quote__inner">
        <div className="tm-quote__mark" aria-hidden="true">
          "
        </div>
        <p className="tm-quote__text">
          Built so the team knows who to call on Monday — not just what's out
          there. We stopped guessing our pipeline.
        </p>
        <div className="tm-quote__attr">Business Development, TM Global</div>
      </div>
    </section>
  )
}

function Faq() {
  return (
    <section className="tm-section--faq" id="faq">
      <div className="tm-faq__inner">
        <div className="tm-faq__head">
          <div className="tm-kicker">FAQ</div>
          <h2 className="tm-h2">How the system runs</h2>
        </div>
        <div className="tm-faq__grid">
          {faqs.map((faq) => (
            <div key={faq.q}>
              <div className="tm-faq__q">{faq.q}</div>
              <div className="tm-faq__a">{faq.a}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

function SubscribeCta() {
  const [email, setEmail] = useState('')
  const [note, setNote] = useState('')

  // The real subscribe endpoint is backend work and isn't agreed yet, so this
  // acknowledges locally rather than pretending to have persisted anything.
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!email) return
    setNote(`Not connected yet — ${email} will be saved once the backend is live.`)
  }

  return (
    <section className="tm-cta" id="cta">
      <div className="tm-cta__glow-a" aria-hidden="true" />
      <div className="tm-cta__glow-b" aria-hidden="true" />
      <div className="tm-cta__inner">
        <h2 className="tm-cta__title">This week's radar is ready</h2>
        <p className="tm-cta__lede">
          Open the dashboard, or add your work email to receive the Monday
          briefing directly.
        </p>
        <form className="tm-cta__form" onSubmit={handleSubmit}>
          <label className="tm-visually-hidden" htmlFor="tm-subscribe-email">
            Work email
          </label>
          <input
            className="tm-cta__input"
            id="tm-subscribe-email"
            type="email"
            placeholder="you@takeoutmedia.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <button className="tm-btn-gradient tm-cta__submit" type="submit">
            Subscribe to Monday briefing
          </button>
        </form>
        <p className="tm-cta__note" role="status">
          {note}
        </p>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="tm-footer">
      <div className="tm-footer__brand">
        <div className="tm-footer__mark">TM</div>
        <div className="tm-footer__name">TM Global Business Intelligence</div>
      </div>
      <div className="tm-footer__meta">
        Internal system · Takeout Media · Design Teem · Ingene Studios · TM Labs
        · TM Foundation · © 2026
      </div>
    </footer>
  )
}
