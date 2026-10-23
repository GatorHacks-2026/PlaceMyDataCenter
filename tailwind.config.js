/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          900: '#0a0f1c',
          800: '#0f1626',
          700: '#162033',
          600: '#1e2a40',
        },
        teal: {
          accent: '#2dd4bf',
        },
      },
    },
  },
  plugins: [],
}
