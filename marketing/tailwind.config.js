/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#0B0F14',
        'ink-raised': '#12181F',
        paper: '#FAF9F6',
        sand: '#F1EFE9',
        teal: {
          DEFAULT: '#0D9488',
          dark: '#0B7A70',
          soft: '#0D948814',
        },
        amber: {
          DEFAULT: '#D9822B',
          soft: '#D9822B1a',
        },
      },
      fontFamily: {
        serif: ['Fraunces', 'ui-serif', 'Georgia', 'serif'],
        sans: ['"IBM Plex Sans"', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      maxWidth: {
        content: '1180px',
      },
    },
  },
  plugins: [],
};
