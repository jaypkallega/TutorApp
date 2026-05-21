import { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from 'react'
import { Trash2, Undo2 } from 'lucide-react'

export interface Stroke {
  points: { x: number; y: number; pressure?: number }[]
  color: string
  width: number
}
export interface CanvasData { strokes: Stroke[] }
export interface StylusCanvasHandle {
  getCanvasData: () => CanvasData
  getImageDataURL: () => string
  clear: () => void
}

interface Props {
  width?: number; height?: number
  strokeColor?: string; strokeWidth?: number
  onStrokeEnd?: () => void
  initialStrokes?: Stroke[]  // Fix 5: restore saved strokes when navigating back
}

const StylusCanvas = forwardRef<StylusCanvasHandle, Props>(
  ({ width = 900, height = 320, strokeColor = '#1a1a1a', strokeWidth = 3, onStrokeEnd, initialStrokes }, ref) => {
    const canvasRef = useRef<HTMLCanvasElement>(null)
    const [strokes, setStrokes] = useState<Stroke[]>(initialStrokes || [])
    const currentStroke = useRef<Stroke | null>(null)
    const isDrawing = useRef(false)

    useImperativeHandle(ref, () => ({
      getCanvasData: () => ({ strokes }),
      getImageDataURL: () => canvasRef.current?.toDataURL('image/png') ?? '',
      clear: () => { setStrokes([]); clearCanvas() },
    }))

    const clearCanvas = useCallback(() => {
      const ctx = canvasRef.current?.getContext('2d')
      if (!ctx) return
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, width, height)
    }, [width, height])

    const redraw = useCallback((allStrokes: Stroke[]) => {
      const ctx = canvasRef.current?.getContext('2d')
      if (!ctx) return
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, width, height)
      allStrokes.forEach((stroke) => {
        if (!stroke.points.length) return
        ctx.beginPath()
        ctx.strokeStyle = stroke.color
        ctx.lineWidth = stroke.width
        ctx.lineCap = 'round'
        ctx.lineJoin = 'round'
        if (stroke.points.length === 1) {
          const p = stroke.points[0]
          ctx.arc(p.x, p.y, stroke.width / 2, 0, Math.PI * 2)
          ctx.fillStyle = stroke.color
          ctx.fill()
        } else {
          ctx.moveTo(stroke.points[0].x, stroke.points[0].y)
          stroke.points.slice(1).forEach((pt) => ctx.lineTo(pt.x, pt.y))
          ctx.stroke()
        }
      })
    }, [width, height])

    // On mount: draw initial strokes (component is keyed per question so this always fires for new question)
    useEffect(() => {
      if (initialStrokes && initialStrokes.length > 0) {
        redraw(initialStrokes)
      } else {
        clearCanvas()
      }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    const getPos = (e: React.PointerEvent<HTMLCanvasElement>) => {
      const rect = e.currentTarget.getBoundingClientRect()
      const scaleX = e.currentTarget.width / rect.width
      const scaleY = e.currentTarget.height / rect.height
      return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY, pressure: e.pressure ?? 0.5 }
    }

    const onPointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
      if (e.pointerType === 'touch' && (e as any).width > 30) return  // palm rejection
      e.currentTarget.setPointerCapture(e.pointerId)
      isDrawing.current = true
      const pos = getPos(e)
      currentStroke.current = { points: [pos], color: strokeColor, width: strokeWidth * (0.5 + pos.pressure) }
    }

    const onPointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
      if (!isDrawing.current || !currentStroke.current) return
      const pos = getPos(e)
      currentStroke.current.points.push(pos)
      const ctx = e.currentTarget.getContext('2d')
      if (!ctx) return
      const pts = currentStroke.current.points
      if (pts.length < 2) return
      ctx.beginPath()
      ctx.strokeStyle = currentStroke.current.color
      ctx.lineWidth = currentStroke.current.width
      ctx.lineCap = 'round'; ctx.lineJoin = 'round'
      ctx.moveTo(pts[pts.length - 2].x, pts[pts.length - 2].y)
      ctx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y)
      ctx.stroke()
    }

    const onPointerUp = () => {
      if (!isDrawing.current || !currentStroke.current) return
      isDrawing.current = false
      if (currentStroke.current.points.length > 0) {
        const newStrokes = [...strokes, currentStroke.current]
        setStrokes(newStrokes)
        onStrokeEnd?.()
      }
      currentStroke.current = null
    }

    const undo = () => { const s = strokes.slice(0, -1); setStrokes(s); redraw(s) }
    const clear = () => { setStrokes([]); clearCanvas() }

    return (
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <button onClick={undo} disabled={strokes.length === 0}
            className="flex items-center gap-1 px-3 py-2 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-40 text-sm font-medium">
            <Undo2 size={16} /> Undo
          </button>
          <button onClick={clear} disabled={strokes.length === 0}
            className="flex items-center gap-1 px-3 py-2 rounded-lg bg-red-50 hover:bg-red-100 text-red-600 disabled:opacity-40 text-sm font-medium">
            <Trash2 size={16} /> Clear
          </button>
        </div>
        <div className="relative rounded-xl overflow-hidden border-2 border-gray-200 touch-none">
          <canvas ref={canvasRef} width={width} height={height}
            className="w-full bg-white cursor-crosshair" style={{ touchAction: 'none' }}
            onPointerDown={onPointerDown} onPointerMove={onPointerMove}
            onPointerUp={onPointerUp} onPointerLeave={onPointerUp} />
          {strokes.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <p className="text-gray-300 text-sm">✏️ Draw or write here — Apple Pencil supported</p>
            </div>
          )}
        </div>
      </div>
    )
  }
)
StylusCanvas.displayName = 'StylusCanvas'
export default StylusCanvas
