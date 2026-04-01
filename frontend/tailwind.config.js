/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: '#22c55e',
          dark: '#16a34a',
          light: '#4ade80',
        },
        surface: {
          DEFAULT: '#0f172a',
          card: '#1e293b',
          border: '#334155',
          hover: '#273447',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}
