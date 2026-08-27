import type { DispositionClass } from './types'

export function dispositionBadgeClass(disposition: DispositionClass): string {
  switch (disposition) {
    case 'manage_at_primary_care':
      return 'badge badge--manage'
    case 'refer_routine':
      return 'badge badge--routine'
    case 'refer_urgent_emergency':
      return 'badge badge--emergency'
  }
}

export function dispositionLabel(disposition: DispositionClass): string {
  switch (disposition) {
    case 'manage_at_primary_care':
      return 'Manage at primary care'
    case 'refer_routine':
      return 'Refer (routine)'
    case 'refer_urgent_emergency':
      return 'Refer (urgent/emergency)'
  }
}
