// Visualizes the 1..25 priority score as a colored band.
export function PriorityBadge({ value }) {
  const bucket = value >= 15 ? "high" : value >= 6 ? "med" : "low";
  return <span className={`prio prio-${bucket}`}>{value}</span>;
}
