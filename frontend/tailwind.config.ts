// frontend/tailwind.config.ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        // Aviation dark theme
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",

        // TRACE-X brand colors
        tracex: {
          50: "#f0f9ff",
          100: "#e0f2fe",
          200: "#bae6fd",
          300: "#7dd3fc",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
          800: "#075985",
          900: "#0c4a6e",
          950: "#082f49",
        },

        // Status colors
        success: {
          DEFAULT: "#22c55e",
          foreground: "#ffffff",
          dim: "#15803d",
          bg: "rgba(34, 197, 94, 0.1)",
        },
        warning: {
          DEFAULT: "#f59e0b",
          foreground: "#000000",
          dim: "#d97706",
          bg: "rgba(245, 158, 11, 0.1)",
        },
        danger: {
          DEFAULT: "#ef4444",
          foreground: "#ffffff",
          dim: "#dc2626",
          bg: "rgba(239, 68, 68, 0.1)",
        },
        critical: {
          DEFAULT: "#dc2626",
          foreground: "#ffffff",
          bg: "rgba(220, 38, 38, 0.15)",
        },

        // Severity
        severity: {
          critical: "#dc2626",
          high: "#ef4444",
          medium: "#f59e0b",
          low: "#22c55e",
          info: "#3b82f6",
        },

        // UI surfaces
        surface: {
          DEFAULT: "hsl(var(--surface))",
          elevated: "hsl(var(--surface-elevated))",
          dim: "hsl(var(--surface-dim))",
        },

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
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"],
        display: ["var(--font-display)", "system-ui", "sans-serif"],
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fadeIn 0.3s ease-in",
        "slide-in-right": "slideInRight 0.3s ease-out",
        "slide-in-up": "slideInUp 0.4s ease-out",
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "spin-slow": "spin 3s linear infinite",
        "glow": "glow 2s ease-in-out infinite alternate",
        "radar": "radar 2s linear infinite",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideInRight: {
          "0%": { transform: "translateX(100%)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        slideInUp: {
          "0%": { transform: "translateY(20px)", opacity: "0" },
          "100%": { transform: "translateY(0)", opacity: "1" },
        },
        glow: {
          "0%": { boxShadow: "0 0 5px rgba(14, 165, 233, 0.2)" },
          "100%": { boxShadow: "0 0 20px rgba(14, 165, 233, 0.6)" },
        },
        radar: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
      },
      boxShadow: {
        glass: "0 4px 30px rgba(0, 0, 0, 0.1)",
        glow: "0 0 20px rgba(14, 165, 233, 0.4)",
        "glow-danger": "0 0 20px rgba(239, 68, 68, 0.4)",
        "glow-success": "0 0 20px rgba(34, 197, 94, 0.4)",
        "inner-glass": "inset 0 1px 0 rgba(255, 255, 255, 0.1)",
      },
      backgroundImage: {
        "grid-pattern":
          "linear-gradient(rgba(14, 165, 233, 0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(14, 165, 233, 0.05) 1px, transparent 1px)",
        "radial-glow":
          "radial-gradient(ellipse at center, rgba(14, 165, 233, 0.15) 0%, transparent 70%)",
      },
      backgroundSize: {
        grid: "40px 40px",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
