// ── NET-1 GLOBAL THEME SYSTEM ────────────────────────────────────
// Loaded on every page. Applies CSS variables to <html> based on
// the saved theme in localStorage.

const NET1_THEMES = {

    'crimson-ice': {
        label: 'Crimson Ice',
        desc:  'Deep black with crimson and cyan — the original',
        preview: ['#080002', '#dc143c', '#00e5ff'],
        vars: {
            '--t-bg':          '#080002',
            '--t-bg2':         '#0d0005',
            '--t-surface':     '#120008',
            '--t-surface2':    '#1a000c',
            '--t-border':      '#3a0018',
            '--t-border-hi':   '#5a0028',
            '--t-text':        '#f0e8eb',
            '--t-text-dim':    '#c084a0',
            '--t-text-mute':   '#5a2035',
            '--t-accent':      '#dc143c',
            '--t-accent-dim':  '#8b0020',
            '--t-accent2':     '#00e5ff',
            '--t-amber':       '#dc143c',
            '--t-green':       '#00e5ff',
            '--t-blue':        '#00e5ff',
            '--t-red':         '#ff4444',
        }
    },

    'dark-slate': {
        label: 'Dark Slate',
        desc:  'Deep slate with amber — the notes theme',
        preview: ['#0d1117', '#f59e0b', '#58a6ff'],
        vars: {
            '--t-bg':          '#0d1117',
            '--t-bg2':         '#010409',
            '--t-surface':     '#161b22',
            '--t-surface2':    '#21262d',
            '--t-border':      '#21262d',
            '--t-border-hi':   '#30363d',
            '--t-text':        '#e6edf3',
            '--t-text-dim':    '#8b949e',
            '--t-text-mute':   '#484f58',
            '--t-accent':      '#f59e0b',
            '--t-accent-dim':  '#92400e',
            '--t-accent2':     '#58a6ff',
            '--t-amber':       '#f59e0b',
            '--t-green':       '#3fb950',
            '--t-blue':        '#58a6ff',
            '--t-red':         '#f85149',
        }
    },

    'deep-ocean': {
        label: 'Deep Ocean',
        desc:  'Midnight blue with teal and violet',
        preview: ['#050d1a', '#00d4aa', '#a78bfa'],
        vars: {
            '--t-bg':          '#050d1a',
            '--t-bg2':         '#020810',
            '--t-surface':     '#0a1628',
            '--t-surface2':    '#0f1f35',
            '--t-border':      '#1a3050',
            '--t-border-hi':   '#254570',
            '--t-text':        '#d4e8f5',
            '--t-text-dim':    '#7aa8c8',
            '--t-text-mute':   '#2a4060',
            '--t-accent':      '#00d4aa',
            '--t-accent-dim':  '#007a60',
            '--t-accent2':     '#a78bfa',
            '--t-amber':       '#00d4aa',
            '--t-green':       '#00d4aa',
            '--t-blue':        '#60b0f0',
            '--t-red':         '#f87171',
        }
    },

    'forest': {
        label: 'Forest',
        desc:  'Dark green with gold and moss',
        preview: ['#080f08', '#78a800', '#d4a017'],
        vars: {
            '--t-bg':          '#080f08',
            '--t-bg2':         '#040804',
            '--t-surface':     '#0f1a0f',
            '--t-surface2':    '#162416',
            '--t-border':      '#1e3020',
            '--t-border-hi':   '#2e4830',
            '--t-text':        '#d8e8d0',
            '--t-text-dim':    '#88a878',
            '--t-text-mute':   '#2e4830',
            '--t-accent':      '#78a800',
            '--t-accent-dim':  '#3a5400',
            '--t-accent2':     '#d4a017',
            '--t-amber':       '#d4a017',
            '--t-green':       '#78a800',
            '--t-blue':        '#5090a0',
            '--t-red':         '#c84040',
        }
    },

};

const NET1_THEME_DEFAULT = 'dark-slate';

function net1ApplyTheme(name) {
    const theme = NET1_THEMES[name] || NET1_THEMES[NET1_THEME_DEFAULT];
    const root  = document.documentElement;
    root.setAttribute('data-theme', name);
    Object.entries(theme.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    localStorage.setItem('net1-theme', name);
}

function net1GetTheme() {
    return localStorage.getItem('net1-theme') || NET1_THEME_DEFAULT;
}

// Apply immediately on load (before paint to avoid flash)
net1ApplyTheme(net1GetTheme());