// ── NET-1 GLOBAL THEME SYSTEM ────────────────────────────────────

const NET1_THEMES = {

    // ════════════════════════════════════════
    //  DARK THEMES
    // ════════════════════════════════════════

    'crimson-ice': {
        label: 'Crimson Ice',
        desc:  'Crimson red meets electric cyan on deep black',
        dark:  true,
        preview: ['#080002', '#dc143c', '#00e5ff'],
        vars: {
            '--t-bg':         '#080002', '--t-bg2':        '#0d0005',
            '--t-surface':    '#120008', '--t-surface2':   '#1a000c',
            '--t-border':     '#3a0018', '--t-border-hi':  '#5a0028',
            '--t-text':       '#f0e8eb', '--t-text-dim':   '#c084a0',
            '--t-text-mute':  '#5a2035',
            '--t-accent':     '#dc143c', '--t-accent-dim': '#8b0020',
            '--t-accent2':    '#00e5ff',
            '--t-amber':      '#ff8c00', '--t-green':      '#00e5ff',
            '--t-blue':       '#00e5ff', '--t-red':        '#ff4444',
        }
    },

    'dark-slate': {
        label: 'Dark Slate',
        desc:  'GitHub-style slate with amber and blue accents',
        dark:  true,
        preview: ['#0d1117', '#f59e0b', '#58a6ff'],
        vars: {
            '--t-bg':         '#0d1117', '--t-bg2':        '#010409',
            '--t-surface':    '#161b22', '--t-surface2':   '#21262d',
            '--t-border':     '#21262d', '--t-border-hi':  '#30363d',
            '--t-text':       '#e6edf3', '--t-text-dim':   '#8b949e',
            '--t-text-mute':  '#484f58',
            '--t-accent':     '#f59e0b', '--t-accent-dim': '#92400e',
            '--t-accent2':    '#58a6ff',
            '--t-amber':      '#f59e0b', '--t-green':      '#3fb950',
            '--t-blue':       '#58a6ff', '--t-red':        '#f85149',
        }
    },

    'deep-ocean': {
        label: 'Deep Ocean',
        desc:  'Midnight blue with teal and violet',
        dark:  true,
        preview: ['#050d1a', '#00d4aa', '#a78bfa'],
        vars: {
            '--t-bg':         '#050d1a', '--t-bg2':        '#020810',
            '--t-surface':    '#0a1628', '--t-surface2':   '#0f1f35',
            '--t-border':     '#1a3050', '--t-border-hi':  '#254570',
            '--t-text':       '#d4e8f5', '--t-text-dim':   '#7aa8c8',
            '--t-text-mute':  '#2a4060',
            '--t-accent':     '#00d4aa', '--t-accent-dim': '#007a60',
            '--t-accent2':    '#a78bfa',
            '--t-amber':      '#fbbf24', '--t-green':      '#00d4aa',
            '--t-blue':       '#60b0f0', '--t-red':        '#f87171',
        }
    },

    'forest': {
        label: 'Forest',
        desc:  'Deep green with gold and moss',
        dark:  true,
        preview: ['#080f08', '#78a800', '#d4a017'],
        vars: {
            '--t-bg':         '#080f08', '--t-bg2':        '#040804',
            '--t-surface':    '#0f1a0f', '--t-surface2':   '#162416',
            '--t-border':     '#1e3020', '--t-border-hi':  '#2e4830',
            '--t-text':       '#d8e8d0', '--t-text-dim':   '#88a878',
            '--t-text-mute':  '#2e4830',
            '--t-accent':     '#78a800', '--t-accent-dim': '#3a5400',
            '--t-accent2':    '#d4a017',
            '--t-amber':      '#d4a017', '--t-green':      '#78a800',
            '--t-blue':       '#5090a0', '--t-red':        '#c84040',
        }
    },

    'neon-tokyo': {
        label: 'Neon Tokyo',
        desc:  'Dark charcoal with hot pink and electric lime',
        dark:  true,
        preview: ['#0e0e14', '#ff2d78', '#c8ff00'],
        vars: {
            '--t-bg':         '#0e0e14', '--t-bg2':        '#08080e',
            '--t-surface':    '#16161e', '--t-surface2':   '#1e1e28',
            '--t-border':     '#2e2040', '--t-border-hi':  '#4a3060',
            '--t-text':       '#f0eeff', '--t-text-dim':   '#a090c0',
            '--t-text-mute':  '#4a3860',
            '--t-accent':     '#ff2d78', '--t-accent-dim': '#8b0040',
            '--t-accent2':    '#c8ff00',
            '--t-amber':      '#ff9900', '--t-green':      '#c8ff00',
            '--t-blue':       '#00d4ff', '--t-red':        '#ff4466',
        }
    },

    'aurora': {
        label: 'Aurora',
        desc:  'Dark navy with shifting green, purple and gold',
        dark:  true,
        preview: ['#060d18', '#00ffaa', '#b060ff'],
        vars: {
            '--t-bg':         '#060d18', '--t-bg2':        '#030810',
            '--t-surface':    '#0b1425', '--t-surface2':   '#101c30',
            '--t-border':     '#182840', '--t-border-hi':  '#243858',
            '--t-text':       '#e0f4ec', '--t-text-dim':   '#70b090',
            '--t-text-mute':  '#203840',
            '--t-accent':     '#00ffaa', '--t-accent-dim': '#007a50',
            '--t-accent2':    '#b060ff',
            '--t-amber':      '#ffd060', '--t-green':      '#00ffaa',
            '--t-blue':       '#4090ff', '--t-red':        '#ff6070',
        }
    },

    'obsidian-gold': {
        label: 'Obsidian Gold',
        desc:  'Pure black with rich gold and warm copper',
        dark:  true,
        preview: ['#0a0a0a', '#d4a017', '#c87040'],
        vars: {
            '--t-bg':         '#0a0a0a', '--t-bg2':        '#050505',
            '--t-surface':    '#111111', '--t-surface2':   '#1a1a1a',
            '--t-border':     '#2a2010', '--t-border-hi':  '#4a3818',
            '--t-text':       '#f0e8d8', '--t-text-dim':   '#b0987a',
            '--t-text-mute':  '#4a3820',
            '--t-accent':     '#d4a017', '--t-accent-dim': '#6a5008',
            '--t-accent2':    '#c87040',
            '--t-amber':      '#d4a017', '--t-green':      '#70a840',
            '--t-blue':       '#6088c0', '--t-red':        '#c05040',
        }
    },

    'synthwave': {
        label: 'Synthwave',
        desc:  'Retro purple-black with magenta and cyan',
        dark:  true,
        preview: ['#110820', '#ff00cc', '#00ffff'],
        vars: {
            '--t-bg':         '#110820', '--t-bg2':        '#0a0418',
            '--t-surface':    '#1a1030', '--t-surface2':   '#221840',
            '--t-border':     '#3a1860', '--t-border-hi':  '#5a2880',
            '--t-text':       '#f8e8ff', '--t-text-dim':   '#c080e0',
            '--t-text-mute':  '#5a2870',
            '--t-accent':     '#ff00cc', '--t-accent-dim': '#800068',
            '--t-accent2':    '#00ffff',
            '--t-amber':      '#ffaa00', '--t-green':      '#00ff88',
            '--t-blue':       '#00ffff', '--t-red':        '#ff3366',
        }
    },

    // ════════════════════════════════════════
    //  LIGHT THEMES
    // ════════════════════════════════════════

    'moonlight': {
        label: 'Moonlight',
        desc:  'Clean white with cool silver blue and indigo',
        dark:  false,
        preview: ['#f0f2f8', '#4a6fa5', '#7c4dcc'],
        vars: {
            '--t-bg':         '#f0f2f8', '--t-bg2':        '#e8ebf4',
            '--t-surface':    '#ffffff', '--t-surface2':   '#eef0f8',
            '--t-border':     '#cdd3e8', '--t-border-hi':  '#a0aed0',
            '--t-text':       '#1e2440', '--t-text-dim':   '#4a5580',
            '--t-text-mute':  '#9aa0c0',
            '--t-accent':     '#4a6fa5', '--t-accent-dim': '#d0d8f0',
            '--t-accent2':    '#7c4dcc',
            '--t-amber':      '#c07a20', '--t-green':      '#2a8050',
            '--t-blue':       '#4a6fa5', '--t-red':        '#b03030',
        }
    },

    'sunrise': {
        label: 'Sunrise',
        desc:  'Warm cream with terracotta, gold and sage',
        dark:  false,
        preview: ['#fdf6ed', '#c4622d', '#e8a030'],
        vars: {
            '--t-bg':         '#fdf6ed', '--t-bg2':        '#f7ede0',
            '--t-surface':    '#ffffff', '--t-surface2':   '#fef0e0',
            '--t-border':     '#e8d0b8', '--t-border-hi':  '#d0a880',
            '--t-text':       '#2c1a0e', '--t-text-dim':   '#7a4a2a',
            '--t-text-mute':  '#c0a080',
            '--t-accent':     '#c4622d', '--t-accent-dim': '#f5e0d0',
            '--t-accent2':    '#e8a030',
            '--t-amber':      '#e8a030', '--t-green':      '#5a8a40',
            '--t-blue':       '#3a6888', '--t-red':        '#b83030',
        }
    },

    'sakura': {
        label: 'Sakura',
        desc:  'Soft pink blossom with rose, moss and lavender',
        dark:  false,
        preview: ['#fdf2f5', '#c0527a', '#7060c0'],
        vars: {
            '--t-bg':         '#fdf2f5', '--t-bg2':        '#f8e8ee',
            '--t-surface':    '#ffffff', '--t-surface2':   '#fdeef3',
            '--t-border':     '#f0cdd8', '--t-border-hi':  '#e0a8be',
            '--t-text':       '#2a1020', '--t-text-dim':   '#804060',
            '--t-text-mute':  '#c898b0',
            '--t-accent':     '#c0527a', '--t-accent-dim': '#fce0ea',
            '--t-accent2':    '#7060c0',
            '--t-amber':      '#c07830', '--t-green':      '#5a8040',
            '--t-blue':       '#5878a8', '--t-red':        '#b83050',
        }
    },

    'sand-dune': {
        label: 'Sand Dune',
        desc:  'Warm parchment with ochre, clay and burnt sienna',
        dark:  false,
        preview: ['#f5f0e8', '#a07840', '#c05030'],
        vars: {
            '--t-bg':         '#f5f0e8', '--t-bg2':        '#ede5d8',
            '--t-surface':    '#fdfaf5', '--t-surface2':   '#f0e8d8',
            '--t-border':     '#ddd0b8', '--t-border-hi':  '#c0a878',
            '--t-text':       '#28200e', '--t-text-dim':   '#705030',
            '--t-text-mute':  '#b89870',
            '--t-accent':     '#a07840', '--t-accent-dim': '#ecdfc8',
            '--t-accent2':    '#c05030',
            '--t-amber':      '#c89050', '--t-green':      '#607840',
            '--t-blue':       '#486880', '--t-red':        '#a04030',
        }
    },

    'mint-fresh': {
        label: 'Mint Fresh',
        desc:  'Crisp white with mint green and coral orange',
        dark:  false,
        preview: ['#f2faf6', '#1a9e6a', '#f06040'],
        vars: {
            '--t-bg':         '#f2faf6', '--t-bg2':        '#e8f5ee',
            '--t-surface':    '#ffffff', '--t-surface2':   '#edf8f2',
            '--t-border':     '#c0e0d0', '--t-border-hi':  '#90c8b0',
            '--t-text':       '#0e2820', '--t-text-dim':   '#3a6850',
            '--t-text-mute':  '#90b8a4',
            '--t-accent':     '#1a9e6a', '--t-accent-dim': '#c8eedd',
            '--t-accent2':    '#f06040',
            '--t-amber':      '#d08820', '--t-green':      '#1a9e6a',
            '--t-blue':       '#3070b0', '--t-red':        '#d04040',
        }
    },

    'lavender-mist': {
        label: 'Lavender Mist',
        desc:  'Soft lavender with violet, rose gold and sage',
        dark:  false,
        preview: ['#f4f0fc', '#7048c8', '#c07898'],
        vars: {
            '--t-bg':         '#f4f0fc', '--t-bg2':        '#ece6f8',
            '--t-surface':    '#ffffff', '--t-surface2':   '#f0ebfc',
            '--t-border':     '#d8ccf0', '--t-border-hi':  '#b8a8e0',
            '--t-text':       '#1e1030', '--t-text-dim':   '#5a4080',
            '--t-text-mute':  '#a890cc',
            '--t-accent':     '#7048c8', '--t-accent-dim': '#e8e0f8',
            '--t-accent2':    '#c07898',
            '--t-amber':      '#b07828', '--t-green':      '#507858',
            '--t-blue':       '#4060b0', '--t-red':        '#b04060',
        }
    },

};

const NET1_THEME_DEFAULT = 'dark-slate';

function net1ApplyTheme(name) {
    const theme = NET1_THEMES[name] || NET1_THEMES[NET1_THEME_DEFAULT];
    const root  = document.documentElement;
    root.setAttribute('data-theme', name);
    root.classList.toggle('theme-light', theme.dark === false);
    Object.entries(theme.vars).forEach(([k, v]) => root.style.setProperty(k, v));
    localStorage.setItem('net1-theme', name);
}

function net1GetTheme() {
    return localStorage.getItem('net1-theme') || NET1_THEME_DEFAULT;
}

// Apply immediately on load (before paint — no flash)
net1ApplyTheme(net1GetTheme());