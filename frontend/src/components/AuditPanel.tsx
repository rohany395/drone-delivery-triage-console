import { CheckCircle2, History } from "lucide-react";
import type { AppState } from "../types";
import { classNames } from "../utils";
import { PanelTitle } from "./PanelTitle";

type AuditPanelProps = {
  state: AppState;
};

export function AuditPanel({ state }: AuditPanelProps) {
  return (
    <section className="panel audit-panel">
      <PanelTitle icon={<History />} title="Audit & Reconciliation" detail={`${state.interventions.length} interventions`} />
      <div className="checks">
        {state.invariants.map((check) => (
          <div key={check.name} className={classNames("check", check.ok ? "ok" : "fail")}>
            <CheckCircle2 size={15} />
            <span>
              <strong>{check.name}</strong>
              <small>{check.detail}</small>
            </span>
          </div>
        ))}
      </div>
      <div className="audit-list">
        {state.interventions.slice(0, 8).map((entry) => (
          <article key={entry.id}>
            <strong>{entry.order_id} {"->"} {entry.target_action.replace("_", " ")}</strong>
            <span>{entry.operator}: {entry.reason}</span>
          </article>
        ))}
      </div>
    </section>
  );
}
