import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity } from "lucide-react";
import { request } from "./api";
import { AuditPanel } from "./components/AuditPanel";
import { FleetPanel } from "./components/FleetPanel";
import { OrderQueue } from "./components/OrderQueue";
import { OverrideModal } from "./components/OverrideModal";
import { ScenarioToolbar } from "./components/ScenarioToolbar";
import { TimelineDrawer } from "./components/TimelineDrawer";
import { TopStrip } from "./components/TopStrip";
import { TriagePanel } from "./components/TriagePanel";
import type { AppState, Order, TimelineEvent, Triage } from "./types";

export function App() {
  const [state, setState] = useState<AppState | null>(null);
  const [triage, setTriage] = useState<Triage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [overrideOrder, setOverrideOrder] = useState<Order | null>(null);
  const [overrideAction, setOverrideAction] = useState("ground_fallback");
  const [operator, setOperator] = useState("Rohan");
  const [reason, setReason] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [nextState, nextTriage] = await Promise.all([request<AppState>("/api/state"), request<Triage>("/api/triage")]);
      setState(nextState);
      setTriage(nextTriage);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach backend");
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(async () => {
      await request<AppState>("/api/sim/tick", { method: "POST", body: JSON.stringify({ minutes: 1 }) }).catch(() => null);
      refresh();
    }, 1800);
    return () => window.clearInterval(timer);
  }, [refresh]);

  useEffect(() => {
    if (!selectedOrder) return;
    request<{ events: TimelineEvent[] }>(`/api/orders/${selectedOrder.id}/timeline`)
      .then((body) => setTimeline(body.events))
      .catch((err) => setError(err instanceof Error ? err.message : "Timeline failed"));
  }, [selectedOrder, state?.clock]);

  const ordersById = useMemo(() => new Map(state?.orders.map((order) => [order.id, order]) ?? []), [state]);
  const gaugePct = state ? Math.min(150, Math.round((state.metrics.demand_per_hour / Math.max(1, state.metrics.throughput_per_hour)) * 100)) : 0;

  async function scenario(path: string) {
    await request<AppState>(path, { method: "POST" });
    await refresh();
  }

  async function applyPlan() {
    await request<AppState>("/api/triage/apply", { method: "POST", body: JSON.stringify({ operator }) });
    await refresh();
  }

  async function submitOverride() {
    if (!overrideOrder || !reason.trim() || !operator.trim()) return;
    await request<AppState>(`/api/orders/${overrideOrder.id}/override`, {
      method: "POST",
      body: JSON.stringify({ target_action: overrideAction, operator, reason })
    });
    setOverrideOrder(null);
    setReason("");
    await refresh();
  }

  if (!state || !triage) {
    return (
      <main className="boot">
        <Activity className="spin" size={24} />
        <span>Connecting to triage service</span>
        {error && <strong>{error}</strong>}
      </main>
    );
  }

  return (
    <main className="app-shell">
      <TopStrip state={state} gaugePct={gaugePct} />
      {error && <div className="banner">{error}</div>}
      <ScenarioToolbar onScenario={scenario} />

      <section className="grid">
        <FleetPanel state={state} />
        <OrderQueue state={state} gaugePct={gaugePct} onSelectOrder={setSelectedOrder} />
        <TriagePanel triage={triage} ordersById={ordersById} onApplyPlan={applyPlan} onOverride={setOverrideOrder} />
        <AuditPanel state={state} />
      </section>

      {selectedOrder && (
        <TimelineDrawer order={selectedOrder} events={timeline} onClose={() => setSelectedOrder(null)} />
      )}

      {overrideOrder && (
        <OverrideModal
          order={overrideOrder}
          operator={operator}
          reason={reason}
          targetAction={overrideAction}
          onOperatorChange={setOperator}
          onReasonChange={setReason}
          onTargetActionChange={setOverrideAction}
          onSubmit={submitOverride}
          onClose={() => setOverrideOrder(null)}
        />
      )}
    </main>
  );
}
