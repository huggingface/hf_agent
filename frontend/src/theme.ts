import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#C7A500', // --accent-yellow
    },
    secondary: {
      main: '#FF9D00',
    },
    background: {
      default: '#0B0D10', // --bg
      paper: '#0F1316',   // --panel
    },
    text: {
      primary: '#E6EEF8', // --text
      secondary: '#98A0AA', // --muted-text
    },
    divider: 'rgba(255,255,255,0.03)',
    success: {
      main: '#2FCC71', // --accent-green
    },
    error: {
      main: '#E05A4F', // --accent-red
    },
    warning: {
      main: '#C7A500',
    },
    info: {
      main: '#58A6FF',
    },
  },
  typography: {
    fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
    fontSize: 15,
    h1: { fontWeight: 600, color: '#E6EEF8' },
    h2: { fontWeight: 600, color: '#E6EEF8' },
    h3: { fontWeight: 600, color: '#E6EEF8' },
    h4: { fontWeight: 600, color: '#E6EEF8' },
    h5: { fontWeight: 600, color: '#E6EEF8' },
    h6: { fontWeight: 600, color: '#E6EEF8' },
    body1: { fontSize: '15px', color: '#E6EEF8' },
    body2: { fontSize: '0.875rem', color: '#98A0AA' },
    button: {
      fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif',
      textTransform: 'none',
      fontWeight: 600,
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        ':root': {
          '--bg': '#0B0D10',
          '--panel': '#0F1316',
          '--surface': '#121416',
          '--text': '#E6EEF8',
          '--muted-text': '#98A0AA',
          '--accent-yellow': '#C7A500',
          '--accent-yellow-weak': 'rgba(199,165,0,0.08)',
          '--accent-green': '#2FCC71',
          '--accent-red': '#E05A4F',
          '--shadow-1': '0 6px 18px rgba(2,6,12,0.55)',
          '--radius-lg': '20px',
          '--radius-md': '12px',
          '--focus': '0 0 0 3px rgba(199,165,0,0.12)',
        },
        body: {
          background: 'linear-gradient(180deg, var(--bg), #090B0D)',
          color: 'var(--text)',
          scrollbarWidth: 'thin',
          '&::-webkit-scrollbar': {
            width: '8px',
            height: '8px',
          },
          '&::-webkit-scrollbar-thumb': {
            backgroundColor: '#30363D',
            borderRadius: '2px',
          },
          '&::-webkit-scrollbar-track': {
            backgroundColor: 'transparent',
          },
        },
        'code, pre': {
          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, "Roboto Mono", monospace',
        },
        '.brand-logo': {
          position: 'relative',
          padding: '6px',
          borderRadius: '8px',
          '&::after': {
            content: '""',
            position: 'absolute',
            inset: '-6px',
            borderRadius: '10px',
            background: 'var(--accent-yellow-weak)',
            zIndex: -1,
            pointerEvents: 'none',
          },
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '10px',
          fontWeight: 600,
          transition: 'transform 0.06s ease, background 0.12s ease, box-shadow 0.12s ease',
          '&:hover': {
            transform: 'translateY(-1px)',
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: 'transparent', // Default to transparent for gradients
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: 'var(--panel)',
          borderRight: '1px solid rgba(255,255,255,0.03)',
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: 'var(--radius-md)',
            '& fieldset': {
              borderColor: 'rgba(255,255,255,0.03)',
            },
            '&:hover fieldset': {
              borderColor: 'rgba(255,255,255,0.1)',
            },
            '&.Mui-focused fieldset': {
              borderColor: 'var(--accent-yellow)',
              borderWidth: '1px',
              boxShadow: 'var(--focus)',
            },
          },
        },
      },
    },
  },
  shape: {
    borderRadius: 12,
  },
});

export default theme;