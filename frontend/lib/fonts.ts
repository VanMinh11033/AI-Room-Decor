import { Newsreader, Plus_Jakarta_Sans } from "next/font/google";

/**
 * Editorial Serif display font for headings, luxury quotes and architectural accents.
 * Includes complete Vietnamese diacritic coverage.
 */
export const newsreader = Newsreader({
  subsets: ["latin", "vietnamese"],
  display: "swap",
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-newsreader",
  fallback: ["Georgia", "Cambria", "Times New Roman", "serif"],
});

/**
 * Modern architectural sans-serif for UI, navigation, labels, data and body prose.
 * Includes complete Vietnamese diacritic coverage.
 */
export const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin", "vietnamese"],
  display: "swap",
  weight: ["400", "500", "600", "700", "800"],
  variable: "--font-plus-jakarta",
  fallback: ["system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "sans-serif"],
});
