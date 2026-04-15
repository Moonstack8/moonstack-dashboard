export default function DataTable({ columns, data, onRowClick, onRowAction, emptyMessage = 'No data' }) {
  if (!data?.length) {
    return (
      <div className="text-center py-12 text-gray-600 text-sm">{emptyMessage}</div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rim">
            {columns.map(col => (
              <th
                key={col.key}
                className={`text-left py-2.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-gray-500 whitespace-nowrap ${
                  col.align === 'right' ? 'text-right' : ''
                }`}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr
              key={row.id || i}
              onClick={() => onRowClick?.(row)}
              className={`border-b border-rim transition-colors ${
                onRowClick ? 'cursor-pointer hover:bg-ink/[0.03]' : ''
              }`}
            >
              {columns.map(col => (
                <td
                  key={col.key}
                  onClick={col.key === 'delete' || col.key === 'optimize' ? e => e.stopPropagation() : undefined}
                  className={`py-2.5 px-3 text-ink/70 whitespace-nowrap ${
                    col.align === 'right' ? 'text-right' : ''
                  }`}
                >
                  {col.render ? col.render(row, onRowAction) : row[col.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
