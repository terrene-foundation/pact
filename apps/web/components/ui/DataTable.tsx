// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * DataTable -- sortable, filterable data table for dashboard views.
 *
 * Supports:
 * - Column-based sorting (ascending/descending toggle)
 * - Text filtering across all columns
 * - Custom cell rendering via column definitions
 * - Responsive layout with horizontal scroll on small screens
 */

"use client";

import { useState, useMemo, useCallback } from "react";

/** Column definition for the DataTable. */
export interface Column<T> {
  /** Unique key for the column, must match a property of T or be a custom key. */
  key: string;
  /** Display header text. */
  header: string;
  /** Whether this column is sortable. Defaults to true. */
  sortable?: boolean;
  /** Custom render function for the cell. Receives the full row. */
  render?: (row: T) => React.ReactNode;
  /** Accessor function to extract the value for sorting/filtering. */
  accessor?: (row: T) => string | number;
}

interface DataTableProps<T> {
  /** Column definitions. */
  columns: Column<T>[];
  /** Array of data rows. */
  data: T[];
  /** Unique key extractor for each row (used as React key). */
  rowKey: (row: T) => string;
  /** Optional placeholder text for the filter input. */
  filterPlaceholder?: string;
  /** When true, the filter input is shown. Defaults to true. */
  filterable?: boolean;
  /** Optional message when data is empty. */
  emptyMessage?: string;
}

type SortDirection = "asc" | "desc";

interface SortState {
  key: string;
  direction: SortDirection;
}

/** Get a sortable/filterable value from a row for a given column. */
function getCellValue<T>(row: T, column: Column<T>): string | number {
  if (column.accessor) {
    return column.accessor(row);
  }
  const value = (row as Record<string, unknown>)[column.key];
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return value;
  return String(value);
}

/** Sortable, filterable data table component. */
export default function DataTable<T>({
  columns,
  data,
  rowKey,
  filterPlaceholder = "Filter...",
  filterable = true,
  emptyMessage = "No data available",
}: DataTableProps<T>) {
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState<SortState | null>(null);

  const handleSort = useCallback(
    (key: string) => {
      setSort((prev) => {
        if (prev?.key === key) {
          return prev.direction === "asc"
            ? { key, direction: "desc" }
            : null;
        }
        return { key, direction: "asc" };
      });
    },
    []
  );

  const filteredData = useMemo(() => {
    if (!filter.trim()) return data;
    const lowerFilter = filter.toLowerCase();
    return data.filter((row) =>
      columns.some((col) => {
        const val = getCellValue(row, col);
        return String(val).toLowerCase().includes(lowerFilter);
      })
    );
  }, [data, filter, columns]);

  const sortedData = useMemo(() => {
    if (!sort) return filteredData;
    const col = columns.find((c) => c.key === sort.key);
    if (!col) return filteredData;

    return [...filteredData].sort((a, b) => {
      const aVal = getCellValue(a, col);
      const bVal = getCellValue(b, col);
      let cmp: number;
      if (typeof aVal === "number" && typeof bVal === "number") {
        cmp = aVal - bVal;
      } else {
        cmp = String(aVal).localeCompare(String(bVal));
      }
      return sort.direction === "asc" ? cmp : -cmp;
    });
  }, [filteredData, sort, columns]);

  const sortIndicator = (key: string): string => {
    if (sort?.key !== key) return "";
    return sort.direction === "asc" ? " \u2191" : " \u2193";
  };

  return (
    <div className="w-full">
      {filterable && (
        <div className="mb-3">
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={filterPlaceholder}
            className="w-full max-w-sm rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            aria-label="Filter table"
          />
        </div>
      )}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {columns.map((col) => {
                const isSortable = col.sortable !== false;
                return (
                  <th
                    key={col.key}
                    scope="col"
                    className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-600 ${
                      isSortable ? "cursor-pointer select-none hover:bg-gray-100" : ""
                    }`}
                    onClick={isSortable ? () => handleSort(col.key) : undefined}
                    aria-sort={
                      sort?.key === col.key
                        ? sort.direction === "asc"
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    {col.header}
                    {isSortable && sortIndicator(col.key)}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 bg-white">
            {sortedData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-sm text-gray-500"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              sortedData.map((row) => (
                <tr key={rowKey(row)} className="hover:bg-gray-50">
                  {columns.map((col) => (
                    <td key={col.key} className="whitespace-nowrap px-4 py-3 text-sm text-gray-800">
                      {col.render ? col.render(row) : String(getCellValue(row, col))}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {filterable && filter && (
        <p className="mt-2 text-xs text-gray-500">
          Showing {sortedData.length} of {data.length} rows
        </p>
      )}
    </div>
  );
}
