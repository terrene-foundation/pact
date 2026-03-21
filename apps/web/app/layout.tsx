// Copyright 2026 Terrene Foundation
// Licensed under the Apache License, Version 2.0

import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "../lib/auth-context";
import { NotificationProvider } from "../lib/notification-context";

export const metadata: Metadata = {
  title: {
    default: "PACT",
    template: "%s | PACT",
  },
  description:
    "Governed operational model for running organizations with AI agents under EATP trust governance",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        {/* Skip to main content link for keyboard navigation */}
        <a href="#main-content" className="skip-link">
          Skip to main content
        </a>
        <AuthProvider>
          <NotificationProvider>{children}</NotificationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
