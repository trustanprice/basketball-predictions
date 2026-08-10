import { getCoachCareerSummary, getCoachTeamSeasons } from "@/lib/api";
import { CoachingExplorer } from "@/components/CoachingExplorer";

export default async function CoachingPage() {
  const [careerSummary, teamSeasons] = await Promise.all([
    getCoachCareerSummary(),
    getCoachTeamSeasons(),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Coaching Evaluation</h1>
        <p className="mt-1 max-w-2xl text-neutral-600">
          Actual win% vs. a roster-talent-implied win% — &quot;wins above roster
          expectation.&quot; Click a coach for their full team-season history, and expand
          any season for the talent composite&apos;s formula.
        </p>
      </div>
      <CoachingExplorer careerSummary={careerSummary} teamSeasons={teamSeasons} />
    </div>
  );
}
