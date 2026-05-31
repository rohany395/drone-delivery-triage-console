export type Aircraft = {
  id: string;
  model: string;
  battery_pct: number;
  hours_since_service: number;
  state: string;
  current_mission_id?: string | null;
  charge_complete_at?: number | null;
  grounded_until?: number;
  maintenance_reason?: string;
};

export type Order = {
  id: string;
  vertical: string;
  priority_tier: "P0" | "P1" | "P2";
  payload_kg: number;
  created_at: number;
  promised_by: number;
  destination: string;
  urgency_flag: boolean;
  state: string;
  assigned_aircraft_id?: string | null;
  mission_id?: string | null;
};

export type Mission = {
  id: string;
  order_id: string;
  aircraft_id: string;
  launched_at: number;
  eta: number;
  state: string;
};

export type Check = { name: string; ok: boolean; detail: string };

export type AuditEntry = {
  id: number;
  ts: number;
  type: string;
  order_id: string;
  operator: string;
  reason: string;
  target_action: string;
};

export type AppState = {
  clock: number;
  nest: { id: string; name: string; weather_state: string; charging_slots: number; status: string };
  fleet: Aircraft[];
  orders: Order[];
  active_missions: Mission[];
  interventions: AuditEntry[];
  metrics: {
    backlog: number;
    ready_aircraft: number;
    operational_aircraft: number;
    throughput_per_hour: number;
    demand_per_hour: number;
    sla_risk: number;
    capacity_tight: boolean;
  };
  invariants: Check[];
};

export type PlanItem = { order_id: string; rationale: string; committed: boolean };

export type Triage = {
  capacity_tight: boolean;
  generated_at_clock: number;
  plan: { protect_now: PlanItem[]; defer: PlanItem[]; ground_fallback: PlanItem[] };
  summary: {
    medical_orders_protected: number;
    retail_deferred: number;
    p0_auto_deferred: number;
    sla_breaches_avoided_vs_fifo: number;
    estimated_delay_minutes: number;
  };
  fifo_baseline: { protect_now: string[]; deferred_p0_count: number; risk: string };
};

export type TimelineEvent = {
  id: number;
  clock: number;
  type: string;
  actor: string;
  payload: Record<string, unknown>;
};
