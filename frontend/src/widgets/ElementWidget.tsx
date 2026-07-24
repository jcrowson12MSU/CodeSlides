import { ButtonWidget, SliderWidget, TextInputWidget } from './inputElements'
import type { ElementMeta } from './elementMeta'

export interface ElementWidgetDispatchProps {
  element: ElementMeta
  value: unknown
  onSetValue: (elementId: string, value: unknown) => void
}

// Dispatches an element's (kind, config) to the matching input widget
// component (ARCHITECTURE.md section 3a: only input elements render here
// -- viewer elements are TODO.md #16). Unknown/unsupported kinds render
// nothing rather than crashing the whole cell's UI.
export function ElementWidget({ element, value, onSetValue }: ElementWidgetDispatchProps) {
  const handleChange = (next: unknown) => onSetValue(element.name, next)

  switch (element.kind) {
    case 'slider':
      return (
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
    case 'button':
      return (
        <ButtonWidget
          elementId={element.name}
          value={typeof value === 'number' ? value : 0}
          onChange={handleChange}
          label={typeof element.config.label === 'string' ? element.config.label : undefined}
        />
      )
    case 'text_input':
      return (
        <TextInputWidget
          elementId={element.name}
          value={typeof value === 'string' ? value : String(element.config.default ?? '')}
          onChange={handleChange}
        />
      )
    default:
      return null
  }
}
