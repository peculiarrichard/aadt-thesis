import { api, type StructuredDraft } from '../api'
import { CaseForm } from './CaseForm'

// Shared review-before-save step for Phase M's two recording flows and its
// de-identified-text upload: nothing upstream of this ever writes to the
// database (api.confirmDraft is the only call that does) -- the doctor
// always sees and can edit the auto-structured fields first.
interface DraftReviewProps {
  draft: StructuredDraft
  sourceType: 'walkthrough' | 'real_consultation'
  onSaved: (caseId: string) => void
}

export function DraftReview({ draft, sourceType, onSaved }: DraftReviewProps) {
  const redactionEntries = Object.entries(draft.redactionSummary)

  return (
    <div className="draft-review">
      <h3>Review before saving</h3>
      {redactionEntries.length > 0 && (
        <p className="note">
          Redacted before processing: {redactionEntries.map(([k, v]) => `${k} (${v})`).join(', ')}.
          Review the text below to confirm nothing identifying remains.
        </p>
      )}
      {draft.llmFlagged && (
        <p className="note note--flag">
          Automatic privacy check:{' '}
          {draft.llmFlagDetails ?? 'this case may reference a real, identifiable patient.'} Please
          review carefully before confirming.
        </p>
      )}
      <CaseForm
        extraNote="Auto-structured from your recording/upload -- check and correct anything before saving."
        submitLabel="Save case"
        requireAttestation
        initial={{
          caseId: draft.caseId ?? undefined,
          caseText: draft.caseText,
          initialImpression: draft.initialImpression ?? undefined,
          questionsToAsk: draft.questionsToAsk,
          examinationOrChecks: draft.examinationOrChecks ?? undefined,
          factorsTowardReferral: draft.factorsTowardReferral ?? undefined,
          factorsAgainstReferral: draft.factorsAgainstReferral ?? undefined,
          flipUp: draft.flipUp ?? undefined,
          flipDown: draft.flipDown ?? undefined,
          redFlags: draft.redFlags ?? undefined,
          confidence: draft.confidence ?? undefined,
          generalRule: draft.generalRule ?? undefined,
          disposition: draft.disposition ?? undefined,
          dispositionReason: draft.dispositionReason ?? undefined,
        }}
        onSubmit={async (fields) => {
          const { caseId } = await api.confirmDraft(fields, sourceType, true)
          onSaved(caseId)
        }}
      />
    </div>
  )
}
