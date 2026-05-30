import { Activity, AlertTriangle, RefreshCcw, SlidersHorizontal } from "lucide-react";

type ScenarioToolbarProps = {
  onScenario: (path: string) => void;
};

export function ScenarioToolbar({ onScenario }: ScenarioToolbarProps) {
  return (
    <section className="toolbar" aria-label="Scenario controls">
      <button onClick={() => onScenario("/api/scenarios/storm-front")}><AlertTriangle size={16} /> Storm front</button>
      <button onClick={() => onScenario("/api/scenarios/aircraft-down")}><SlidersHorizontal size={16} /> Aircraft down</button>
      <button onClick={() => onScenario("/api/scenarios/demand-spike")}><Activity size={16} /> Demand spike</button>
      <button onClick={() => onScenario("/api/sim/reset")}><RefreshCcw size={16} /> Reset</button>
    </section>
  );
}
