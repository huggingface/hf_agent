import { createTheme } from '@mui/material/styles';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#FEE133',
      light: '#FFF066',
      dark: '#B29F24',
    },
    secondary: {
      main: '#FF9D00',
    },
    background: {
      default: '#0D1117',
      paper: '#161B22',
    },
    text: {
      primary: '#E6EDF3',
      secondary: '#8B949E',
    },
    divider: '#30363D',
    success: {
      main: '#2EA043', // Muted green
    },
    error: {
      main: '#F85149',
    },
    warning: {
      main: '#D29922',
    },
    info: {
      main: '#58A6FF',
    },
  },
  typography: {
    fontFamily: '"IBM Plex Sans", "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    h1: {
      fontWeight: 600,
    },
    h2: {
      fontWeight: 600,
    },
    h3: {
      fontWeight: 600,
    },
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
    body1: {
      fontSize: '0.9375rem',
    },
    body2: {
      fontSize: '0.875rem',
    },
    button: {
      fontFamily: '"JetBrains Mono", "IBM Plex Sans", monospace',
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
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
          fontFamily: '"JetBrains Mono", "Fira Code", monospace',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'uppercase',
          fontWeight: 600,
          letterSpacing: '0.05em',
          fontSize: '0.75rem',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderRight: '1px solid #30363D',
        },
      },
    },
  },
  shape: {
    borderRadius: 2,
  },
});

export default theme;
