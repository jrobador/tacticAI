import * as SliderPrimitive from '@radix-ui/react-slider'

interface Props { value: number; min: number; max: number; step: number; onChange: (v: number) => void; label: string }
export function Slider({ value, min, max, step, onChange, label }: Props) {
  return (
    <SliderPrimitive.Root className="relative flex h-5 w-full touch-none items-center select-none" value={[value]} min={min} max={max} step={step} onValueChange={([v]) => onChange(v)}>
      <SliderPrimitive.Track className="relative h-1.5 grow rounded-full bg-muted">
        <SliderPrimitive.Range className="absolute h-full rounded-full bg-primary" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb aria-label={label} className="block size-4 rounded-full border-2 border-primary bg-background" />
    </SliderPrimitive.Root>
  )
}
