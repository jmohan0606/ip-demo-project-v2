import type { Config } from "tailwindcss";
const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    container: { center: true, padding: "24px", screens: { "2xl": "1440px" } },
    extend: {
      fontFamily: {
        v2: ['Calibri', 'Carlito', '-apple-system', '"Segoe UI"', 'sans-serif'],
      },
      colors: {
        // iPerform V2 tokens (docs/ui/DESIGN_TOKENS.md)
        v2: {
          navy: "#10315B",
          "navy-dark": "#0B2444",
          "navy-ink": "#12243B",
          page: "#F4F6F9",
          card: "#FFFFFF",
          "header-bg": "#E8EDF4",
          "group-bg": "#EEF2F7",
          "sub-bg": "#F7F9FC",
          "total-bg": "#E3EAF3",
          text: "#1C2530",
          muted: "#63707F",
          faint: "#8B98A8",
          link: "#1B62B5",
          positive: "#1E7A45",
          "positive-bg": "#E8F3EC",
          negative: "#B3261E",
          "negative-bg": "#FBEAE8",
          warn: "#B7791F",
          "warn-bg": "#FDF6E7",
          purple: "#5B3E90",
          "chart-recurring": "#C2BE9E",
          "chart-nonrecurring": "#6193BD",
          grid: "#EEF1F5",
          border: "#D8DEE8",
          "border-strong": "#B9C4D2",
          "border-subtle": "#EDF1F6",
        },
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
        secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
        muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
        accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
        destructive: { DEFAULT: "hsl(var(--destructive))", foreground: "hsl(var(--destructive-foreground))" },
        success: { DEFAULT: "hsl(var(--success))", foreground: "hsl(var(--success-foreground))" },
        warning: { DEFAULT: "hsl(var(--warning))", foreground: "hsl(var(--warning-foreground))" }
      },
      borderRadius: { xl: "18px", "2xl": "24px", "3xl": "32px" },
      boxShadow: {
        "enterprise-card": "0 16px 45px rgba(15, 23, 42, 0.12)",
        "glow-blue": "0 0 40px rgba(59, 130, 246, 0.22)"
      },
      animation: { "slide-up": "slide-up .35s ease-out" },
      keyframes: { "slide-up": { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "translateY(0)" } } }
    }
  },
  plugins: [require("tailwindcss-animate")]
};
export default config;
