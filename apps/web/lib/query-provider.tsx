"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

export const STALE_TIMES = {
  realtime: 0,
  frequent: 30 * 1000,
  standard: 2 * 60 * 1000,
  slow: 5 * 60 * 1000,
  static: 30 * 60 * 1000,
} as const;

export function PactQueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: STALE_TIMES.standard,
            gcTime: 10 * 60 * 1000,
            retry: 2,
            refetchOnWindowFocus: true,
          },
          mutations: {
            retry: 1,
          },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
