/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          bg: "#15130F",
          surface: "#1E1B16",
          raised: "#262119",
          border: "#362F24",
          "border-strong": "#453B2C",
        },
        ink: {
          DEFAULT: "#F1EDE4",
          muted: "#96897A",
          faint: "#6B6154",
        },
        amber: {
          DEFAULT: "#E3953C",
          dim: "#8C5A25",
          bright: "#F4B667",
        },
        teal: {
          DEFAULT: "#3FCDB0",
          dim: "#1E5E51",
        },
        critical: {
          DEFAULT: "#E5555A",
          dim: "#6E2629",
        },
        steel: {
          DEFAULT: "#7C93B0",
        },
      },
      fontFamily: {
        sans: ["Archivo", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "6px",
        lg: "10px",
      },
    },
  },
  plugins: [],
};
