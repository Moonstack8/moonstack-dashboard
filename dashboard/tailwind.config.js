/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f4ff',
          100: '#e0e9ff',
          500: '#3b5bdb',
          600: '#3451c7',
          700: '#2c44b0',
          900: '#1a2a6e',
        },
        // Semantic theme tokens — driven by CSS variables in index.css
        surface:  'rgb(var(--bg-surface)  / <alpha-value>)',
        elevated: 'rgb(var(--bg-elevated) / <alpha-value>)',
        ink:      'rgb(var(--color-ink)   / <alpha-value>)',
        rim:      'var(--border-subtle)',
        'rim-2':  'var(--border-default)',
      },
    },
  },
  plugins: [],
}

