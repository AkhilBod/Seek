import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070607",
        coal: "#111012",
        ember: "#e3343f",
        oxblood: "#7f121b",
        smoke: "#a9a4aa"
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(227, 52, 63, 0.26), 0 22px 80px rgba(227, 52, 63, 0.14)"
      }
    }
  },
  plugins: []
};

export default config;
