export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        neurolens: {
          bg: '#09090B',
          surface: '#18181B',
          surfaceHover: '#1F1F23',
          border: '#27272A',
          borderHover: '#3F3F46',
          textPrimary: '#FAFAFA',
          textSecondary: '#A1A1AA',
          textMuted: '#71717A',
          badgeEstablished: '#FFFFFF',
          badgeEstablishedText: '#000000',
          badgeMeasured: '#3F3F46',
          badgeMeasuredText: '#FFFFFF',
          badgeExploratory: 'transparent',
          badgeExploratoryBorder: '#FAFAFA',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Monaco', 'monospace'],
      },
      fontSize: {
        'display': ['3.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em', fontWeight: '700' }],
        'headline': ['1.5rem', { lineHeight: '1.3', letterSpacing: '-0.01em', fontWeight: '600' }],
        'title': ['1.125rem', { lineHeight: '1.4', fontWeight: '500' }],
        'body': ['1rem', { lineHeight: '1.6' }],
        'small': ['0.875rem', { lineHeight: '1.5' }],
        'tiny': ['0.75rem', { lineHeight: '1.5' }],
      },
      spacing: {
        'panel': '1.5rem',
        'panel-sm': '1rem',
        'panel-lg': '2rem',
      },
      borderRadius: {
        'panel': '0.5rem',
        'badge': '9999px',
      },
      boxShadow: {
        'panel': '0 1px 3px 0 rgb(0 0 0 / 0.3), 0 1px 2px -1px rgb(0 0 0 / 0.2)',
        'panel-hover': '0 4px 6px -1px rgb(0 0 0 / 0.3), 0 2px 4px -2px rgb(0 0 0 / 0.2)',
      },
    },
  },
  plugins: [],
}
