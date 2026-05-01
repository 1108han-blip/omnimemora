/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        background: '#0B0F14',
        surface: '#0F151D',
        panel: '#111923',
        border: '#1F2A37',
        muted: '#8B96A6',
        foreground: '#E5EAF0',
        accent: '#6D7CFF',
        cyan: '#35D7FF',
        success: '#39D98A',
        warning: '#F5B84B',
        danger: '#FF5D73',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'SFMono-Regular', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        focus: '0 0 0 1px rgba(109,124,255,.55)',
      },
    },
  },
  plugins: [],
};
