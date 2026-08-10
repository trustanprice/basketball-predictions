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
            Two candidates — <strong>{mc.candidates.join(" and ")}</strong> — were each tuned
            via walk-forward cross-validation, then compared on walk-forward mean absolute
            error across {mc.n_walk_forward_folds} rolling folds:
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

        <div>
          <p className="text-label mb-1 text-xs text-ink">Top Features by Permutation Importance</p>
          <p className="mb-2">
            How much walk-forward error gets worse when a feature is shuffled — bigger is more
            important.
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
