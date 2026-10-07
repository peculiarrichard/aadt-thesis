import type { DispositionClass } from './types'

export function dispositionBadgeClass(disposition: DispositionClass): string {
  switch (disposition) {
    case 'self_care_advice':
      return 'badge badge--manage'
    case 'scheduled_appointment':
      return 'badge badge--routine'
    case 'urgent_referral':
      return 'badge badge--emergency'
  }
}

export function dispositionLabel(disposition: DispositionClass): string {
  switch (disposition) {
    case 'self_care_advice':
      return 'Self-care advice'
    case 'scheduled_appointment':
      return 'Scheduled appointment'
    case 'urgent_referral':
      return 'Urgent referral'
  }
}
