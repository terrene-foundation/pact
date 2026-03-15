// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

/**
 * Pagination -- page navigation and page-size selector for the audit table.
 *
 * Displays Previous/Next buttons, current page indicator, total record count,
 * and a page-size dropdown (25, 50, 100 records per page).
 */

"use client";

interface PaginationProps {
  /** Current page (1-indexed). */
  page: number;
  /** Number of records per page. */
  pageSize: number;
  /** Total number of records across all pages. */
  totalRecords: number;
  /** Callback when the page changes. */
  onPageChange: (page: number) => void;
  /** Callback when the page size changes (resets to page 1). */
  onPageSizeChange: (size: number) => void;
}

const PAGE_SIZE_OPTIONS = [25, 50, 100];

/** Pagination controls for the audit trail table. */
export default function Pagination({
  page,
  pageSize,
  totalRecords,
  onPageChange,
  onPageSizeChange,
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalRecords / pageSize));
  const startRecord = totalRecords === 0 ? 0 : (page - 1) * pageSize + 1;
  const endRecord = Math.min(page * pageSize, totalRecords);

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      {/* Record count and page size */}
      <div className="flex items-center gap-4">
        <p className="text-xs text-gray-500">
          {totalRecords === 0
            ? "No records"
            : `Showing ${startRecord}-${endRecord} of ${totalRecords} records`}
        </p>
        <div className="flex items-center gap-2">
          <label htmlFor="audit-page-size" className="text-xs text-gray-500">
            Per page:
          </label>
          <select
            id="audit-page-size"
            value={pageSize}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            className="rounded-md border border-gray-300 px-2 py-1 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Page navigation */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Previous page"
        >
          Previous
        </button>
        <span className="text-xs text-gray-600 tabular-nums">
          Page {page} of {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="rounded-md border border-gray-300 bg-white px-3 py-1 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Next page"
        >
          Next
        </button>
      </div>
    </div>
  );
}
