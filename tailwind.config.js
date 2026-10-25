/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: 'rgb(var(--surface-base) / <alpha-value>)',
          800: 'rgb(var(--surface-card) / <alpha-value>)',
          700: 'rgb(var(--surface-raised) / <alpha-value>)',
          600: 'rgb(var(--surface-border) / <alpha-value>)',
        },
        teal: {
          accent: 'rgb(var(--accent) / <alpha-value>)',
        },
      },
    },
  },
  plugins: [],
}
