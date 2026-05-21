/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50:  '#f0fafa',
          100: '#cceff0',
          500: '#01696f',
          600: '#015f65',
          700: '#014d52',
          800: '#013d41',
        },
        surface: '#f9f8f5',
        muted: '#7a7974',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
