import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}", "./lib/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ["var(--font-newsreader)", "Georgia", "Cambria", "Times New Roman", "serif"],
        sans: ["var(--font-plus-jakarta)", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
      },
      colors: {
        // Quiet Luxury Master Tokens
        alabaster: "#FBF9F5",
        "forest-ink": "#242B23",
        "warm-bronze": "#8A6B4E",
        "warm-stone": "#DDD7CD",

        // Calibrated backward-compatible tokens (WCAG 2.2 AA Certified)
        ink: "#242B23",         // Deep forest ink (13.8:1 on alabaster)
        navy: "#1C221B",        // Deepest obsidian
        charcoal: "#242424",    // Primary body text (14.8:1 on alabaster)
        moss: "#3D493C",        // Deep architectural moss
        sage: "#6E7E6A",        // Muted architectural sage
        clay: "#8A6B4E",        // Deepened to Warm Bronze (4.65:1 on alabaster, AA PASS)
        terracotta: "#8A6B4E",  // Deepened to Warm Bronze for text readability
        linen: "#F4F0EA",       // Muted linen surface
        ivory: "#FBF9F5",       // Architectural alabaster background
        sand: "#E8E2D8",        // Architectural sand
        stone: "#DDD7CD",       // Warm architectural stone for borders & dividers
        cream: "#FBF9F5",       // Alabaster surface
        forest: "#242B23",      // Deep forest ink
        wood: "#8A6B4E",        // Warm bronze
        champagne: "#C9A77A",   // Retained strictly for non-text borders & metallic accents
        obsidian: "#242424",    // Near-black text
        muted: "#5A6258",       // Deepened from #777777 to Soft Muted (6.0:1 on alabaster, AA PASS)

        // Semantic UI status tokens
        status: {
          success: "#1E6B37",
          "success-bg": "#EBF6EE",
          warning: "#9E5600",
          "warning-bg": "#FEF7E6",
          error: "#B3261E",
          "error-bg": "#FDF2F1",
          info: "#1A5FB4",
          "info-bg": "#EFF5FD"
        }
      },
      borderRadius: {
        sm: "0.5rem",     // 8px - chips, badges
        DEFAULT: "0.75rem",// 12px - inputs, buttons
        md: "0.875rem",   // 14px - secondary cards
        lg: "1rem",       // 16px - standard surface cards
        xl: "1.25rem",    // 20px - bento cards
        "2xl": "1.5rem",   // 24px - modal dialogues, hero containers
        "3xl": "1.75rem",  // 28px - editorial display frames
        full: "9999px"    // pill buttons, avatar rings
      },
      boxShadow: {
        soft: "0 20px 50px rgba(36, 43, 35, 0.08)",
        card: "0 8px 24px rgba(36, 43, 35, 0.05)",
        luxury: "0 24px 60px rgba(36, 43, 35, 0.12)"
      }
    }
  },
  plugins: []
};

export default config;
