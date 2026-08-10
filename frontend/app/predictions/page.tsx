import { getMethodology, getPredictions } from "@/lib/api";
import { PredictionsExplorer } from "@/components/PredictionsExplorer";
import { ScrollSpyNav } from "@/components/ScrollSpyNav";

const SECTIONS = [
  {
    id: "prediction",
    number: "01",
    label: "Prediction",
    description: "Pick any team for its predicted wins, 80% interval, and forecast season.",
  },
  {
    id: "methodology",
    number: "02",
    label: "Methodology",
    description: "Validation method, model comparison, and the top features driving the model.",
  },
  {
    id: "chart",
    number: "03",
    label: "Chart",
    description: "All 30 teams plotted on the two most-influential available features.",
  },
];

export default async function PredictionsPage() {
  const [predictions, methodology] = await Promise.all([getPredictions(), getMethodology()]);

  return (
    <div className="md:pl-16">
      <ScrollSpyNav sections={SECTIONS} />
      <div className="mb-12">
        <p className="text-label mb-3 text-xs text-accent">Phase 1 — Win Model</p>
        <h1 className="text-headline text-4xl sm:text-5xl">Team Win Predictions</h1>
        <p className="prose-narrow mt-4 text-ink-muted">
          Every number here comes from a model that was tested the honest way — evaluated only
          on seasons it never trained on. Each forecast ships with an 80% interval and a full
          breakdown of how it was built, not just a single confident-looking number.
        </p>
      </div>
      <PredictionsExplorer predictions={predictions} methodology={methodology} />
    </div>
  );
}
