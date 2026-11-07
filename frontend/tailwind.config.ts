import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#2D332C",
        navy: "#222721",
        charcoal: "#242424",
        moss: "#4F5D4E",
        sage: "#8A9A86",
        clay: "#A68B6D",
        terracotta: "#C9A77A",
        linen: "#F4F0EA",
        ivory: "#FAF8F5",
        sand: "#E8E0D5",
        stone: "#F2EDE6",
        cream: "#FAF8F5",
        forest: "#2D332C",
        wood: "#A68B6D",
        champagne: "#C9A77A",
        obsidian: "#242424",
        muted: "#777777"
      },
      boxShadow: {
        soft: "0 20px 50px rgba(45, 51, 44, 0.10)",
        card: "0 10px 30px rgba(45, 51, 44, 0.06)",
        luxury: "0 24px 60px rgba(45, 51, 44, 0.14)"
      }
    }
  },
  plugins: []
};

export default config;

