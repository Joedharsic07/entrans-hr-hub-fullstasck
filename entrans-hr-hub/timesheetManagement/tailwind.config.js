/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{html,ts}"],
  theme: {
    extend: {
      colors: {
        'primary':       '#1F3A5F',
        'primary-hover': '#14263F',
        'secondary':     '#F5F5F5',
        'accent':        '#E2A512',
        'success':       '#10B981',
        'error':         '#EF4444',
        'warning':       '#F59E0B',
        'gray-light':    '#F5F5F5',
        'gray-border':   '#E5E7EB',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        'page-title':    ['32px', { lineHeight: '1.15', letterSpacing: '-0.025em', fontWeight: '700' }],
        'section-title': ['20px', { lineHeight: '1.3',  letterSpacing: '-0.015em', fontWeight: '600' }],
        'card-title':    ['18px', { lineHeight: '1.4',  fontWeight: '600' }],
      },
      boxShadow: {
        'xs': '0 1px 2px 0 rgba(15,23,42,0.05)',
        'soft': '0 2px 8px 0 rgba(15,23,42,0.06), 0 1px 2px -1px rgba(15,23,42,0.04)',
        'card': '0 1px 3px 0 rgba(15,23,42,0.08), 0 1px 2px -1px rgba(15,23,42,0.05)',
        'card-hover': '0 4px 6px -1px rgba(15,23,42,0.08), 0 2px 4px -2px rgba(15,23,42,0.05)',
        'modal': '0 20px 40px -8px rgba(15,23,42,0.15), 0 8px 16px -4px rgba(15,23,42,0.08)',
      },
      borderRadius: {
        'sm': '6px',
        'DEFAULT': '8px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
        '2xl': '20px',
        '3xl': '24px',
      },
      transitionDuration: {
        '120': '120ms',
        '180': '180ms',
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.4, 0, 0.2, 1)',
        'spring': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      keyframes: {
        'fade-in-up': {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'scale-in': {
          '0%':   { opacity: '0', transform: 'scale(0.96)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in-up': 'fade-in-up 200ms cubic-bezier(0.4,0,0.2,1) both',
        'scale-in':   'scale-in 180ms cubic-bezier(0.34,1.56,0.64,1) both',
      },
    },
  },
  plugins: [],
}

