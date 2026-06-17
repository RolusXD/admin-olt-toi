import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#f7f8fb",
        foreground: "#17202a",
        primary: "#006b5f",
        accent: "#d6a84f",
        danger: "#b42318",
        warning: "#b54708",
        muted: "#667085",
      },
      boxShadow: {
        panel: "0 1px 2px rgba(16, 24, 40, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
