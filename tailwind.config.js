/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: { colors: { brand: { DEFAULT: '#B5262E', dark: '#8E1B22', light: '#FBECEC' } } } },
  plugins: [],
}
