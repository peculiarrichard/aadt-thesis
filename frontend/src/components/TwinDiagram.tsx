// A small explanatory diagram of the ADT-RA concept (addt_solution_design.md
// Section 3): a clinician's digital twin drafts a disposition from guideline
// grounding, precedent memory, and persona conditioning, a constraint checker
// can veto that draft, and the clinician always reviews the result before it's
// final (Section 9 -- an escalated draft is never shown as a normal output).
export function TwinDiagram() {
  return (
    <svg
      className="twin-diagram"
      viewBox="0 0 720 260"
      role="img"
      aria-labelledby="twin-diagram-title twin-diagram-desc"
      xmlns="http://www.w3.org/2000/svg"
    >
      <title id="twin-diagram-title">How the agentic digital twin works</title>
      <desc id="twin-diagram-desc">
        The clinician's twin drafts a disposition from guideline grounding, precedent memory, and
        persona conditioning. A constraint checker can veto the draft. The clinician always reviews
        the result before it's final.
      </desc>

      <defs>
        <marker
          id="diagram-arrowhead"
          viewBox="0 0 10 10"
          refX="8"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0,0 L10,5 L0,10 z" className="diagram-arrowhead-fill" />
        </marker>
      </defs>

      {/* Doctor */}
      <circle cx="70" cy="120" r="36" className="diagram-node diagram-node--doctor" />
      <text x="70" y="115" textAnchor="middle" className="diagram-node-label">
        Doctor
      </text>
      <text x="70" y="131" textAnchor="middle" className="diagram-node-label">
        (DDT)
      </text>

      {/* Doctor -> Twin */}
      <line
        x1="108"
        y1="120"
        x2="248"
        y2="120"
        className="diagram-arrow"
        markerEnd="url(#diagram-arrowhead)"
      />

      {/* Twin hub */}
      <rect x="250" y="30" width="220" height="180" rx="16" className="diagram-hub" />
      <text x="360" y="54" textAnchor="middle" className="diagram-hub-title">
        Agentic Digital Twin
      </text>

      <rect x="262" y="68" width="94" height="38" rx="8" className="diagram-node" />
      <text
        x="309"
        y="84"
        textAnchor="middle"
        className="diagram-node-label diagram-node-label--sm"
      >
        <tspan x="309" dy="0">
          Guideline
        </tspan>
        <tspan x="309" dy="13">
          grounding
        </tspan>
      </text>

      <rect x="364" y="68" width="94" height="38" rx="8" className="diagram-node" />
      <text
        x="411"
        y="84"
        textAnchor="middle"
        className="diagram-node-label diagram-node-label--sm"
      >
        <tspan x="411" dy="0">
          Precedent
        </tspan>
        <tspan x="411" dy="13">
          memory
        </tspan>
      </text>

      <rect x="262" y="114" width="94" height="38" rx="8" className="diagram-node" />
      <text
        x="309"
        y="130"
        textAnchor="middle"
        className="diagram-node-label diagram-node-label--sm"
      >
        <tspan x="309" dy="0">
          Persona
        </tspan>
        <tspan x="309" dy="13">
          conditioning
        </tspan>
      </text>

      <rect
        x="364"
        y="114"
        width="94"
        height="38"
        rx="8"
        className="diagram-node diagram-node--veto"
      />
      <text
        x="411"
        y="130"
        textAnchor="middle"
        className="diagram-node-label diagram-node-label--sm"
      >
        <tspan x="411" dy="0">
          Constraint
        </tspan>
        <tspan x="411" dy="13">
          checker
        </tspan>
      </text>

      <text x="360" y="192" textAnchor="middle" className="diagram-hub-caption">
        drafts, then can be vetoed
      </text>

      {/* Twin -> Output */}
      <line
        x1="472"
        y1="120"
        x2="562"
        y2="120"
        className="diagram-arrow"
        markerEnd="url(#diagram-arrowhead)"
      />

      {/* Output */}
      <rect x="564" y="85" width="130" height="70" rx="12" className="diagram-node" />
      <text
        x="629"
        y="112"
        textAnchor="middle"
        className="diagram-node-label diagram-node-label--sm"
      >
        Disposition
      </text>
      <text
        x="629"
        y="128"
        textAnchor="middle"
        className="diagram-node-label diagram-node-label--sm"
      >
        + explanation
      </text>

      {/* Feedback loop: output -> doctor reviews */}
      <path
        d="M 629 158 C 629 232, 70 232, 70 160"
        className="diagram-feedback"
        markerEnd="url(#diagram-arrowhead)"
      />
      <text x="360" y="248" textAnchor="middle" className="diagram-feedback-label">
        the clinician always reviews the result before it's final
      </text>
    </svg>
  )
}
