# NET-1 — Offline Knowledge System

Personal note : this is a vibe codded project with potential flaws and bugs, please review the project in detail before considering to launch

> *Knowledge should be resilient. NET-1 is a small step toward information self-sufficiency.*

NET-1 is a self-hosted knowledge hub designed to run on your own server or computer. Once completely configured, it provides you  persistent, local access to a curated collection of human knowledge independent of the internet.

The core idea is simple: in an increasingly connected world, we are entirely dependent on internet access for information. NET-1 challenges that dependency by letting you back up critical knowledge locally — Wikipedia, textbooks, travel guides, classic literature, repair manuals, and scientific research — all searchable and queryable through a local LLM, with no cloud required.

In scenarios where internet infrastructure fails — whether through natural disaster, power grid disruption, geopolitical events, or simply living off-grid — NET-1 becomes your network's library. Set it up on a RSBC or any Linux server, connect devices over a local network, and anyone on that network can search, read, prompt the AI, take notes, and access your PDF collection.

---

## Features

### Knowledge Base
- Full-text search across **Wikipedia**, **Wikibooks**, **Wikivoyage**, **Project Gutenberg**, **iFixit** and **arXiv**
- Intelligent query routing — repair questions go to iFixit, travel queries go to Wikivoyage, research queries go to arXiv
- Article reader with paper-style Kindle theme and dark mode

### Local LLM Chat
- Conversational AI powered by **Ollama** — runs entirely on your hardware
- Context-aware responses drawing from your local knowledge library
- Persistent chat history per user stored in Valkey
- Switch between installed models from the System page
- Supports any Ollama-compatible model (qwen3, llama3, phi4, gemma3 and more)

### PDF Library
- Upload and organise PDF files in your local library
- Tag-based filtering and organising
- Auto-generated cover thumbnails
- In-browser PDF reader

### Notes
- Rich text note editor powered by Quill
- Private, shared, and public visibility per note
- Tag system with custom icons and colours
- Note sharing with specific users on the network
- Comments and @mentions
- Pin notes for quick access

### System Management *(admin only)*
- Data sync — download and parse knowledge sources (sample or full)
- LLM management — pull, switch and delete Ollama models
- User management — create, activate, deactivate and delete users
- Role system — User, Staff, Superuser

### Monitoring *(staff only)*
- Real-time CPU, RAM and disk usage charts
- Custom date range filtering for resource history
- Live user sessions
- Full activity log with user and action filters

---

## Requirements

- Linux (Ubuntu 22.04+ recommended)
- [Podman](https://podman.io/) + [podman-compose](https://github.com/containers/podman-compose)
- `make`
- 8GB+ RAM min recommended (for LLM inference)
- 50GB+ disk space recommended (for extensive knowledge dumps and models)

---

## Initial Setup

### 1. Clone the repository

```bash
git clone https://github.com/starshipjourney/net-1.git
cd net-1
```

### 2. Configure your environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
nano .env
```

At minimum set these values:

```env
# Generate a secure key:
# python3 -c "import secrets; print(secrets.token_urlsafe(50))"
SECRET_KEY=your-long-random-secret-key

DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=net1db
DB_USER=net1user
DB_PASSWORD=your-strong-database-password
DB_HOST=postgres
DB_PORT=5432

VALKEY_HOST=valkey
VALKEY_PORT=6379

OLLAMA_HOST=http://ollama:11434
```

### 3. Build and start

```bash
make setup
```

This will:
- Build the Django container image
- Pull Postgres, Valkey and Ollama images
- Start all four containers
- Run database migrations automatically
- Collect static files

### 4. Create your admin account

```bash
make superuser
```

Follow the prompts to set your username and password.

### 5. Pull an LLM model

```bash
podman exec net1-ollama ollama pull qwen3:8b
```

Recommended models by hardware:

| Hardware | Recommended model |
|----------|------------------|
| 8GB RAM  | `qwen3:1.7b` or `gemma3:1b` |
| 16GB RAM | `qwen3:8b` or `phi4-mini` |
| 32GB RAM | `qwen3:14b` or `llama3.2` |

### 6. Visit the app

Open your browser and go to:

```
http://localhost:8000
```

Log in with the superuser account you created.

### 7. Sync your first knowledge source

1. Go to **SYSTEM** page
2. Select a source (start with **Wikipedia** in **SAMPLE** mode for a quick test)
3. Click **START SYNC**

A full Wikipedia sync will take several hours and requires significant disk space. Sample mode downloads a small subset for testing.

---

## Daily Usage

```bash
# Start all containers
make up

# Stop all containers
make down

# View logs
make logs-app

# Open Django shell
make shell

# Run a management command
make bash
# then: python manage.py <command>
```

---

## Project Structure

```
net-1/
├── .env.example          # Environment variable template
├── .gitignore
├── Makefile              # Common commands
├── podman-compose.yml    # Container orchestration
├── main/                 # Django application
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── core/             # Settings, URLs
│   ├── interface/        # Templates, static files
│   ├── data_master/      # Knowledge base, LLM, PDF library
│   ├── notes/            # Notes application
│   └── system_logger/    # Monitoring, user management
└── data/                 # Runtime data (not in git)
    ├── db/               # Postgres and Valkey data
    ├── dumps/            # Downloaded knowledge source files
    ├── ollama/           # LLM model files
    ├── pdfs/             # Your PDF library
    └── static/           # Collected static files
```

---

## Knowledge Sources

| Source | Content | Full size |
|--------|---------|-----------|
| Wikipedia | Encyclopaedia articles | ~22GB |
| Wikibooks | Free textbooks | ~3GB |
| Wikivoyage | Travel guides | ~1GB |
| Project Gutenberg | Classic literature | ~70GB |
| iFixit | Repair and how-to guides | ~2GB |
| arXiv | Scientific research abstracts | ~4GB |

> Start with sample mode to test. Full downloads are large and can take several hours.

---

## License

MIT — free to use, modify and distribute.

---

## Author

Built by [starshipjourney](https://github.com/starshipjourney) as a personal project in self-sufficiency and offline resilience.
