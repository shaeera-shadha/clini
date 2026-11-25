import { useNavigate } from 'react-router-dom'

import { Card, PillButton } from '../components/ui/primitives'

/** Shown on pages that need a generated note when there is none yet. */
export function NeedsNote({ what }: { what: string }) {
  const navigate = useNavigate()
  return (
    <div className="p-6">
      <Card>
        <p className="text-body">{what}</p>
        <p className="mt-1 text-body text-muted">Generate a note on the Consultation page first.</p>
        <PillButton className="mt-4" onClick={() => navigate('/')}>
          Go to Consultation
        </PillButton>
      </Card>
    </div>
  )
}
