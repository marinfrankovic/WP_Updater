/** Simple shimmer skeleton block. Width/height accept any CSS size. */
export function Skeleton({ width = '100%', height = 16, radius = 6 }: { width?: string | number; height?: string | number; radius?: number }) {
  return (
    <span
      className="skeleton"
      style={{ width, height, borderRadius: radius, display: 'inline-block' }}
    />
  );
}

/** A full skeleton table used while the app is "loading". */
export function SkeletonTable({ rows = 8, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="card">
      <table className="data-table">
        <thead>
          <tr>
            {Array.from({ length: cols }).map((_, i) => (
              <th key={i}><Skeleton width="70%" /></th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, r) => (
            <tr key={r}>
              {Array.from({ length: cols }).map((_, c) => (
                <td key={c}><Skeleton width={c === 0 ? 18 : '80%'} /></td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
