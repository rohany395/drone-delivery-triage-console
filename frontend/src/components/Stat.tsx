type StatProps = {
  label: string;
  value: number;
};

export function Stat({ label, value }: StatProps) {
  return (
    <div className="stat">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
