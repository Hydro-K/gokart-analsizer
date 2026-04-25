/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg:      '#0d1b2a',
        surface: '#112233',
        border:  '#1a2a3a',
        accent:  '#00BFFF',
        orange:  '#FF8800',
        green:   '#00FF88',
        red:     '#FF4444',
        gold:    '#FFD700',
      },
    },
  },
  plugins: [],
}
