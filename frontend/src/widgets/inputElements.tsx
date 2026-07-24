// Reactive input-element widgets (ARCHITECTURE.md section 3a): slider,
// button, text_input. Each is a controlled component whose value comes
// from the server (via props, reduced from cell_output/element state
// upstream) and whose interactions send set_element_value over the
// websocket -- the server is always the source of truth; these never
// hold their own independent state beyond the pending edit itself.

export interface ElementWidgetProps<TValue> {
  elementId: string
  value: TValue
  onChange: (value: TValue) => void
}

export interface SliderConfig {
  min: number
  max: number
  step?: number
}

export function SliderWidget({
  elementId,
  value,
  onChange,
  config,
}: ElementWidgetProps<number> & { config: SliderConfig }) {
  return (
    <label className="cs-element cs-element-slider">
      <span className="cs-element-label">{elementId}</span>
      <input
        type="range"
        min={config.min}
        max={config.max}
        step={config.step ?? 1}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <span className="cs-element-value">{value}</span>
    </label>
  )
}

export function ButtonWidget({
  elementId,
  value,
  onChange,
  label,
}: ElementWidgetProps<number> & { label?: string }) {
  return (
    <button
      type="button"
      className="cs-element cs-element-button"
      onClick={() => onChange((value ?? 0) + 1)}
    >
      {label || elementId}
    </button>
  )
}

export function TextInputWidget({ elementId, value, onChange }: ElementWidgetProps<string>) {
  return (
    <label className="cs-element cs-element-text-input">
      <span className="cs-element-label">{elementId}</span>
      <input type="text" value={value ?? ''} onChange={(event) => onChange(event.target.value)} />
    </label>
  )
}
