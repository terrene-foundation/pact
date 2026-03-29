/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Shadcn CSS variable-based colors
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },

        // PACT semantic colors
        // Verification gradient levels
        "gradient-auto": {
          DEFAULT: "#16a34a",
          light: "#dcfce7",
          dark: "#166534",
        },
        "gradient-flagged": {
          DEFAULT: "#eab308",
          light: "#fef9c3",
          dark: "#854d0e",
        },
        "gradient-held": {
          DEFAULT: "#f97316",
          light: "#ffedd5",
          dark: "#9a3412",
        },
        "gradient-blocked": {
          DEFAULT: "#dc2626",
          light: "#fee2e2",
          dark: "#991b1b",
        },

        // Trust posture levels (cool → warm as autonomy increases)
        "posture-pseudo": { DEFAULT: "#6b7280", light: "#f3f4f6" },
        "posture-supervised": { DEFAULT: "#3b82f6", light: "#dbeafe" },
        "posture-shared": { DEFAULT: "#8b5cf6", light: "#ede9fe" },
        "posture-continuous": { DEFAULT: "#06b6d4", light: "#cffafe" },
        "posture-delegated": { DEFAULT: "#16a34a", light: "#dcfce7" },

        // Platform brand
        "care-primary": {
          DEFAULT: "#2563eb",
          light: "#eff6ff",
          dark: "#1e40af",
        },
        "care-surface": { DEFAULT: "#ffffff", dark: "#111827" },
        "care-border": { DEFAULT: "#e5e7eb", dark: "#374151" },
        "care-muted": { DEFAULT: "#6b7280", light: "#9ca3af" },

        // Status
        "status-active": "#16a34a",
        "status-suspended": "#eab308",
        "status-revoked": "#dc2626",
        "status-inactive": "#6b7280",

        // Urgency (for approval queue)
        "urgency-critical": "#dc2626",
        "urgency-high": "#f97316",
        "urgency-medium": "#eab308",
        "urgency-low": "#6b7280",
      },

      // Shadcn border radius
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },

      // Typography scale
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },

      // Spacing for consistent dashboard layout
      spacing: {
        sidebar: "16rem", // 256px sidebar width
        header: "3.5rem", // 56px header height
      },

      // Animation for real-time activity feed
      keyframes: {
        "slide-in": {
          "0%": { transform: "translateX(-10px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.5" },
        },
      },
      animation: {
        "slide-in": "slide-in 0.2s ease-out",
        "pulse-slow": "pulse 2s ease-in-out infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
