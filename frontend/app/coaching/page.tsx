import { getCoachCareerSummary, getCoachTeamSeasons, getPredictions } from "@/lib/api";
import { CoachingExplorer } from "@/components/CoachingExplorer";
import { ScrollSpyNav } from "@/components/ScrollSpyNav";

const SECTIONS = [
  {
    id: "career-summary",
    number: "01",
    label: "Career Summary",
    description: "One row per coach, aggregated across every team and season they've coached.",
  },
  {
    id: "wins-above-expectation",
    number: "02",
    label: "WAE Detail",
    description: "Click a coach above for their full team-season breakdown.",
  },
];

export default async function CoachingPage() {
  // getPredictions() added here (not previously fetched on this page) so a
  // team-name click can show that team's current win-model forecast — a new
  // requirement, not incidental scope creep; see frontend/AGENTS.md.
  const [careerSummary, teamSeasons, predictions] = await Promise.all([
    getCoachCareerSummary(),
    getCoachTeamSeasons(),
    getPredictions(),
  ]);

  return (
    <div className="md:pl-16">
      <ScrollSpyNav sections={SECTIONS} />
      <div className="mb-12">
        <p className="text-label mb-3 text-xs text-accent">Phase 4 — Coaching Eval</p>
        <h1 className="text-headline text-4xl sm:text-5xl">Coaching Evaluation</h1>
        <p className="prose-narrow mt-4 text-ink-muted">
          Actual win% vs. a roster-talent-implied win% — <strong>&quot;wins above roster
          expectation.&quot;</strong> Click a coach for their full team-season history, and
          expand any season for the talent composite&apos;s formula.
        </p>
      </div>
      <CoachingExplorer careerSummary={careerSummary} teamSeasons={teamSeasons} predictions={predictions} />
    </div>
  );
}
