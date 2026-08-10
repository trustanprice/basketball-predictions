import { getMethodology, getPredictions } from "@/lib/api";
import { PredictionsExplorer } from "@/components/PredictionsExplorer";

export default async function PredictionsPage() {
  const [predictions, methodology] = await Promise.all([getPredictions(), getMethodology()]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Team Win Predictions</h1>
        <p className="mt-1 text-neutral-600">
          Walk-forward validated, with an 80% prediction interval and the full
          methodology behind every number.
        </p>
      </div>
      <PredictionsExplorer predictions={predictions} methodology={methodology} />
    </div>
  );
}
