"use client";

import { FieldLabel, Input, Select } from "@/components/ui/Input";
import type { Condition, Policy } from "@/lib/types";

const OUTCOME_KINDS = ["approve", "deny", "route", "escalate"] as const;
const NUMBER_OPS = ["gt", "gte", "lt", "lte", "eq", "neq"];
const STRING_OPS = ["eq", "neq", "in", "not_in"];
const BOOL_OPS = ["eq"];

function opsFor(valueType: string): string[] {
  if (valueType === "number") return NUMBER_OPS;
  if (valueType === "boolean") return BOOL_OPS;
  return STRING_OPS;
}

/** Editable Policy form: the reviewer structures the policy the citation will
 *  justify. Controlled — the parent owns the draft state and re-saves. */
export function PolicyEditor({
  policy,
  onChange,
}: {
  policy: Policy;
  onChange: (next: Policy) => void;
}) {
  function patch(p: Partial<Policy>) {
    onChange({ ...policy, ...p });
  }
  function patchCondition(i: number, c: Partial<Condition>) {
    patch({ conditions: policy.conditions.map((cond, idx) => (idx === i ? { ...cond, ...c } : cond)) });
  }
  function addCondition() {
    patch({ conditions: [...policy.conditions, { field: "", operator: "eq", value: "", value_type: "string" }] });
  }
  function removeCondition(i: number) {
    patch({ conditions: policy.conditions.filter((_, idx) => idx !== i) });
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <FieldLabel>Policy id</FieldLabel>
          <Input mono value={policy.id} onChange={(e) => patch({ id: e.target.value })} placeholder="refund.annual_14d" className="h-9" />
        </div>
        <div>
          <FieldLabel>Workflow</FieldLabel>
          <Input mono value={policy.workflow} onChange={(e) => patch({ workflow: e.target.value })} placeholder="refund" className="h-9" />
        </div>
      </div>

      <div className="grid grid-cols-[1fr_1fr_auto] gap-3">
        <div>
          <FieldLabel>Outcome</FieldLabel>
          <Select mono value={policy.effect.kind} onChange={(e) => patch({ effect: { ...policy.effect, kind: e.target.value as Policy["effect"]["kind"] } })}>
            {OUTCOME_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
          </Select>
        </div>
        <div>
          <FieldLabel>Action</FieldLabel>
          <Input mono value={policy.effect.action} onChange={(e) => patch({ effect: { ...policy.effect, action: e.target.value } })} placeholder="approve_full_refund" className="h-9" />
        </div>
        <div>
          <FieldLabel>Priority</FieldLabel>
          <Input mono type="number" value={policy.priority} onChange={(e) => patch({ priority: Number(e.target.value) })} className="h-9 w-20" />
        </div>
      </div>

      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="t-eyebrow">Conditions</span>
          <button type="button" onClick={addCondition} className="text-xs font-medium text-link underline underline-offset-2">+ add condition</button>
        </div>
        {policy.conditions.length === 0 ? (
          <p className="text-xs text-mute">No conditions — needs explicit sign-off to publish.</p>
        ) : (
          <div className="space-y-2">
            {policy.conditions.map((c, i) => (
              <div key={i} className="grid grid-cols-[1fr_auto_1fr_auto_auto] items-center gap-2">
                <Input mono value={c.field} onChange={(e) => patchCondition(i, { field: e.target.value })} placeholder="field" className="h-9" />
                <Select mono value={c.operator} onChange={(e) => patchCondition(i, { operator: e.target.value })} className="w-auto">
                  {opsFor(c.value_type).map((op) => <option key={op} value={op}>{op}</option>)}
                </Select>
                <Input
                  mono
                  value={String(c.value ?? "")}
                  onChange={(e) => {
                    const raw = e.target.value;
                    const value = c.value_type === "number" ? Number(raw) : c.value_type === "boolean" ? raw === "true" : raw;
                    patchCondition(i, { value });
                  }}
                  placeholder="value"
                  className="h-9"
                />
                <Select
                  mono
                  value={c.value_type}
                  onChange={(e) => {
                    const value_type = e.target.value as Condition["value_type"];
                    const validOps = opsFor(value_type);
                    const operator = validOps.includes(c.operator) ? c.operator : validOps[0];
                    patchCondition(i, { value_type, operator });
                  }}
                  className="w-auto"
                >
                  <option value="string">string</option>
                  <option value="number">number</option>
                  <option value="boolean">boolean</option>
                </Select>
                <button type="button" onClick={() => removeCondition(i)} className="px-1 text-xs text-mute hover:text-deny" aria-label="remove condition">✕</button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <FieldLabel>Rationale</FieldLabel>
        <Input mono value={policy.rationale} onChange={(e) => patch({ rationale: e.target.value })} placeholder="One-sentence paraphrase of the rule." className="h-9" />
      </div>
    </div>
  );
}
