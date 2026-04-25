import { useEffect, useRef } from 'react'

interface Props {
  xy: number[][]
  width?: number
  height?: number
  dotPosition?: [number, number] | null
}

export function TrackCanvas({ xy, width = 400, height = 400, dotPosition = null }: Props) {
  const trackRef = useRef<HTMLCanvasElement>(null)
  const dotRef   = useRef<HTMLCanvasElement>(null)

  // Draw track outline once
  useEffect(() => {
    const canvas = trackRef.current
    if (!canvas || xy.length < 2) return
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, width, height)

    // Normalize xy to canvas size
    const xs = xy.map(p => p[0])
    const ys = xy.map(p => p[1])
    const xMin = Math.min(...xs), xMax = Math.max(...xs)
    const yMin = Math.min(...ys), yMax = Math.max(...ys)
    const scale = Math.min((width - 40) / (xMax - xMin || 1), (height - 40) / (yMax - yMin || 1))

    const toCanvas = (x: number, y: number) => [
      (x - xMin) * scale + 20,
      height - ((y - yMin) * scale + 20),
    ]

    ctx.strokeStyle = '#00BFFF'
    ctx.lineWidth = 2
    ctx.beginPath()
    const [sx, sy] = toCanvas(xs[0], ys[0])
    ctx.moveTo(sx, sy)
    for (let i = 1; i < xs.length; i++) {
      const [cx, cy] = toCanvas(xs[i], ys[i])
      ctx.lineTo(cx, cy)
    }
    ctx.closePath()
    ctx.stroke()

    // Store scale info on canvas for dot layer
    ;(canvas as any)._trackScale = { xMin, yMin, scale, width, height }
  }, [xy, width, height])

  // Draw animated dot
  useEffect(() => {
    const canvas = dotRef.current
    const trackCanvas = trackRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, width, height)
    if (!dotPosition || !(trackCanvas as any)?._trackScale) return

    const { xMin, yMin, scale } = (trackCanvas as any)._trackScale
    const [dx, dy] = [
      (dotPosition[0] - xMin) * scale + 20,
      height - ((dotPosition[1] - yMin) * scale + 20),
    ]
    ctx.fillStyle = '#FF8800'
    ctx.beginPath()
    ctx.arc(dx, dy, 5, 0, Math.PI * 2)
    ctx.fill()
  }, [dotPosition, width, height])

  return (
    <div style={{ position: 'relative', width, height }}>
      <canvas ref={trackRef} width={width} height={height} style={{ position: 'absolute', top: 0, left: 0 }} />
      <canvas ref={dotRef}   width={width} height={height} style={{ position: 'absolute', top: 0, left: 0 }} />
    </div>
  )
}
