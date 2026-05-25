/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./core/templates/**/*.html",
    "./tools/**/*.html",
  ],
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        apik: {
          "primary":         "#6B6FBF",
          "primary-content": "#ffffff",
          "secondary":       "#2C3355",
          "secondary-content": "#ffffff",
          "accent":          "#7575C8",
          "neutral":         "#2C3355",
          "neutral-content": "#ffffff",
          "base-100":        "#ffffff",
          "base-200":        "#f4f5f8",
          "base-300":        "#e8eaf0",
          "base-content":    "#1e2337",
          "info":            "#3b82f6",
          "success":         "#22c55e",
          "warning":         "#f59e0b",
          "error":           "#ef4444",
        },
      },
    ],
  },
}
