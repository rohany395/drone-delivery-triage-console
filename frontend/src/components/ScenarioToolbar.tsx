import { Activity, AlertTriangle, Pause, Play, RefreshCcw, SlidersHorizontal, StepForward } from "lucide-react";

type ScenarioToolbarProps = {
  onScenario: (path: string) => void;
  running: boolean;
  onStep: () => void;
  onToggleRunning: () => void;
};

export function ScenarioToolbar({ onScenario, running, onStep, onToggleRunning }: ScenarioToolbarProps) {
  return (
    <section className="toolbar" aria-label="Scenario controls">
      <div className="sim-controls" aria-label="Simulation clock controls">
        <button className="clock-step" onClick={onStep}><StepForward size={16} /> Step</button>
        <button className="clock-toggle" onClick={onToggleRunning}>{running ? <Pause size={16} /> : <Play size={16} />} {running ? "Pause" : "Play"}</button>
      </div>
      <button className="scenario-storm" onClick={() => onScenario("/api/scenarios/storm-front")}><AlertTriangle size={16} /> Storm front</button>
      <button className="scenario-aircraft" onClick={() => onScenario("/api/scenarios/aircraft-down")}><SlidersHorizontal size={16} /> Aircraft down</button>
      <button className="scenario-demand" onClick={() => onScenario("/api/scenarios/demand-spike")}><Activity size={16} /> Demand spike</button>
      <button className="scenario-reset" onClick={() => onScenario("/api/sim/reset")}><RefreshCcw size={16} /> Reset</button>
    </section>
  );
}
