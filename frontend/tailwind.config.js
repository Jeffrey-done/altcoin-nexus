/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', '"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'ui-monospace', 'monospace'],
        display: ['"Plus Jakarta Sans"', '"Inter"', 'system-ui', 'sans-serif'],
      },
      colors: {
        // 机构级深色板
        terminal: {
          DEFAULT: '#0a0e1a',   // 最深背景
          surface: '#0f1424',   // 卡片背景
          raised: '#151b2e',    // 浮起元素
          border: '#1e2740',    // 边框
          muted: '#2a3352',     // 禁用/暗色元素
        },
        // 哑光金 - 机构金融标配
        gold: {
          50: '#fefce8',
          100: '#fef9c3',
          200: '#fef08a',
          300: '#fde047',
          400: '#facc15',
          500: '#d4a853',       // 主金色
          600: '#b8922e',
          700: '#9a7b1f',
          800: '#7c6318',
          900: '#5e4b12',
        },
        // 冷蓝灰 - 辅助
        steel: {
          50: '#f8fafc',
          100: '#e2e8f0',
          200: '#cbd5e1',
          300: '#94a3b8',
          400: '#64748b',
          500: '#475569',
          600: '#334155',
          700: '#1e293b',
          800: '#0f172a',
          900: '#020617',
        },
        // PnL 色彩 - 机构级（低饱和）
        gain: '#22c55e',
        loss: '#ef4444',
        flat: '#64748b',
      },
      fontSize: {
        'display': ['2.5rem', { lineHeight: '1', letterSpacing: '-0.04em', fontWeight: '700' }],
        'heading': ['1.5rem', { lineHeight: '1.2', letterSpacing: '-0.03em', fontWeight: '600' }],
        'subheading': ['1rem', { lineHeight: '1.4', letterSpacing: '-0.01em', fontWeight: '600' }],
        'label': ['0.6875rem', { lineHeight: '1', letterSpacing: '0.08em', fontWeight: '500' }],
        'data': ['0.8125rem', { lineHeight: '1.4', fontWeight: '500' }],
        'data-lg': ['1.25rem', { lineHeight: '1.2', fontWeight: '700' }],
        'data-xl': ['1.75rem', { lineHeight: '1.1', fontWeight: '700' }],
      },
      borderRadius: {
        'card': '0.5rem',
        'button': '0.375rem',
      },
      transitionTimingFunction: {
        'institutional': 'cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        'ticker': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(212, 168, 83, 0)' },
          '50%': { boxShadow: '0 0 12px 0 rgba(212, 168, 83, 0.15)' },
        },
      },
      animation: {
        'ticker': 'ticker 2s ease-in-out infinite',
        'slide-up': 'slide-up 0.5s cubic-bezier(0.16, 1, 0.3, 1) both',
        'fade-in': 'fade-in 0.4s ease both',
        'pulse-glow': 'pulse-glow 3s ease-in-out infinite',
      },
      boxShadow: {
        'card': '0 1px 3px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(255, 255, 255, 0.03)',
        'card-hover': '0 4px 12px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(212, 168, 83, 0.1)',
        'glow-gold': '0 0 20px rgba(212, 168, 83, 0.15)',
        'glow-blue': '0 0 20px rgba(56, 189, 248, 0.15)',
        'inner': 'inset 0 1px 0 rgba(255, 255, 255, 0.03)',
      },
    },
  },
  plugins: [],
}