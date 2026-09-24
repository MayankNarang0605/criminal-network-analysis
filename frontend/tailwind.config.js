/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        // CrimeNet design system — adapted from Thxrun's CSS variables
        bg: {
          0: '#070a12',
          1: '#0c111e',
          2: '#101728',
        },
        surface: {
          DEFAULT: '#141d33',
          hover: '#192542',
          active: '#1f2e52',
        },
        accent: {
          DEFAULT: '#00d2ff',
          secondary: '#6366f1',
          glow: 'rgba(0,210,255,0.28)',
        },
        crimenet: {
          red: '#f43f5e',
          amber: '#f59e0b',
          green: '#10b981',
          cyan: '#06b6d4',
          danger: '#ef4444',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      borderRadius: {
        DEFAULT: '16px',
        sm: '10px',
      },
      boxShadow: {
        soft: '0 24px 60px -20px rgba(0,0,0,0.75)',
        card: '0 4px 24px -8px rgba(0,0,0,0.55)',
        glass: '0 12px 36px -10px rgba(0,0,0,0.55)',
      },
      backgroundImage: {
        'accent-gradient': 'linear-gradient(135deg, #00d2ff, #6366f1)',
        'danger-gradient': 'linear-gradient(135deg, #ef4444, #dc2626)',
      },
    },
  },
  plugins: [],
}
