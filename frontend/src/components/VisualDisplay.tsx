/**
 * VisualDisplay — renders exercise visual content from structured JSON.
 *
 * Supported types:
 *   table       → HTML table
 *   number_line → SVG number line with marked points
 *   bar_graph   → SVG bar chart
 *   pie_chart   → SVG pie chart
 *   geometry    → SVG shape renderer (triangle, rectangle, circle, angle,
 *                  polygon, compound, cube_net)
 *   axes        → SVG coordinate grid with points / segments / polygon  [R-C]
 *   page_image  → img served from /api/v1/textbooks/{id}/page/{page}
 */

// ── Data interfaces ─────────────────────────────────────────────────────────

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
  // cube_net specific
  net_cells?: [number, number][] | null
  cell_labels?: Record<string, string>
  // 3-D shape outputs from geometry engine
  cylinder_data?: {
    cx: number; cy_top: number; cy_bottom: number
    rx: number; ry: number
    radius_label?: string | null; height_label?: string | null
  } | null
  cone_data?: {
    cx: number; apex_y: number; base_cy: number
    rx: number; ry: number
    radius_label?: string | null; height_label?: string | null; slant_label?: string | null
  } | null
  cuboid_data?: {
    front: [number, number][]
    top:   [number, number][]
    right: [number, number][]
    labels:    { length?: string; width?: string; height?: string }
    label_pos: { length?: [number, number]; width?: [number, number]; height?: [number, number] }
  } | null
}

/** R-C: coordinate plane with points, segments, shaded polygon */
interface AxesData {
  type: 'axes'
  x_min: number; x_max: number
  y_min: number; y_max: number
  points?: { x: number; y: number; label?: string }[]
  segments?: { from: [number, number]; to: [number, number]; label?: string; dashed?: boolean }[]
  polygon_points?: [number, number][] | null
  description?: string
}

interface PageImageData {
  type: 'page_image'; page: number; textbook_id: number; description?: string
}

interface MCQOption {
  label: string
  visual: object
}

interface MCQOptionsData {
  type: 'mcq_options'
  options: MCQOption[]
  correct_option?: string
}

type VisualData = TableData | NumberLineData | BarGraphData | PieChartData
                | GeometryData | AxesData | PageImageData | MCQOptionsData

// ── Shared colours ───────────────────────────────────────────────────────────
const GEO_STROKE  = '#1e3a5f'
const GEO_FILL    = '#e8f4fd'
const GEO_ACCENT  = '#01696f'
const GEO_LABEL   = '#374151'
const MEASURE_BG  = 'white'
const PALETTE     = ['#01696f','#0891b2','#7c3aed','#d97706','#dc2626','#16a34a']

// ── Tiny geometry helpers ─────────────────────────────────────────────────────
function mid(a: [number,number], b: [number,number]): [number,number] {
  return [(a[0]+b[0])/2, (a[1]+b[1])/2]
}
function dist(a: [number,number], b: [number,number]) {
  return Math.sqrt((b[0]-a[0])**2 + (b[1]-a[1])**2)
}
function unit(a: [number,number], b: [number,number]): [number,number] {
  const d = dist(a, b) || 1
  return [(b[0]-a[0])/d, (b[1]-a[1])/d]
}

// ── Shared sub-components ─────────────────────────────────────────────────────

function MeasureLabel({ x, y, text }: { x: number; y: number; text: string }) {
  const w = text.length * 6 + 10
  return (
    <g>
      <rect x={x - w/2} y={y - 10} width={w} height={18} rx="4" fill={MEASURE_BG} stroke="#d1d5db" strokeWidth="0.8" />
      <text x={x} y={y + 4} textAnchor="middle" fontSize="10" fill={GEO_LABEL} fontWeight="600">{text}</text>
    </g>
  )
}

function RightAngleMark({ B, A, C }: { B: [number,number]; A: [number,number]; C: [number,number] }) {
  const size = 8
  const uBA = unit(B, A), uBC = unit(B, C)
  const p1: [number,number] = [B[0]+uBA[0]*size, B[1]+uBA[1]*size]
  const p2: [number,number] = [p1[0]+uBC[0]*size, p1[1]+uBC[1]*size]
  const p3: [number,number] = [B[0]+uBC[0]*size, B[1]+uBC[1]*size]
  return <polyline points={`${p1[0]},${p1[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`}
    fill="none" stroke={GEO_STROKE} strokeWidth="1.2" />
}

