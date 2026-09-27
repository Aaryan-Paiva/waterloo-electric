import type { Provenance, ProvenanceType } from "@/types/api";

const META: Record<ProvenanceType, { label: string; glyph: string; color: string }> = {
  observed: { label: "Observed", glyph: "◉", color: "var(--observed)" },
  derived: { label: "Derived", glyph: "◈", color: "var(--derived)" },
  modeled: { label: "Modeled", glyph: "◇", color: "var(--modeled)" },
  hypothetical: { label: "Hypothetical", glyph: "✦", color: "var(--hypo)" },
};

export function ProvenanceBadge({ type }: { type: ProvenanceType }) {
  const m = META[type];
  return (
    <span className="chip" style={{ borderColor: m.color, color: m.color }} title={m.label}>
      <span aria-hidden>{m.glyph}</span>
      {m.label}
    </span>
  );
}

export function ProvenanceRow({ label, p }: { label: string; p: Provenance }) {
  return (
    <li className="flex flex-col gap-1 py-2 border-b" style={{ borderColor: "var(--line)" }}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm">{label}</span>
        <ProvenanceBadge type={p.type} />
      </div>
      {p.sourceName && <span className="text-xs" style={{ color: "var(--muted)" }}>{p.sourceName}</span>}
      {p.notes && <span className="text-xs" style={{ color: "var(--muted)" }}>{p.notes}</span>}
    </li>
  );
}
