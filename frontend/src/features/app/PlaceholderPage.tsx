/**
 * Stand-in for a screen whose todo is agreed but whose contract isn't built
 * yet. Deliberately dashed and explicit about WHY it is empty — an unlabelled
 * blank screen reads as a bug, and three of the five units will legitimately
 * see empty data on day one.
 */
export function PlaceholderPage({
  kicker,
  title,
  lede,
  waitingOn,
}: {
  kicker: string
  title: string
  lede: string
  waitingOn: string
}) {
  return (
    <main className="tm-page">
      <div className="tm-page__kicker">
        <span className="tm-page__dash" aria-hidden="true" />
        {kicker}
      </div>
      <h1 className="tm-page__title">{title}</h1>
      <p className="tm-page__lede">{lede}</p>

      <div className="tm-placeholder">
        <div className="tm-placeholder__label">Not built yet</div>
        <p className="tm-placeholder__text">{waitingOn}</p>
      </div>
    </main>
  )
}
