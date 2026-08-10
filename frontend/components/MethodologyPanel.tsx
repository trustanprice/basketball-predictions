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
    <details className="rounded-lg border border-neutral-200 bg-white p-4">
      <summary className="cursor-pointer font-medium text-neutral-900">
        How this was calculated
      </summary>
      <div className="mt-4 space-y-4 text-sm text-neutral-700">
        <p>
          <span className="font-medium">Validation method: </span>
          {metadata.validation_method}
        </p>
        <p>
          <span className="font-medium">Target: </span>
          {metadata.target_definition}
        </p>

        <div>
          <p className="font-medium text-neutral-900">Model selection</p>
          <p>
            Two candidates — {mc.candidates.join(" and ")} — were each tuned via
            walk-forward cross-validation, then compared on walk-forward mean
            absolute error across {mc.n_walk_forward_folds} rolling folds:
          </p>
          <table className="mt-2 w-full max-w-sm border-collapse text-left">
            <thead>
              <tr className="border-b border-neutral-200">
                <th className="py-1 pr-4 font-medium">Candidate</th>
                <th className="py-1 font-medium">Walk-forward MAE</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="py-1 pr-4">KNN</td>
                <td className="py-1">{mc.knn_walk_forward_mae} wins</td>
              </tr>
              <tr>
                <td className="py-1 pr-4">GBM (monotonic)</td>
                <td className="py-1">{mc.gbm_walk_forward_mae} wins</td>
              </tr>
            </tbody>
          </table>
          <p className="mt-2">
            Winner: <span className="font-medium">{mc.winner.toUpperCase()}</span>, params{" "}
            <code className="text-xs">{JSON.stringify(metadata.winning_model.best_params)}</code>
          </p>
        </div>

        <p>
          <span className="font-medium">Prediction interval: </span>
          {metadata.prediction_interval.method} ({metadata.prediction_interval.coverage} coverage).
        </p>

        <div>
          <p className="font-medium text-neutral-900">
            Top features by permutation importance
          </p>
          <p className="mb-2">
            How much walk-forward error gets worse when a feature is shuffled — bigger
            is more important.
          </p>
          <table className="w-full max-w-md border-collapse text-left">
            <tbody>
              {metadata.top_feature_importance.slice(0, 8).map((f) => (
                <tr key={f.feature} className="border-b border-neutral-100">
                  <td className="py-1 pr-4">{f.feature}</td>
                  <td className="py-1 text-neutral-500">{f.importance_mae_increase}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {Object.keys(metadata.feature_notes).length > 0 && (
          <div>
            <p className="font-medium text-neutral-900">Notes on specific features</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {Object.entries(metadata.feature_notes).map(([feature, note]) => (
                <li key={feature}>
                  <span className="font-medium">{feature}</span> — {note}
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-neutral-500">
          Trained on {metadata.n_training_rows} team-seasons ({metadata.n_teams} teams,
          feature seasons {Math.min(...metadata.feature_seasons_used)}–
          {Math.max(...metadata.feature_seasons_used)}). Generated{" "}
          {new Date(metadata.generated_at).toLocaleString()}.
        </p>
      </div>
    </details>
  );
}
