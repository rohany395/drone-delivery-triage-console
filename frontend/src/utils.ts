import type { Order } from "./types";

export function classNames(...names: Array<string | false | null | undefined>) {
  return names.filter(Boolean).join(" ");
}

export function slaMinutes(order: Order, clock: number) {
  return order.promised_by - clock;
}
