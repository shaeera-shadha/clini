import { Card } from '../components/ui/primitives'

/** Holds the route for a page that is built in the next phase, and says so plainly. */
export function NextPhasePage({ description }: { description: string }) {
  return (
    <div className="p-6">
      <Card>
        <p className="text-body text-muted">{description}</p>
      </Card>
    </div>
  )
}
