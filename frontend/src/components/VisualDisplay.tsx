/**
 * VisualDisplay — renders exercise visual content from structured JSON.
 *
 * Supported types:
 *   table       → HTML table
 *   number_line → SVG number line with marked points
 *   bar_graph   → SVG bar chart
 *   pie_chart   → SVG pie chart
 *   geometry    → description + SVG placeholder with measurements
 *   page_image  → img served from /api/v1/textbooks/{id}/page/{page}
 */

interface TableData {
  type: 'table'; title?: string
  headers: string[]; rows: string[][]
}

interface NumberLineData {
  type: 'number_line'; min: number; max: number
  marked_points: { value: number; label?: string }[]
  arrows?: { from: number; to: number; label?: string }[]
}

interface BarGraphData {
  type: 'bar_graph'; title?: string; x_label?: string; y_label?: string
  bars: { label: string; value: number }[]
}

interface PieChartData {
  type: 'pie_chart'; title?: string
  slices: { label: string; value: number }[]
}

interface GeometryData {
  type: 'geometry'; shape?: string; description: string
  vertices?: Record<string, [number, number]> | null
  angles?: Record<string, string | null> | null
  circle_data?: {
    cx: number; cy: number; radius: number
    radius_label?: string | null; diameter_label?: string | null
  } | null
  measurements?: { label: string; value: string; type?: string }[]
}

interface PageImageData {
  type: 'page_image'; page: number; textbook_id: number; description?: string
}

