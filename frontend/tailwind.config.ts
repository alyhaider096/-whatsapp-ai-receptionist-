import type { Config } from "tailwindcss";

function rgbVar(name: string) {
  return `rgb(var(${name}) / <alpha-value>)`;
}

const config: Config = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Geist", "sans-serif"],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 4px)",
        sm: "calc(var(--radius) - 8px)",
      },
      colors: {
        background: rgbVar("--background"),
        foreground: rgbVar("--foreground"),
        card: {
          DEFAULT: rgbVar("--card"),
          foreground: rgbVar("--card-foreground"),
        },
        popover: {
          DEFAULT: rgbVar("--popover"),
          foreground: rgbVar("--popover-foreground"),
        },
        primary: {
          DEFAULT: rgbVar("--primary"),
          foreground: rgbVar("--primary-foreground"),
        },
        secondary: {
          DEFAULT: rgbVar("--secondary"),
          foreground: rgbVar("--secondary-foreground"),
        },
        muted: {
          DEFAULT: rgbVar("--muted"),
          foreground: rgbVar("--muted-foreground"),
        },
        accent: {
          DEFAULT: rgbVar("--accent"),
          foreground: rgbVar("--accent-foreground"),
        },
        destructive: {
          DEFAULT: rgbVar("--destructive"),
          foreground: rgbVar("--destructive-foreground"),
        },
        border: rgbVar("--border"),
        input: rgbVar("--input"),
        ring: rgbVar("--ring"),

        // Material 3 surface scale + semantic roles (custom UI, not shadcn)
        surface: rgbVar("--surface"),
        "surface-container-lowest": rgbVar("--surface-container-lowest"),
        "surface-container-low": rgbVar("--surface-container-low"),
        "surface-container": rgbVar("--surface-container"),
        "surface-container-high": rgbVar("--surface-container-high"),
        "surface-container-highest": rgbVar("--surface-container-highest"),
        outline: rgbVar("--outline"),
        "outline-variant": rgbVar("--outline-variant"),
        "on-surface": rgbVar("--on-surface"),
        "on-surface-variant": rgbVar("--on-surface-variant"),
        "primary-container": rgbVar("--primary-container"),
        "on-primary-container": rgbVar("--on-primary-container"),
        "on-primary-fixed-variant": rgbVar("--on-primary-fixed-variant"),
        tertiary: rgbVar("--tertiary"),
        "tertiary-container": rgbVar("--tertiary-container"),
        "on-tertiary": rgbVar("--on-tertiary"),
        "error-container": rgbVar("--error-container"),
        "on-error-container": rgbVar("--on-error-container"),
      },
    },
  },
  plugins: [],
};
export default config;
