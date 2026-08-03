import type { ReactNode } from 'react'
import { ButtonWidget, SliderWidget, TextInputWidget } from './inputElements'
import type { ElementMeta } from './elementMeta'

export interface ElementWidgetDispatchProps {
  element: ElementMeta
  value: unknown
  onSetValue: (elementId: string, value: unknown) => void
  /** Omitted by Cell.tsx's tabbed layout (TODO.md #56) -- once only one
   * element renders at a time via tab selection, a per-element minimize
   * toggle has nothing left to save space for. Kept optional rather than
   * removed outright so any other future caller stacking multiple
   * elements at once can still opt back in. */
  onToggleMinimize?: () => void
}

// Dispatches an element's (kind, config) to the matching input widget
// component (ARCHITECTURE.md section 3a: only input elements render here
// -- viewer elements are ViewerElementWidget.tsx). Unknown/unsupported
// kinds render nothing rather than crashing the whole cell's UI. Wraps
// whichever widget renders with a minimize toggle (ARCHITECTURE.md
// section 8) common to every element kind, so individual widgets don't
// each need their own copy of that control.
export function ElementWidget({ element, value, onSetValue, onToggleMinimize }: ElementWidgetDispatchProps) {
  const handleChange = (next: unknown) => onSetValue(element.name, next)

  let widget: ReactNode
  switch (element.kind) {
    case 'slider':
      widget = (
        <SliderWidget
          elementId={element.name}
          value={typeof value === 'number' ? value : Number(element.config.default ?? 0)}
          onChange={handleChange}
          config={{
            min: Number(element.config.min ?? 0),
            max: Number(element.config.max ?? 100),
          }}
        />
      )
      break
    case 'button':
      widget = (
        <ButtonWidget
          elementId={element.name}
          value={typeof value === 'number' ? value : 0}
          onChange={handleChange}
          label={typeof element.config.label === 'string' ? element.config.label : undefined}
        />
      )
      break
    case 'text_input':
      widget = (
        <TextInputWidget
          elementId={element.name}
          value={typeof value === 'string' ? value : String(element.config.default ?? '')}
          onChange={handleChange}
        />
      )
      break
    default:
      return null
  }

  return (
    <div className="cs-element-wrapper">
      {widget}
      {onToggleMinimize && (
        <button
          type="button"
          className="cs-minimize-toggle"
          onClick={onToggleMinimize}
          aria-label={`Minimize ${element.name}`}
        >
          {'▾'}
        </button>
      )}
    </div>
  )
}