type VisualData = TableData | NumberLineData | BarGraphData | PieChartData | GeometryData | PageImageData

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------
function TableVisual({ data }: { data: TableData }) {
  return (
    <div className="overflow-x-auto">
      {data.title && <p className="text-sm font-semibold text-gray-600 mb-2">{data.title}</p>}
      <table className="text-sm border-collapse w-full">
        <thead>
          <tr className="bg-primary-50">
            {data.headers.map((h, i) => (
              <th key={i} className="border border-gray-200 px-3 py-2 font-semibold text-gray-700 text-left">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, ri) => (
            <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              {row.map((cell, ci) => (
                <td key={ci} className="border border-gray-200 px-3 py-2 text-gray-700">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Number Line
// ---------------------------------------------------------------------------
function NumberLineVisual({ data }: { data: NumberLineData }) {
  const W = 500, H = 80
  const MARGIN = 40
  const range = data.max - data.min
  const toX = (v: number) => MARGIN + ((v - data.min) / range) * (W - 2 * MARGIN)

  const ticks: number[] = []
  const step = range <= 20 ? 1 : range <= 50 ? 5 : 10
  for (let v = data.min; v <= data.max; v += step) ticks.push(v)

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-lg">
      {/* Main line */}
      <line x1={MARGIN - 10} y1={H / 2} x2={W - MARGIN + 10} y2={H / 2} stroke="#374151" strokeWidth="2" />
      {/* Arrows */}
      <polygon points={`${W - MARGIN + 10},${H/2} ${W - MARGIN + 3},${H/2 - 4} ${W - MARGIN + 3},${H/2 + 4}`} fill="#374151" />
      <polygon points={`${MARGIN - 10},${H/2} ${MARGIN - 3},${H/2 - 4} ${MARGIN - 3},${H/2 + 4}`} fill="#374151" />
      {/* Ticks */}
      {ticks.map(v => (
        <g key={v}>
          <line x1={toX(v)} y1={H/2 - 5} x2={toX(v)} y2={H/2 + 5} stroke="#6b7280" strokeWidth="1" />
          <text x={toX(v)} y={H/2 + 18} textAnchor="middle" fontSize="10" fill="#6b7280">{v}</text>
        </g>
      ))}
      {/* Marked points */}
      {(data.marked_points || []).map((pt, i) => (
        <g key={i}>
          <circle cx={toX(pt.value)} cy={H/2} r="5" fill="#01696f" />
          {pt.label && (
            <text x={toX(pt.value)} y={H/2 - 12} textAnchor="middle" fontSize="11" fontWeight="bold" fill="#01696f">{pt.label}</text>
          )}
        </g>
      ))}
      {/* Arrows between points */}
      {(data.arrows || []).map((arr, i) => {
        const x1 = toX(arr.from), x2 = toX(arr.to), y = H / 2 - 15
        return (
          <g key={i}>
            <line x1={x1} y1={y} x2={x2} y2={y} stroke="#f59e0b" strokeWidth="2" markerEnd="url(#arrowhead)" />
            {arr.label && <text x={(x1 + x2) / 2} y={y - 8} textAnchor="middle" fontSize="9" fill="#f59e0b">{arr.label}</text>}
          </g>
        )
      })}
      <defs>
        <marker id="arrowhead" markerWidth="6" markerHeight="4" refX="3" refY="2" orient="auto">
          <polygon points="0 0, 6 2, 0 4" fill="#f59e0b" />
        </marker>
      </defs>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Bar Graph
// ---------------------------------------------------------------------------
function BarGraphVisual({ data }: { data: BarGraphData }) {
  const W = 400, H = 200
  const MARGIN = { top: 20, right: 20, bottom: 50, left: 45 }
  const chartW = W - MARGIN.left - MARGIN.right
  const chartH = H - MARGIN.top - MARGIN.bottom
  const maxVal = Math.max(...data.bars.map(b => b.value), 1)
  const barW = chartW / data.bars.length * 0.6
  const gap = chartW / data.bars.length

  const COLORS = ['#01696f', '#0891b2', '#7c3aed', '#d97706', '#dc2626', '#16a34a']

  return (
    <div>
      {data.title && <p className="text-sm font-semibold text-gray-600 mb-1 text-center">{data.title}</p>}
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-md">
        <g transform={`translate(${MARGIN.left}, ${MARGIN.top})`}>
          {/* Y axis */}
          <line x1={0} y1={0} x2={0} y2={chartH} stroke="#d1d5db" strokeWidth="1" />
          {[0, 0.25, 0.5, 0.75, 1].map(pct => {
            const y = chartH * (1 - pct)
            const val = Math.round(maxVal * pct)
            return (
              <g key={pct}>
                <line x1={-4} y1={y} x2={0} y2={y} stroke="#9ca3af" strokeWidth="1" />
                <text x={-8} y={y + 4} textAnchor="end" fontSize="9" fill="#6b7280">{val}</text>
                <line x1={0} y1={y} x2={chartW} y2={y} stroke="#f3f4f6" strokeWidth="1" />
              </g>
            )
          })}
          {/* X axis */}
          <line x1={0} y1={chartH} x2={chartW} y2={chartH} stroke="#d1d5db" strokeWidth="1" />
          {/* Bars */}
          {data.bars.map((bar, i) => {
            const bh = (bar.value / maxVal) * chartH
            const x = i * gap + (gap - barW) / 2
            return (
              <g key={i}>
                <rect x={x} y={chartH - bh} width={barW} height={bh} fill={COLORS[i % COLORS.length]} rx="3" />
                <text x={x + barW / 2} y={chartH + 14} textAnchor="middle" fontSize="9" fill="#6b7280">{bar.label}</text>
                <text x={x + barW / 2} y={chartH - bh - 4} textAnchor="middle" fontSize="9" fill="#374151">{bar.value}</text>
              </g>
            )
          })}
          {/* Axis labels */}
          {data.x_label && <text x={chartW / 2} y={chartH + 34} textAnchor="middle" fontSize="10" fill="#9ca3af">{data.x_label}</text>}
          {data.y_label && <text x={-32} y={chartH / 2} textAnchor="middle" fontSize="10" fill="#9ca3af" transform={`rotate(-90, -32, ${chartH/2})`}>{data.y_label}</text>}
        </g>
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Pie Chart
// ---------------------------------------------------------------------------
function PieChartVisual({ data }: { data: PieChartData }) {
  const COLORS = ['#01696f', '#0891b2', '#7c3aed', '#d97706', '#dc2626', '#16a34a']
  const total = data.slices.reduce((s, sl) => s + sl.value, 0)
  let angle = -Math.PI / 2
  const cx = 80, cy = 80, r = 65

  const sliceElems = data.slices.map((sl, i) => {
    const frac = sl.value / total
    const sweep = frac * 2 * Math.PI
    const x1 = cx + r * Math.cos(angle), y1 = cy + r * Math.sin(angle)
    const x2 = cx + r * Math.cos(angle + sweep), y2 = cy + r * Math.sin(angle + sweep)
    const midAngle = angle + sweep / 2
    const lx = cx + (r + 18) * Math.cos(midAngle), ly = cy + (r + 18) * Math.sin(midAngle)
    const large = sweep > Math.PI ? 1 : 0
    const path = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z`
    angle += sweep
    return { path, color: COLORS[i % COLORS.length], label: sl.label, lx, ly, pct: Math.round(frac * 100) }
  })

  return (
    <div>
      {data.title && <p className="text-sm font-semibold text-gray-600 mb-1 text-center">{data.title}</p>}
      <svg viewBox="0 0 220 180" className="w-full max-w-xs">
        {sliceElems.map((s, i) => (
          <g key={i}>
            <path d={s.path} fill={s.color} stroke="white" strokeWidth="2" />
          </g>
        ))}
        {/* Legend */}
        {data.slices.map((sl, i) => (
          <g key={i} transform={`translate(170, ${10 + i * 20})`}>
            <rect width="12" height="12" fill={COLORS[i % COLORS.length]} rx="2" />
            <text x="16" y="10" fontSize="9" fill="#374151">{sl.label} ({Math.round(sl.value/total*100)}%)</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Geometry SVG — full renderer
// ---------------------------------------------------------------------------
const GEO_STROKE = '#1e3a5f'
const GEO_FILL   = '#e8f4fd'
const GEO_ACCENT = '#01696f'
const GEO_LABEL  = '#374151'
const MEASURE_BG = 'white'

/** Midpoint between two points */
function mid(a: [number,number], b: [number,number]): [number,number] {
  return [(a[0]+b[0])/2, (a[1]+b[1])/2]
}

/** Distance between two points */
function dist(a: [number,number], b: [number,number]) {
  return Math.sqrt((b[0]-a[0])**2 + (b[1]-a[1])**2)
}

/** Unit vector from a to b */
function unit(a: [number,number], b: [number,number]): [number,number] {
  const d = dist(a, b) || 1
  return [(b[0]-a[0])/d, (b[1]-a[1])/d]
}

/** Measurement label pill at a given point */
function MeasureLabel({ x, y, text }: { x: number; y: number; text: string }) {
  const w = text.length * 6 + 10
  return (
    <g>
      <rect x={x - w/2} y={y - 10} width={w} height={18} rx="4" fill={MEASURE_BG} stroke="#d1d5db" strokeWidth="0.8" />
      <text x={x} y={y + 4} textAnchor="middle" fontSize="10" fill={GEO_LABEL} fontWeight="600">{text}</text>
    </g>
  )
}

/** Right-angle square mark at vertex B between rays BA and BC */
function RightAngleMark({ B, A, C }: { B: [number,number]; A: [number,number]; C: [number,number] }) {
  const size = 8
  const uBA = unit(B, A)
  const uBC = unit(B, C)
  const p1: [number,number] = [B[0] + uBA[0]*size, B[1] + uBA[1]*size]
  const p2: [number,number] = [p1[0] + uBC[0]*size, p1[1] + uBC[1]*size]
  const p3: [number,number] = [B[0] + uBC[0]*size, B[1] + uBC[1]*size]
  return <polyline points={`${p1[0]},${p1[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`}
    fill="none" stroke={GEO_STROKE} strokeWidth="1.2" />
}

/** Arc angle mark at vertex with label */
function AngleArc({ O, A, B, label }: { O: [number,number]; A: [number,number]; B: [number,number]; label: string }) {
  const r = 18
  const uA = unit(O, A)
  const uB = unit(O, B)
  const x1 = O[0] + uA[0]*r, y1 = O[1] + uA[1]*r
  const x2 = O[0] + uB[0]*r, y2 = O[1] + uB[1]*r
  // cross product to determine sweep
  const cross = uA[0]*uB[1] - uA[1]*uB[0]
  const sweep = cross > 0 ? 1 : 0
  const midUx = (uA[0] + uB[0]) / 2 || 0.1
  const midUy = (uA[1] + uB[1]) / 2 || 0.1
  const m = Math.sqrt(midUx**2 + midUy**2) || 1
  const lx = O[0] + (midUx/m) * (r + 14)
  const ly = O[1] + (midUy/m) * (r + 14)
  return (
    <g>
      <path d={`M${x1},${y1} A${r},${r} 0 0 ${sweep} ${x2},${y2}`}
        fill="none" stroke={GEO_ACCENT} strokeWidth="1.2" />
      <MeasureLabel x={lx} y={ly} text={label} />
    </g>
  )
}

function GeometryVisual({ data }: { data: GeometryData }) {
  const { shape, vertices, angles, circle_data, measurements, description } = data
  const V = vertices   // shorthand

  // ── CIRCLE ────────────────────────────────────────────────────────────────
  if (shape === 'circle' && circle_data) {
    const { cx, cy, radius, radius_label, diameter_label } = circle_data
    // Fit circle in 200×160 viewport
    const scale = Math.min(80 / radius, 1)
    const scx = 100, scy = 80, sr = radius * scale
    const rx2 = scx + sr, ry2 = scy
    return (
      <svg viewBox="0 0 200 160" className="w-full max-w-xs">
        <circle cx={scx} cy={scy} r={sr} fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" />
        {radius_label && <>
          <line x1={scx} y1={scy} x2={rx2} y2={ry2} stroke={GEO_ACCENT} strokeWidth="1.5" strokeDasharray="3 2" />
          <MeasureLabel x={(scx+rx2)/2} y={scy - 10} text={radius_label} />
        </>}
        {diameter_label && <>
          <line x1={scx - sr} y1={scy} x2={scx + sr} y2={scy} stroke={GEO_ACCENT} strokeWidth="1.5" strokeDasharray="3 2" />
          <MeasureLabel x={scx} y={scy + sr + 14} text={diameter_label} />
        </>}
        {/* Centre dot */}
        <circle cx={scx} cy={scy} r="2.5" fill={GEO_STROKE} />
      </svg>
    )
  }

  // ── POLYGON / TRIANGLE / RECTANGLE / ANGLE (need vertices) ────────────────
  if (V && Object.keys(V).length >= 2) {
    const keys = Object.keys(V)
    const pts = keys.map(k => V[k])
    const polyPoints = pts.map(p => `${p[0]},${p[1]}`).join(' ')

    // Lookup measurements by label for side labels
    const measureMap: Record<string, string> = {}
    ;(measurements || []).forEach(m => { measureMap[m.label] = m.value })

    // Determine which vertex has the right angle (for right_triangle)
    const rightAngleVertex = shape === 'right_triangle'
      ? (keys.find(k => angles?.[k] === '90°') ?? keys[1])
      : null

    return (
      <svg viewBox="0 0 200 160" className="w-full max-w-xs">
        {/* Shape fill */}
        <polygon points={polyPoints} fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" strokeLinejoin="round" />

        {/* Right angle mark */}
        {rightAngleVertex && (() => {
          const idx = keys.indexOf(rightAngleVertex)
          const prev = keys[(idx - 1 + keys.length) % keys.length]
          const next = keys[(idx + 1) % keys.length]
          return <RightAngleMark B={V[rightAngleVertex]} A={V[prev]} C={V[next]} />
        })()}

        {/* Vertex labels */}
        {keys.map(k => {
          const [x, y] = V[k]
          // Nudge label away from centroid
          const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length
          const cy2 = pts.reduce((s, p) => s + p[1], 0) / pts.length
          const dx = x - cx, dy = y - cy2
          const len = Math.sqrt(dx*dx + dy*dy) || 1
          const nx = x + (dx/len)*12, ny = y + (dy/len)*12
          return (
            <text key={k} x={nx} y={ny} textAnchor="middle" dominantBaseline="central"
              fontSize="11" fontWeight="700" fill={GEO_STROKE}>{k}</text>
          )
        })}

        {/* Side measurement labels at edge midpoints */}
        {keys.map((k, i) => {
          const next = keys[(i + 1) % keys.length]
          const edgeLabel = `${k}${next}`
          const label = measureMap[edgeLabel] || measureMap[`${next}${k}`]
          if (!label) return null
          const [mx, my] = mid(V[k], V[next])
          // Offset label slightly outward from polygon centre
          const cx = pts.reduce((s, p) => s + p[0], 0) / pts.length
          const cy2 = pts.reduce((s, p) => s + p[1], 0) / pts.length
          const dx = mx - cx, dy = my - cy2
          const len = Math.sqrt(dx*dx + dy*dy) || 1
          const ox = mx + (dx/len)*14, oy = my + (dy/len)*14
          return <MeasureLabel key={edgeLabel} x={ox} y={oy} text={label} />
        })}

        {/* Angle arcs */}
        {keys.map((k, i) => {
          const angleLabel = angles?.[k]
          if (!angleLabel || angleLabel === '90°') return null
          const prev = keys[(i - 1 + keys.length) % keys.length]
          const next = keys[(i + 1) % keys.length]
          return <AngleArc key={k} O={V[k]} A={V[prev]} B={V[next]} label={angleLabel} />
        })}
      </svg>
    )
  }

  // ── FALLBACK: text description + measurement chips ─────────────────────────
  return (
    <div className="bg-blue-50 rounded-xl p-4 border border-blue-100">
      <p className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-2">Figure</p>
      <p className="text-sm text-gray-700 leading-relaxed">{description}</p>
      {measurements && measurements.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {measurements.map((m, i) => (
            <span key={i} className="bg-white border border-blue-200 text-blue-700 text-xs px-2 py-1 rounded-lg font-mono">
              {m.label} = {m.value}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page Image (served from backend)
// ---------------------------------------------------------------------------
function PageImageVisual({ data }: { data: PageImageData }) {
  const src = `/api/v1/textbooks/${data.textbook_id}/page/${data.page}`
  return (
    <div className="rounded-xl overflow-hidden border border-gray-200 bg-gray-50">
      {data.description && <p className="text-xs text-gray-500 px-3 py-1.5 border-b border-gray-100">{data.description}</p>}
      <img src={src} alt="Figure from textbook" className="w-full object-contain max-h-96" loading="lazy" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------
interface Props {
  visualData: string | object | null
  visualType?: string | null
}

export default function VisualDisplay({ visualData, visualType }: Props) {
  if (!visualData) return null

  let data: VisualData
  try {
    data = typeof visualData === 'string' ? JSON.parse(visualData) : visualData as VisualData
  } catch {
    return null
  }

  const type = data.type || visualType

  return (
    <div className="my-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
      <p className="text-xs text-gray-400 uppercase tracking-wide font-medium mb-2">Figure</p>
      {type === 'table' && <TableVisual data={data as TableData} />}
      {type === 'number_line' && <NumberLineVisual data={data as NumberLineData} />}
      {type === 'bar_graph' && <BarGraphVisual data={data as BarGraphData} />}
      {type === 'pie_chart' && <PieChartVisual data={data as PieChartData} />}
      {type === 'geometry' && <GeometryVisual data={data as GeometryData} />}
      {type === 'page_image' && <PageImageVisual data={data as PageImageData} />}
    </div>
  )
}
