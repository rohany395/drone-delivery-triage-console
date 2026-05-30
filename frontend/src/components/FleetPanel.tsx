import { BatteryCharging, Plane } from "lucide-react";
import type { AppState } from "../types";
import { classNames } from "../utils";
import { PanelTitle } from "./PanelTitle";

type FleetPanelProps = {
  state: AppState;
};

export function FleetPanel({ state }: FleetPanelProps) {
  return (
    <aside className="panel fleet-panel">
      <PanelTitle icon={<Plane />} title="Fleet" detail={`${state.active_missions.length} active missions`} />
      <div className="fleet-list">
        {state.fleet.map((aircraft) => (
          <article key={aircraft.id} className={classNames("aircraft", aircraft.state)}>
            <div>
              <strong>{aircraft.id}</strong>
              <span>{aircraft.model}</span>
            </div>
            <p>{aircraft.state.replace("_", " ")}</p>
            <div className="battery"><BatteryCharging size={14} /> {aircraft.battery_pct}%</div>
            <small>
              {aircraft.current_mission_id
                ? `Mission ${aircraft.current_mission_id}`
                : aircraft.charge_complete_at
                  ? `Ready T+${aircraft.charge_complete_at}m`
                  : aircraft.maintenance_reason ?? "Available"}
            </small>
          </article>
        ))}
      </div>
    </aside>
  );
}