function AngleArc({ O, A, B, label }: { O: [number,number]; A: [number,number]; B: [number,number]; label: string }) {
  const r = 18
  const uA = unit(O, A), uB = unit(O, B)
  const x1 = O[0]+uA[0]*r, y1 = O[1]+uA[1]*r
  const x2 = O[0]+uB[0]*r, y2 = O[1]+uB[1]*r
  const cross = uA[0]*uB[1] - uA[1]*uB[0]
  const sweep = cross > 0 ? 1 : 0
  const midUx = (uA[0]+uB[0])/2 || 0.1, midUy = (uA[1]+uB[1])/2 || 0.1
  const m = Math.sqrt(midUx**2 + midUy**2) || 1
  const lx = O[0]+(midUx/m)*(r+14), ly = O[1]+(midUy/m)*(r+14)
  return (
    <g>
      <path d={`M${x1},${y1} A${r},${r} 0 0 ${sweep} ${x2},${y2}`}
        fill="none" stroke={GEO_ACCENT} strokeWidth="1.2" />
      <MeasureLabel x={lx} y={ly} text={label} />
    </g>
  )
}

// ── TABLE ────────────────────────────────────────────────────────────────────
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

// ── NUMBER LINE ──────────────────────────────────────────────────────────────
function NumberLineVisual({ data }: { data: NumberLineData }) {
  const W = 500, H = 80, MARGIN = 40
  const range = data.max - data.min
  const toX = (v: number) => MARGIN + ((v - data.min) / range) * (W - 2 * MARGIN)
  const ticks: number[] = []
  const step = range <= 20 ? 1 : range <= 50 ? 5 : 10
  for (let v = data.min; v <= data.max; v += step) ticks.push(v)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-lg">
      <line x1={MARGIN-10} y1={H/2} x2={W-MARGIN+10} y2={H/2} stroke="#374151" strokeWidth="2" />
      <polygon points={`${W-MARGIN+10},${H/2} ${W-MARGIN+3},${H/2-4} ${W-MARGIN+3},${H/2+4}`} fill="#374151" />
      <polygon points={`${MARGIN-10},${H/2} ${MARGIN-3},${H/2-4} ${MARGIN-3},${H/2+4}`} fill="#374151" />
      {ticks.map(v => (
        <g key={v}>
          <line x1={toX(v)} y1={H/2-5} x2={toX(v)} y2={H/2+5} stroke="#6b7280" strokeWidth="1" />
          <text x={toX(v)} y={H/2+18} textAnchor="middle" fontSize="10" fill="#6b7280">{v}</text>
        </g>
      ))}
      {(data.marked_points || []).map((pt, i) => (
        <g key={i}>
          <circle cx={toX(pt.value)} cy={H/2} r="5" fill="#01696f" />
          {pt.label && <text x={toX(pt.value)} y={H/2-12} textAnchor="middle" fontSize="11" fontWeight="bold" fill="#01696f">{pt.label}</text>}
        </g>
      ))}
      {(data.arrows || []).map((arr, i) => {
        const x1 = toX(arr.from), x2 = toX(arr.to), y = H/2-15
        return (
          <g key={i}>
            <line x1={x1} y1={y} x2={x2} y2={y} stroke="#f59e0b" strokeWidth="2" markerEnd="url(#arrowhead)" />
            {arr.label && <text x={(x1+x2)/2} y={y-8} textAnchor="middle" fontSize="9" fill="#f59e0b">{arr.label}</text>}
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

// ── BAR GRAPH ────────────────────────────────────────────────────────────────
function BarGraphVisual({ data }: { data: BarGraphData }) {
  const W = 400, H = 200
  const M = { top: 20, right: 20, bottom: 50, left: 45 }
  const cW = W - M.left - M.right, cH = H - M.top - M.bottom
  const maxVal = Math.max(...data.bars.map(b => b.value), 1)
  const barW = cW / data.bars.length * 0.6
  const gap  = cW / data.bars.length
  return (
    <div>
      {data.title && <p className="text-sm font-semibold text-gray-600 mb-1 text-center">{data.title}</p>}
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-md">
        <g transform={`translate(${M.left},${M.top})`}>
          <line x1={0} y1={0} x2={0} y2={cH} stroke="#d1d5db" strokeWidth="1" />
          {[0,0.25,0.5,0.75,1].map(pct => {
            const y = cH*(1-pct); const val = Math.round(maxVal*pct)
            return <g key={pct}>
              <line x1={-4} y1={y} x2={0} y2={y} stroke="#9ca3af" strokeWidth="1" />
              <text x={-8} y={y+4} textAnchor="end" fontSize="9" fill="#6b7280">{val}</text>
              <line x1={0} y1={y} x2={cW} y2={y} stroke="#f3f4f6" strokeWidth="1" />
            </g>
          })}
          <line x1={0} y1={cH} x2={cW} y2={cH} stroke="#d1d5db" strokeWidth="1" />
          {data.bars.map((bar, i) => {
            const bh = (bar.value/maxVal)*cH; const x = i*gap+(gap-barW)/2
            return <g key={i}>
              <rect x={x} y={cH-bh} width={barW} height={bh} fill={PALETTE[i%PALETTE.length]} rx="3" />
              <text x={x+barW/2} y={cH+14} textAnchor="middle" fontSize="9" fill="#6b7280">{bar.label}</text>
              <text x={x+barW/2} y={cH-bh-4} textAnchor="middle" fontSize="9" fill="#374151">{bar.value}</text>
            </g>
          })}
          {data.x_label && <text x={cW/2} y={cH+34} textAnchor="middle" fontSize="10" fill="#9ca3af">{data.x_label}</text>}
          {data.y_label && <text x={-32} y={cH/2} textAnchor="middle" fontSize="10" fill="#9ca3af" transform={`rotate(-90,-32,${cH/2})`}>{data.y_label}</text>}
        </g>
      </svg>
    </div>
  )
}

// ── PIE CHART ────────────────────────────────────────────────────────────────
function PieChartVisual({ data }: { data: PieChartData }) {
  const total = data.slices.reduce((s, sl) => s + sl.value, 0)
  let angle = -Math.PI / 2
  const cx = 80, cy = 80, r = 65
  const slices = data.slices.map((sl, i) => {
    const sweep = (sl.value/total) * 2 * Math.PI
    const x1 = cx+r*Math.cos(angle), y1 = cy+r*Math.sin(angle)
    const x2 = cx+r*Math.cos(angle+sweep), y2 = cy+r*Math.sin(angle+sweep)
    const large = sweep > Math.PI ? 1 : 0
    const path = `M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z`
    angle += sweep
    return { path, color: PALETTE[i%PALETTE.length], label: sl.label, value: sl.value }
  })
  return (
    <div>
      {data.title && <p className="text-sm font-semibold text-gray-600 mb-1 text-center">{data.title}</p>}
      <svg viewBox="0 0 220 180" className="w-full max-w-xs">
        {slices.map((s, i) => <path key={i} d={s.path} fill={s.color} stroke="white" strokeWidth="2" />)}
        {data.slices.map((sl, i) => (
          <g key={i} transform={`translate(170,${10+i*20})`}>
            <rect width="12" height="12" fill={PALETTE[i%PALETTE.length]} rx="2" />
            <text x="16" y="10" fontSize="9" fill="#374151">{sl.label} ({Math.round(sl.value/total*100)}%)</text>
          </g>
        ))}
      </svg>
    </div>
  )
}

// ── CUBE NET (R-B) ────────────────────────────────────────────────────────────
/**
 * Renders a net of a cube as a grid of squares.
 * data.net_cells: [[row, col], ...] — positions of the 6 square faces.
 * data.cell_labels: { "row,col": "face name" } — optional face labels.
 */
function CubeNetVisual({ data }: { data: GeometryData }) {
  const cells: [number, number][] = data.net_cells ?? []
  const cellLabels: Record<string, string> = data.cell_labels ?? {}

  // Fallback: standard cross-shaped net if no cells provided
  const effectiveCells: [number, number][] = cells.length === 6
    ? cells
    : [[0,1],[1,0],[1,1],[1,2],[1,3],[2,1]]

  const CELL = 38
  const rows = effectiveCells.map(c => c[0])
  const cols = effectiveCells.map(c => c[1])
  const minR = Math.min(...rows), minC = Math.min(...cols)
  const maxR = Math.max(...rows), maxC = Math.max(...cols)
  const gridW = (maxC - minC + 1) * CELL
  const gridH = (maxR - minR + 1) * CELL
  const viewW = gridW + 36, viewH = gridH + 36
  const offX = 18, offY = 18

  // Fold direction arrows on each outer edge (cosmetic affordance)
  return (
    <div>
      <svg viewBox={`0 0 ${viewW} ${viewH}`} className="w-full max-w-xs">
        {/* Ghost grid for context */}
        {effectiveCells.map(([r, c], i) => {
          const x = (c - minC) * CELL + offX
          const y = (r - minR) * CELL + offY
          const key = `${r},${c}`
          const label = cellLabels[key]
          return (
            <g key={i}>
              <rect x={x} y={y} width={CELL} height={CELL}
                fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="1.8" rx="2" />
              {label && (
                <text x={x + CELL/2} y={y + CELL/2}
                  textAnchor="middle" dominantBaseline="central"
                  fontSize="8" fill={GEO_LABEL} fontWeight="700">
                  {label}
                </text>
              )}
            </g>
          )
        })}
        {/* Dashed fold lines between adjacent cells */}
        {effectiveCells.map(([r, c]) => {
          const lines: JSX.Element[] = []
          const x = (c - minC) * CELL + offX
          const y = (r - minR) * CELL + offY
          // Check right neighbour
          if (effectiveCells.some(([nr, nc]) => nr === r && nc === c + 1)) {
            lines.push(
              <line key={`${r},${c}-r`}
                x1={x + CELL} y1={y + 4} x2={x + CELL} y2={y + CELL - 4}
                stroke={GEO_ACCENT} strokeWidth="1" strokeDasharray="3 2" opacity="0.6" />
            )
          }
          // Check bottom neighbour
          if (effectiveCells.some(([nr, nc]) => nr === r + 1 && nc === c)) {
            lines.push(
              <line key={`${r},${c}-b`}
                x1={x + 4} y1={y + CELL} x2={x + CELL - 4} y2={y + CELL}
                stroke={GEO_ACCENT} strokeWidth="1" strokeDasharray="3 2" opacity="0.6" />
            )
          }
          return lines
        })}
      </svg>
      {/* Legend if no labels */}
      {Object.keys(cellLabels).length === 0 && (
        <p className="text-xs text-gray-400 mt-1 text-center">
          Dashed lines = fold edges
        </p>
      )}
    </div>
  )
}

// ── CYLINDER (Gap-3) ──────────────────────────────────────────────────────────
function CylinderVisual({ data }: { data: GeometryData }) {
  const c = data.cylinder_data!
  const { cx, cy_top, cy_bottom, rx, ry, radius_label, height_label } = c
  return (
    <svg viewBox="0 0 200 160" className="w-full max-w-xs">
      {/* Body fill between ellipses */}
      <rect x={cx - rx} y={cy_top} width={2 * rx} height={cy_bottom - cy_top}
        fill={GEO_FILL} stroke="none" />
      {/* Bottom ellipse */}
      <ellipse cx={cx} cy={cy_bottom} rx={rx} ry={ry}
        fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" />
      {/* Left and right vertical lines */}
      <line x1={cx - rx} y1={cy_bottom} x2={cx - rx} y2={cy_top}
        stroke={GEO_STROKE} strokeWidth="2" />
      <line x1={cx + rx} y1={cy_bottom} x2={cx + rx} y2={cy_top}
        stroke={GEO_STROKE} strokeWidth="2" />
      {/* Top ellipse — drawn last so it covers the body rect edge */}
      <ellipse cx={cx} cy={cy_top} rx={rx} ry={ry}
        fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" />
      {/* Radius line on top face */}
      {radius_label && <>
        <line x1={cx} y1={cy_top} x2={cx + rx} y2={cy_top}
          stroke={GEO_ACCENT} strokeWidth="1.5" strokeDasharray="4 2" />
        <MeasureLabel x={(cx + cx + rx) / 2} y={cy_top - 12} text={radius_label} />
      </>}
      {/* Height indicator on the right side */}
      {height_label && <>
        <line x1={cx + rx + 10} y1={cy_top}    x2={cx + rx + 10} y2={cy_bottom}
          stroke={GEO_ACCENT} strokeWidth="1.5" />
        <line x1={cx + rx + 6}  y1={cy_top}    x2={cx + rx + 14} y2={cy_top}
          stroke={GEO_ACCENT} strokeWidth="1.5" />
        <line x1={cx + rx + 6}  y1={cy_bottom} x2={cx + rx + 14} y2={cy_bottom}
          stroke={GEO_ACCENT} strokeWidth="1.5" />
        <MeasureLabel x={cx + rx + 26} y={(cy_top + cy_bottom) / 2} text={height_label} />
      </>}
    </svg>
  )
}

// ── CONE (Gap-3) ──────────────────────────────────────────────────────────────
function ConeVisual({ data }: { data: GeometryData }) {
  const c = data.cone_data!
  const { cx, apex_y, base_cy, rx, ry, radius_label, height_label, slant_label } = c
  return (
    <svg viewBox="0 0 200 160" className="w-full max-w-xs">
      <ellipse cx={cx} cy={base_cy} rx={rx} ry={ry}
        fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" />
      <line x1={cx} y1={apex_y} x2={cx - rx} y2={base_cy}
        stroke={GEO_STROKE} strokeWidth="2" />
      <line x1={cx} y1={apex_y} x2={cx + rx} y2={base_cy}
        stroke={GEO_STROKE} strokeWidth="2" />
      <circle cx={cx} cy={apex_y} r="3" fill={GEO_STROKE} />
      {height_label && <>
        <line x1={cx} y1={apex_y} x2={cx} y2={base_cy}
          stroke={GEO_ACCENT} strokeWidth="1.5" strokeDasharray="4 2" />
        <MeasureLabel x={cx + 18} y={(apex_y + base_cy) / 2} text={height_label} />
      </>}
      {radius_label && <>
        <line x1={cx} y1={base_cy} x2={cx + rx} y2={base_cy}
          stroke={GEO_ACCENT} strokeWidth="1.5" strokeDasharray="4 2" />
        <MeasureLabel x={(cx + cx + rx) / 2} y={base_cy + 14} text={radius_label} />
      </>}
      {slant_label && (
        <MeasureLabel
          x={(cx + cx + rx) / 2 + 4}
          y={(apex_y + base_cy) / 2 - 8}
          text={slant_label} />
      )}
    </svg>
  )
}

// ── CUBOID (Gap-3) ─────────────────────────────────────────────────────────────
function CuboidVisual({ data }: { data: GeometryData }) {
  const c = data.cuboid_data!
  const toPoints = (pts: [number, number][]) => pts.map(p => `${p[0]},${p[1]}`).join(' ')
  const { labels, label_pos } = c
  return (
    <svg viewBox="0 0 200 160" className="w-full max-w-xs">
      {/* Right face — darkest shade */}
      <polygon points={toPoints(c.right as [number, number][])
        } fill="#cce8f0" stroke={GEO_STROKE} strokeWidth="1.5" strokeLinejoin="round" />
      {/* Top face — medium shade */}
      <polygon points={toPoints(c.top as [number, number][])
        } fill="#d8eff7" stroke={GEO_STROKE} strokeWidth="1.5" strokeLinejoin="round" />
      {/* Front face — lightest */}
      <polygon points={toPoints(c.front as [number, number][])
        } fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" strokeLinejoin="round" />
      {labels.length && label_pos.length && (
        <MeasureLabel x={label_pos.length![0]} y={label_pos.length![1]} text={labels.length} />
      )}
      {labels.width && label_pos.width && (
        <MeasureLabel x={label_pos.width![0]}  y={label_pos.width![1]}  text={labels.width}  />
      )}
      {labels.height && label_pos.height && (
        <MeasureLabel x={label_pos.height![0]} y={label_pos.height![1]} text={labels.height} />
      )}
    </svg>
  )
}

// ── COORDINATE AXES (R-C) ─────────────────────────────────────────────────────
function CoordinateAxesVisual({ data }: { data: AxesData }) {
  const W = 280, H = 240, PAD = 38
  const { x_min, x_max, y_min, y_max } = data
  const xRange = x_max - x_min || 1
  const yRange = y_max - y_min || 1

  const toX = (v: number) => PAD + (v - x_min) / xRange * (W - 2*PAD)
  const toY = (v: number) => H - PAD - (v - y_min) / yRange * (H - 2*PAD)

  // Smart tick spacing
  const xStep = xRange <= 10 ? 1 : xRange <= 20 ? 2 : xRange <= 50 ? 5 : 10
  const yStep = yRange <= 10 ? 1 : yRange <= 20 ? 2 : yRange <= 50 ? 5 : 10

  const xTicks: number[] = []
  for (let v = Math.ceil(x_min/xStep)*xStep; v <= x_max; v += xStep) xTicks.push(+v.toFixed(6))
  const yTicks: number[] = []
  for (let v = Math.ceil(y_min/yStep)*yStep; v <= y_max; v += yStep) yTicks.push(+v.toFixed(6))

  // Clamp origin so axes always appear inside viewport
  const ox = Math.max(PAD, Math.min(W-PAD, toX(0)))
  const oy = Math.max(PAD, Math.min(H-PAD, toY(0)))

  const AXIS_CLR = '#374151'
  const POINT_CLR = GEO_ACCENT

  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-sm">
        {/* Grid lines */}
        {xTicks.map(v => (
          <line key={`vg${v}`}
            x1={toX(v)} y1={PAD} x2={toX(v)} y2={H-PAD}
            stroke={v === 0 ? '#d1d5db' : '#f3f4f6'} strokeWidth={v === 0 ? 1 : 1} />
        ))}
        {yTicks.map(v => (
          <line key={`hg${v}`}
            x1={PAD} y1={toY(v)} x2={W-PAD} y2={toY(v)}
            stroke={v === 0 ? '#d1d5db' : '#f3f4f6'} strokeWidth={v === 0 ? 1 : 1} />
        ))}

        {/* X axis */}
        <line x1={PAD-4} y1={oy} x2={W-PAD+10} y2={oy} stroke={AXIS_CLR} strokeWidth="1.5" />
        <polygon points={`${W-PAD+10},${oy} ${W-PAD+3},${oy-3} ${W-PAD+3},${oy+3}`} fill={AXIS_CLR} />
        <text x={W-PAD+14} y={oy+4} fontSize="12" fill={AXIS_CLR} fontWeight="700">x</text>

        {/* Y axis */}
        <line x1={ox} y1={H-PAD+4} x2={ox} y2={PAD-10} stroke={AXIS_CLR} strokeWidth="1.5" />
        <polygon points={`${ox},${PAD-10} ${ox-3},${PAD-3} ${ox+3},${PAD-3}`} fill={AXIS_CLR} />
        <text x={ox+4} y={PAD-12} fontSize="12" fill={AXIS_CLR} fontWeight="700">y</text>

        {/* X tick marks + labels */}
        {xTicks.map(v => (
          <g key={`xt${v}`}>
            <line x1={toX(v)} y1={oy-4} x2={toX(v)} y2={oy+4} stroke={AXIS_CLR} strokeWidth="1" />
            {v !== 0 && (
              <text x={toX(v)} y={oy+15} textAnchor="middle" fontSize="9" fill="#6b7280">{v}</text>
            )}
          </g>
        ))}

        {/* Y tick marks + labels */}
        {yTicks.map(v => (
          <g key={`yt${v}`}>
            <line x1={ox-4} y1={toY(v)} x2={ox+4} y2={toY(v)} stroke={AXIS_CLR} strokeWidth="1" />
            {v !== 0 && (
              <text x={ox-8} y={toY(v)+4} textAnchor="end" fontSize="9" fill="#6b7280">{v}</text>
            )}
          </g>
        ))}

        {/* Origin label */}
        {x_min <= 0 && x_max >= 0 && y_min <= 0 && y_max >= 0 && (
          <text x={ox-8} y={oy+15} textAnchor="end" fontSize="9" fill="#6b7280">0</text>
        )}

        {/* Shaded polygon region */}
        {data.polygon_points && data.polygon_points.length >= 3 && (
          <polygon
            points={data.polygon_points.map(([x,y]) => `${toX(x)},${toY(y)}`).join(' ')}
            fill="rgba(1,105,111,0.12)" stroke={POINT_CLR} strokeWidth="1.5" strokeLinejoin="round" />
        )}

        {/* Line segments */}
        {(data.segments ?? []).map((seg, i) => (
          <g key={i}>
            <line
              x1={toX(seg.from[0])} y1={toY(seg.from[1])}
              x2={toX(seg.to[0])}   y2={toY(seg.to[1])}
              stroke={POINT_CLR} strokeWidth="1.5"
              strokeDasharray={seg.dashed ? '4 2' : undefined} />
            {seg.label && (
              <text
                x={(toX(seg.from[0])+toX(seg.to[0]))/2 + 6}
                y={(toY(seg.from[1])+toY(seg.to[1]))/2 - 6}
                fontSize="9" fill={POINT_CLR} fontWeight="600">{seg.label}</text>
            )}
          </g>
        ))}

        {/* Points */}
        {(data.points ?? []).map((pt, i) => (
          <g key={i}>
            <circle cx={toX(pt.x)} cy={toY(pt.y)} r="4" fill={POINT_CLR} />
            {pt.label && (
              <text x={toX(pt.x)+8} y={toY(pt.y)-6}
                fontSize="11" fontWeight="700" fill={POINT_CLR}>{pt.label}</text>
            )}
            <text x={toX(pt.x)} y={toY(pt.y)+17}
              textAnchor="middle" fontSize="8" fill="#9ca3af">
              ({pt.x},{pt.y})
            </text>
          </g>
        ))}
      </svg>
    </div>
  )
}

// ── GEOMETRY (single shape) ───────────────────────────────────────────────────
function GeometryVisual({ data }: { data: GeometryData }) {
  const { shape, vertices, angles, circle_data, measurements, description } = data
  const V = vertices

  // ── CUBE NET ────────────────────────────────────────────────────────────────
  if (shape === 'cube_net') return <CubeNetVisual data={data} />

  // ── 3-D SHAPES ─────────────────────────────────────────────────────────────
  if (shape === 'cylinder' && data.cylinder_data) return <CylinderVisual data={data} />
  if (shape === 'cone'     && data.cone_data)     return <ConeVisual     data={data} />
  if (shape === 'cuboid'   && data.cuboid_data)   return <CuboidVisual   data={data} />

  // ── CIRCLE ──────────────────────────────────────────────────────────────────
  if (shape === 'circle' && circle_data) {
    const { cx: _cx, cy: _cy, radius, radius_label, diameter_label } = circle_data
    const scale = Math.min(80 / radius, 1)
    const scx = 100, scy = 80, sr = radius * scale
    const rx2 = scx + sr
    return (
      <svg viewBox="0 0 200 160" className="w-full max-w-xs">
        <circle cx={scx} cy={scy} r={sr} fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" />
        {radius_label && <>
          <line x1={scx} y1={scy} x2={rx2} y2={scy} stroke={GEO_ACCENT} strokeWidth="1.5" strokeDasharray="3 2" />
          <MeasureLabel x={(scx+rx2)/2} y={scy - 10} text={radius_label} />
        </>}
        {diameter_label && <>
          <line x1={scx-sr} y1={scy} x2={scx+sr} y2={scy} stroke={GEO_ACCENT} strokeWidth="1.5" strokeDasharray="3 2" />
          <MeasureLabel x={scx} y={scy+sr+14} text={diameter_label} />
        </>}
        <circle cx={scx} cy={scy} r="2.5" fill={GEO_STROKE} />
      </svg>
    )
  }

  // ── POLYGON / TRIANGLE / RECTANGLE / COMPOUND / ANGLE (vertex-based) ────────
  if (V && Object.keys(V).length >= 2) {
    const keys = Object.keys(V)
    const pts  = keys.map(k => V[k])
    const polyPoints = pts.map(p => `${p[0]},${p[1]}`).join(' ')

    const measureMap: Record<string, string> = {}
    ;(measurements || []).forEach(m => { measureMap[m.label] = m.value })

    // Track which measurement labels are attached to a vertex pair.
    const attachedLabels = new Set<string>()
    for (let i = 0; i < keys.length; i++) {
      const k = keys[i], next = keys[(i + 1) % keys.length]
      ;(measurements || []).forEach(m => {
        if (m.label === `${k}${next}` || m.label === `${next}${k}`) {
          attachedLabels.add(m.label)
        }
      })
    }
    const unmatched = (measurements || []).filter(m => !attachedLabels.has(m.label)
      && m.type !== 'angle'
    )

    const rightAngleVertex = shape === 'right_triangle'
      ? (keys.find(k => angles?.[k] === '90°') ?? keys[1])
      : null

    return (
      <div>
        <svg viewBox="0 0 200 160" className="w-full max-w-xs">
          <polygon points={polyPoints} fill={GEO_FILL} stroke={GEO_STROKE} strokeWidth="2" strokeLinejoin="round" />

          {rightAngleVertex && (() => {
            const idx  = keys.indexOf(rightAngleVertex)
            const prev = keys[(idx-1+keys.length)%keys.length]
            const next = keys[(idx+1)%keys.length]
            return <RightAngleMark B={V[rightAngleVertex]} A={V[prev]} C={V[next]} />
          })()}

          {keys.map(k => {
            const [x, y] = V[k]
            const cxv = pts.reduce((s,p) => s+p[0],0)/pts.length
            const cyv = pts.reduce((s,p) => s+p[1],0)/pts.length
            const dx = x-cxv, dy = y-cyv
            const len = Math.sqrt(dx*dx+dy*dy)||1
            return (
              <text key={k} x={x+(dx/len)*12} y={y+(dy/len)*12}
                textAnchor="middle" dominantBaseline="central"
                fontSize="11" fontWeight="700" fill={GEO_STROKE}>{k}</text>
            )
          })}

          {keys.map((k,i) => {
            const next = keys[(i+1)%keys.length]
            const label = measureMap[`${k}${next}`] || measureMap[`${next}${k}`]
            if (!label) return null
            const [mx, my] = mid(V[k], V[next])
            const cxv = pts.reduce((s,p) => s+p[0],0)/pts.length
            const cyv = pts.reduce((s,p) => s+p[1],0)/pts.length
            const dx = mx-cxv, dy = my-cyv
            const len = Math.sqrt(dx*dx+dy*dy)||1
            return <MeasureLabel key={`${k}${next}`} x={mx+(dx/len)*14} y={my+(dy/len)*14} text={label} />
          })}

          {keys.map((k,i) => {
            const angleLabel = angles?.[k]
            if (!angleLabel || angleLabel === '90°') return null
            const prev = keys[(i-1+keys.length)%keys.length]
            const next = keys[(i+1)%keys.length]
            return <AngleArc key={k} O={V[k]} A={V[prev]} B={V[next]} label={angleLabel} />
          })}
        </svg>

        {/* Gap 2: show measurements not attached to any vertex pair as chips */}
        {unmatched.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-2">
            {unmatched.map((m, i) => (
              <span key={i}
                className="bg-white border border-blue-200 text-blue-700 text-xs px-2 py-0.5 rounded-lg font-mono">
                {m.label} = {m.value}
              </span>
            ))}
          </div>
        )}
      </div>
    )
  }

  // ── FALLBACK: text description + measurement chips ────────────────────────
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

// ── MCQ OPTIONS GRID (read-only for Results page) ─────────────────────────────
interface MCQOptionsVisualProps {
  data: MCQOptionsData
  selectedOption?: string  // Student's selected option (for highlighting)
}

function MCQOptionsVisual({ data, selectedOption }: MCQOptionsVisualProps) {
  const options = data.options || []
  const correctOpt = (data.correct_option || '').toUpperCase()
  
  return (
    <div className="grid grid-cols-2 gap-3 my-3">
      {options.map((opt, idx) => {
        const label = opt.label?.toUpperCase() || String.fromCharCode(65 + idx)
        const isCorrect = label === correctOpt
        const isSelected = selectedOption && label === selectedOption.toUpperCase()
        
        let borderColor = 'border-gray-200'
        if (isSelected && isCorrect) borderColor = 'border-green-500 ring-2 ring-green-200'
        else if (isSelected && !isCorrect) borderColor = 'border-red-400 ring-2 ring-red-200'
        else if (isCorrect) borderColor = 'border-green-400'
        
        return (
          <div key={idx} className={`relative rounded-xl border-2 ${borderColor} bg-white overflow-hidden`}>
            {/* Letter badge */}
            <div className={`absolute top-1.5 left-1.5 w-7 h-7 rounded-full flex items-center justify-center font-bold text-sm z-10
              ${isSelected ? 'bg-primary-500 text-white' : 'bg-gray-100 text-gray-600'}`}>
              {label}
            </div>
            {/* Visual content */}
            <div className="pt-9 p-2">
              <VisualDisplay visualData={opt.visual} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── PAGE IMAGE ───────────────────────────────────────────────────────────────
function PageImageVisual({ data }: { data: PageImageData }) {
  const src = `/api/v1/textbooks/${data.textbook_id}/page/${data.page}`
  return (
    <div className="rounded-xl overflow-hidden border border-gray-200 bg-gray-50">
      {data.description && <p className="text-xs text-gray-500 px-3 py-1.5 border-b border-gray-100">{data.description}</p>}
      <img src={src} alt="Figure from textbook" className="w-full object-contain max-h-96" loading="lazy" />
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
interface Props {
  visualData: string | object | null
  visualType?: string | null
  selectedOption?: string  // For MCQ: student's selected option (Results page)
}

export default function VisualDisplay({ visualData, visualType, selectedOption }: Props) {
  if (!visualData) return null

  let data: VisualData
  try {
    data = typeof visualData === 'string' ? JSON.parse(visualData) : visualData as VisualData
  } catch {
    return null
  }

  const type = data.type || visualType

  // Handle mcq_options type specially
  if (type === 'mcq_options') {
    return (
      <div className="my-3">
        <MCQOptionsVisual data={data as MCQOptionsData} selectedOption={selectedOption} />
      </div>
    )
  }

  return (
    <div className="my-3 p-3 bg-gray-50 rounded-xl border border-gray-100">
      <p className="text-xs text-gray-400 uppercase tracking-wide font-medium mb-2">Figure</p>
      {type === 'table'       && <TableVisual          data={data as TableData} />}
      {type === 'number_line' && <NumberLineVisual      data={data as NumberLineData} />}
      {type === 'bar_graph'   && <BarGraphVisual        data={data as BarGraphData} />}
      {type === 'pie_chart'   && <PieChartVisual        data={data as PieChartData} />}
      {type === 'geometry'    && <GeometryVisual        data={data as GeometryData} />}
      {type === 'axes'        && <CoordinateAxesVisual  data={data as AxesData} />}
      {type === 'page_image'  && <PageImageVisual       data={data as PageImageData} />}
    </div>
  )
}
