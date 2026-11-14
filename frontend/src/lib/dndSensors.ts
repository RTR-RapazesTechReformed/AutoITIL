import type { PointerEvent as ReactPointerEvent } from 'react'
import {
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type PointerSensorOptions,
} from '@dnd-kit/core'

/** PointerSensor que ignora toque — mouse e caneta continuam arrastando
 *  na hora, como sempre. O toque fica com o TouchSensor (abaixo), que
 *  exige segurar o dedo antes de arrastar. */
class MousePointerSensor extends PointerSensor {
  static activators = [
    {
      eventName: 'onPointerDown' as const,
      handler: (
        { nativeEvent: event }: ReactPointerEvent,
        { onActivation }: PointerSensorOptions,
      ) => {
        if (!event.isPrimary || event.button !== 0 || event.pointerType === 'touch') return false
        onActivation?.({ event })
        return true
      },
    },
  ]
}

/** Sensores de drag do Kanban.
 *
 *  O padrão do dnd-kit (PointerSensor sem restrição) começa o arraste no
 *  primeiro pointerdown. Com o dedo isso disputa com a rolagem: ou o
 *  navegador rola e cancela o ponteiro (o card nunca arrasta), ou o card
 *  agarra todo toque e a lista não rola mais. Em telas de toque o gesto
 *  vira "tocar e segurar": 250ms parado inicia o arraste; mexer o dedo
 *  antes disso (mais que 8px) é rolagem normal. */
export function useKanbanSensors() {
  return useSensors(
    useSensor(MousePointerSensor),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 8 } }),
    useSensor(KeyboardSensor),
  )
}
