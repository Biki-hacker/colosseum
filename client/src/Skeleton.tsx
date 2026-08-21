export function HistorySkeleton() {
  return (
    <div className="history-stage skeleton-stage" aria-busy="true" aria-label="Loading verdict archive">
      {/* Skeleton Analytics */}
      <div className="analytics-card skeleton-card-clay">
        <div className="analytics-header">
          <div className="skeleton-line skeleton-w-40 skeleton-h-16" />
          <div className="skeleton-line skeleton-w-20 skeleton-h-12" />
        </div>

        <div className="win-distribution">
          <div className="win-labels">
            <div className="skeleton-line skeleton-w-20 skeleton-h-12" />
            <div className="skeleton-line skeleton-w-20 skeleton-h-12" />
          </div>
          <div className="skeleton-win-bar">
            <div className="skeleton-fill" />
          </div>
        </div>

        <div className="stats-row">
          <div className="stat-box skeleton-stat">
            <div className="skeleton-line skeleton-w-30 skeleton-h-20" />
            <div className="skeleton-line skeleton-w-60 skeleton-h-10" />
          </div>
          <div className="stat-box skeleton-stat">
            <div className="skeleton-line skeleton-w-30 skeleton-h-20" />
            <div className="skeleton-line skeleton-w-60 skeleton-h-10" />
          </div>
          <div className="stat-box skeleton-stat">
            <div className="skeleton-line skeleton-w-30 skeleton-h-20" />
            <div className="skeleton-line skeleton-w-60 skeleton-h-10" />
          </div>
        </div>
      </div>

      {/* Skeleton Filter Bar */}
      <div className="filter-bar skeleton-filter-bar">
        <div className="skeleton-line skeleton-search-input" />
        <div className="filter-group">
          <div className="skeleton-pill skeleton-btn" />
          <div className="skeleton-pill skeleton-btn" />
          <div className="skeleton-pill skeleton-btn" />
        </div>
      </div>

      {/* Skeleton Debate Cards */}
      <div className="debate-list">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="debate-card skeleton-debate-card">
            <div className="card-header">
              <div className="skeleton-line skeleton-w-25 skeleton-h-12" />
              <div className="skeleton-pill skeleton-w-15 skeleton-h-14" />
            </div>
            <div className="skeleton-line skeleton-w-85 skeleton-h-18" />
            <div className="skeleton-line skeleton-w-65 skeleton-h-14" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function ModalTranscriptSkeleton() {
  return (
    <div className="modal-skeleton-body" aria-busy="true" aria-label="Loading debate details">
      <div className="speech-list">
        {/* Left bubble (Optimist) */}
        <div className="speech-row opt-row">
          <div className="speech-bubble skeleton-bubble skeleton-opt-bubble">
            <div className="speech-meta">
              <div className="skeleton-line skeleton-w-25 skeleton-h-10" />
              <div className="skeleton-line skeleton-w-20 skeleton-h-10" />
            </div>
            <div className="skeleton-line skeleton-w-90 skeleton-h-14" />
            <div className="skeleton-line skeleton-w-75 skeleton-h-14" />
          </div>
        </div>

        {/* Right bubble (Pessimist) */}
        <div className="speech-row pes-row">
          <div className="speech-bubble skeleton-bubble skeleton-pes-bubble">
            <div className="speech-meta">
              <div className="skeleton-line skeleton-w-25 skeleton-h-10" />
              <div className="skeleton-line skeleton-w-20 skeleton-h-10" />
            </div>
            <div className="skeleton-line skeleton-w-85 skeleton-h-14" />
            <div className="skeleton-line skeleton-w-60 skeleton-h-14" />
          </div>
        </div>

        {/* Left bubble (Optimist) */}
        <div className="speech-row opt-row">
          <div className="speech-bubble skeleton-bubble skeleton-opt-bubble">
            <div className="speech-meta">
              <div className="skeleton-line skeleton-w-25 skeleton-h-10" />
              <div className="skeleton-line skeleton-w-20 skeleton-h-10" />
            </div>
            <div className="skeleton-line skeleton-w-95 skeleton-h-14" />
            <div className="skeleton-line skeleton-w-70 skeleton-h-14" />
          </div>
        </div>
      </div>
    </div>
  );
}

export function ArenaSkeleton() {
  return (
    <div className="arena-stage skeleton-stage" aria-busy="true" aria-label="Connecting to live arena">
      {/* 1. Combatant Cards Skeleton */}
      <div className="combatants-roster">
        {/* Left: The Optimist */}
        <div className="combatant-card opt-card skeleton-combatant">
          <div className="combatant-info">
            <div className="skeleton-line skeleton-w-30 skeleton-h-10" />
            <div className="skeleton-line skeleton-w-70 skeleton-h-20" />
            <div className="skeleton-pill skeleton-w-25 skeleton-h-12" />
          </div>
        </div>

        {/* Center: VS Marker */}
        <div className="vs-marker">
          <span>VS</span>
        </div>

        {/* Right: The Pessimist */}
        <div className="combatant-card pes-card skeleton-combatant">
          <div
            className="combatant-info text-right"
            style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}
          >
            <div className="skeleton-line skeleton-w-30 skeleton-h-10" />
            <div className="skeleton-line skeleton-w-70 skeleton-h-20" />
            <div className="skeleton-pill skeleton-w-25 skeleton-h-12" />
          </div>
        </div>
      </div>

      {/* 2. Sanctum / Podium Skeleton */}
      <div className="sanctum-card skeleton-card-clay" style={{ textAlign: "center" }}>
        <div className="skeleton-line skeleton-w-35 skeleton-h-18" style={{ margin: "0 auto 10px" }} />
        <div className="skeleton-line skeleton-w-60 skeleton-h-12" style={{ margin: "0 auto 18px" }} />
        <div className="skeleton-pill skeleton-w-30 skeleton-h-36" style={{ margin: "0 auto" }} />
      </div>

      {/* 3. Transcript Bubbles Skeleton */}
      <div className="speech-list" style={{ marginTop: "8px" }}>
        <div className="speech-row opt-row">
          <div className="speech-bubble skeleton-bubble skeleton-opt-bubble">
            <div className="speech-meta">
              <div className="skeleton-line skeleton-w-25 skeleton-h-10" />
              <div className="skeleton-line skeleton-w-20 skeleton-h-10" />
            </div>
            <div className="skeleton-line skeleton-w-90 skeleton-h-14" />
            <div className="skeleton-line skeleton-w-75 skeleton-h-14" />
          </div>
        </div>

        <div className="speech-row pes-row">
          <div className="speech-bubble skeleton-bubble skeleton-pes-bubble">
            <div className="speech-meta">
              <div className="skeleton-line skeleton-w-25 skeleton-h-10" />
              <div className="skeleton-line skeleton-w-20 skeleton-h-10" />
            </div>
            <div className="skeleton-line skeleton-w-85 skeleton-h-14" />
            <div className="skeleton-line skeleton-w-60 skeleton-h-14" />
          </div>
        </div>
      </div>
    </div>
  );
}
