import type { ModelMetadata } from "@/lib/types";

/**
 * The win model's "how this was calculated" explanation. Plain server
 * component — <details>/<summary> gives native expand/collapse with zero
 * client JS, which is all this needs (nothing here is interactive beyond
 * open/closed).
 */
export function MethodologyPanel({ metadata }: { metadata: ModelMetadata }) {
  const mc = metadata.model_comparison;
  return (
    <details className="card card-interactive group">
      <summary className="text-label cursor-pointer rounded-sm text-xs text-ink transition-colors duration-200 ease-out [&::-webkit-details-marker]:text-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        How This Was Calculated
      </summary>
      <div className="prose-narrow mt-6 space-y-5 text-sm text-ink-muted">
        <p>
          <strong>Validation method.</strong> {metadata.validation_method}
        </p>
        <p>
          <strong>Target.</strong> {metadata.target_definition}
        </p>

        <div>
          <p className="text-label mb-2 text-xs text-ink">Model Selection</p>
          <p>
            We tuned two candidate models — <strong>{mc.candidates.join(" and ")}</strong> — the
            same walk-forward way, then let them compete on {mc.n_walk_forward_folds} rolling,
            never-seen-before seasons:
          </p>
          <table className="mt-3 w-full max-w-sm border-collapse text-left">
            <thead>
              <tr className="border-b border-line/10">
                <th className="text-label py-1.5 pr-4 text-[11px] font-normal text-ink-muted">
                  Candidate
                </th>
                <th className="text-label py-1.5 text-[11px] font-normal text-ink-muted">
                  Walk-forward MAE
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-line/5">
                <td className="py-1.5 pr-4">KNN</td>
                <td className="text-label py-1.5 text-xs">{mc.knn_walk_forward_mae} wins</td>
              </tr>
              <tr>
                <td className="py-1.5 pr-4">GBM (monotonic)</td>
                <td className="text-label py-1.5 text-xs">{mc.gbm_walk_forward_mae} wins</td>
              </tr>
            </tbody>
          </table>
          <p className="mt-3">
            Winner: <strong>{mc.winner.toUpperCase()}</strong>, params{" "}
            <code className="text-label text-[11px] text-ink-muted">
              {JSON.stringify(metadata.winning_model.best_params)}
            </code>
          </p>
        </div>

        <p>
          <strong>Prediction interval.</strong> {metadata.prediction_interval.method} (
          {metadata.prediction_interval.coverage} coverage).
        </p>

        {metadata.backtest_accuracy && (
          <div>
            <p className="text-label mb-2 text-xs text-ink">Backtested Accuracy</p>
            <div className="flex gap-6">
              {metadata.backtest_accuracy.thresholds_wins.map((t) => (
                <div key={t}>
                  <p className="text-label text-2xl text-accent">
                    {(metadata.backtest_accuracy.overall[String(t)] * 100).toFixed(0)}%
                  </p>
                  <p className="text-label text-[10px] text-ink-muted">within ±{t} wins</p>
                </div>
              ))}
            </div>
            <p className="mt-3">{metadata.backtest_accuracy.note}</p>
          </div>
        )}

        {metadata.calibration && (
          <div>
            <p className="text-label mb-2 text-xs text-ink">Calibration</p>
            <p>{metadata.calibration.description}</p>
            <table className="mt-3 w-full max-w-sm border-collapse text-left">
              <tbody>
                <tr className="border-b border-line/5">
                  <td className="py-1.5 pr-4">Walk-forward MAE, uncalibrated</td>
                  <td className="text-label py-1.5 text-xs">
                    {metadata.calibration.walk_forward_mae_uncalibrated} wins
                  </td>
                </tr>
                <tr>
                  <td className="py-1.5 pr-4">Walk-forward MAE, calibrated</td>
                  <td className="text-label py-1.5 text-xs">
                    {metadata.calibration.walk_forward_mae_calibrated} wins
                  </td>
                </tr>
              </tbody>
            </table>
            <p className="mt-3">{metadata.calibration.note}</p>
          </div>
        )}

        <div>
          <p className="text-label mb-1 text-xs text-ink">Top Features by Permutation Importance</p>
          <p className="mb-2">
            We scramble one feature at a time and see how much worse the model gets — the
            bigger the damage, the more that feature is actually doing.
          </p>
          <table className="w-full max-w-md border-collapse text-left">
            <tbody>
              {metadata.top_feature_importance.slice(0, 8).map((f) => (
                <tr key={f.feature} className="border-b border-line/5">
                  <td className="text-label py-1.5 pr-4 text-xs">{f.feature}</td>
                  <td className="py-1.5 text-ink-muted">{f.importance_mae_increase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {Object.keys(metadata.feature_notes).length > 0 && (
          <div>
            <p className="text-label mb-2 text-xs text-ink">Notes on Specific Features</p>
            <ul className="space-y-2">
              {Object.entries(metadata.feature_notes).map(([feature, note]) => (
                <li key={feature}>
                  <strong>{feature}</strong> — {note}
                </li>
              ))}
            </ul>
          </div>
        )}

        {metadata.roster_projection && (
          <div>
            <p className="text-label mb-2 text-xs text-ink">
              Next Season&apos;s Roster: What&apos;s Real, What&apos;s Carried Over
            </p>
            <p>{metadata.roster_projection.note}</p>
            {metadata.roster_projection.available && (
              <p className="text-label mt-2 text-[11px] text-ink-muted">
                Roster season {metadata.roster_projection.season} —{" "}
                {metadata.roster_projection.teams_projected.length} team(s) from real current
                rosters, {metadata.roster_projection.teams_fallback_stale.length} on stale
                carry-forward.
              </p>
            )}
          </div>
        )}

        <p className="text-label text-[11px] text-ink-muted/70">
          Trained on {metadata.n_training_rows} team-seasons ({metadata.n_teams} teams, feature
          seasons {Math.min(...metadata.feature_seasons_used)}–
          {Math.max(...metadata.feature_seasons_used)}). Generated{" "}
          {new Date(metadata.generated_at).toLocaleString()}.
        </p>
      </div>
    </details>
  );
}
