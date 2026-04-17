/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      // Paleta base — los derivados del acento se aplican via CSS variables
      // en runtime (ver src/lib/theme.js). Aqui solo dejamos el neutral.
      colors: {
        bg: {
          0: 'hsl(230, 10%, 4%)',
          1: 'hsl(230, 10%, 7%)',
          2: 'hsl(230, 10%, 10%)',
          3: 'hsl(230, 10%, 13%)',
        },
        fg: {
          1: 'hsl(220, 15%, 96%)',
          2: 'hsl(220, 10%, 70%)',
          3: 'hsl(220, 10%, 48%)',
          4: 'hsl(220, 10%, 32%)',
        },
        border: {
          DEFAULT: 'hsl(230, 10%, 15%)',
          strong: 'hsl(230, 10%, 22%)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
