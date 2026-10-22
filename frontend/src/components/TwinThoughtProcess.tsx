import { dispositionLabel } from '../dispositionDisplay'
import type { DispositionClass } from '../types'

const ESCALATION_REASON_TEXT: Record<string, string> = {
  persona_response_unparseable:
    "The AI couldn't produce an answer in the expected format, so this is treated as uncertain rather than guessed.",
  precedent_disagreement:
    "The AI's answer disagreed with what similar past cases from your own history suggested.",
  constraint_violation:
    "This case tripped one of the built-in safety rules, which always overrides the AI's own reasoning.",
  low_confidence: "The twin's confidence in this specific answer was too low to show it directly.",
}

function friendlyEscalationReason(reason: string): string {
  return ESCALATION_REASON_TEXT[reason] ?? reason
}

export interface TwinThoughtProcessData {
  draftDisposition: string
  disposition: string | null
  escalated: boolean
  escalationReasons: string[]
  precedentCaseRefs: string[]
  explanation: {
    matchedConditions: string[]
    guidelineEvidence: string[]
    constraintRulesTriggered: string[]
    reasoningSummary: string
  }
}

export function TwinThoughtProcess({ result }: { result: TwinThoughtProcessData }) {
  const { explanation } = result
  const draftOverridden = result.disposition !== null && result.disposition !== result.draftDisposition

  return (
    <div className="thought-process">
      <h4>How the twin reached this</h4>

      {draftOverridden && (
        <p className="thought-note">
          Its first instinct was{' '}
          <strong>{dispositionLabel(result.draftDisposition as DispositionClass)}</strong>, but a
          safety rule changed that to{' '}
          <strong>{dispositionLabel(result.disposition as DispositionClass)}</strong>.
        </p>
      )}

      <ul className="thought-list">
        {result.precedentCaseRefs.length > 0 ? (
          <li>
            Looked at {result.precedentCaseRefs.length} similar past case
            {result.precedentCaseRefs.length === 1 ? '' : 's'} from your own case history.
          </li>
        ) : (
          <li>Didn't use any past-case history for this answer.</li>
        )}

        {explanation.matchedConditions.length > 0 ? (
          <li>
            Found official guideline information related to:{' '}
            {explanation.matchedConditions.join(', ')}.
          </li>
        ) : (
          <li>Found no closely related official guideline information for this case.</li>
        )}

        {explanation.constraintRulesTriggered.length > 0 && (
          <li className="thought-list--warning">
            A built-in safety rule fired ({explanation.constraintRulesTriggered.join(', ')}) --
            this always overrides everything else above.
          </li>
        )}
      </ul>

      {result.escalated && result.escalationReasons.length > 0 && (
        <div className="escalation-reasons">
          <h5>Why this was sent for review</h5>
          <ul>
            {result.escalationReasons.map((reason) => (
              <li key={reason}>{friendlyEscalationReason(reason)}</li>
            ))}
          </ul>
        </div>
      )}

      {explanation.guidelineEvidence.length > 0 && (
        <details className="guideline-details">
          <summary>Guideline details it used</summary>
          <ul className="evidence-list">
            {explanation.guidelineEvidence.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
      )}

      <p className="thought-raw">{explanation.reasoningSummary}</p>
    </div>
  )
}
