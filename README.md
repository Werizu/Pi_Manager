# PiManager

A command-line tool for managing one or more Raspberry Pis from macOS. Deploy websites, monitor system health, restart services, view logs, and SSH into your Pis — all from a single `pi` command with an interactive REPL.

## Features

- **Multi-Pi support** — manage multiple Raspberry Pis from one tool, switch between them with `use`
- **Numbered selection** — pick Pis, projects, and services by number instead of typing names
- **Interactive REPL** — type `pi` and stay in a persistent shell with tab-completion and command history
- **One-shot CLI** — run `pi status` or `pi deploy my-site` directly from your terminal for scripting
- **Self-updating** — run `pi update` to pull the latest version and reinstall
- **System monitoring** — CPU, RAM, disk, temperature, uptime at a glance
- **Service management** — check status, start, stop, or restart individual services or all at once
- **Log viewing** — tail Apache error logs, with optional real-time streaming
- **One-command deploys** — rsync to Pi, restart Apache, purge Cloudflare cache
- **SSH** — opens in a new Terminal.app window so the REPL stays running
- **Setup wizard** — generates SSH keys, copies them to the Pi, tests the connection
- **Backwards-compatible** — old single-Pi configs are automatically migrated

## Requirements

- macOS (uses Terminal.app for SSH windows)
- Python 3.10+
- [pipx](https://pypa.github.io/pipx/) (recommended) or pip
- One or more Raspberry Pis with SSH enabled

## Installation

```bash
# Install pipx if you don't have it
brew install pipx

# Clone the repo (use SSH if you have it set up)
git clone https://github.com/Werizu/Pi-WebHost-Manager.git
cd Pi-WebHost-Manager

# Install
pipx install .
```

The `pi` command is now available globally in your terminal.

## Quick start

```bash
pi
```

On first run a setup wizard walks you through:

1. Pi name (e.g. `homepi`, `mediaserver`)
2. IP address / hostname and username
3. SSH key generation (stored safely in `~/.pi-manager/keys/`, not in the project directory)
4. Copying the public key to your Pi
5. Which services to monitor (defaults: `apache2`, `mariadb`, `cloudflared`)
6. Option to add more Pis
7. Cloudflare setup — same account for all Pis or separate tokens per Pi
8. Deploy projects (local path, remote path, target Pi, Cloudflare zone ID per project)

The wizard tests the SSH connection for each Pi and tells you if something's wrong. Re-run anytime with `setup` (REPL) or `pi setup` (CLI).

## Usage

### Interactive mode (REPL)

Run `pi` with no arguments to enter the interactive shell:

```
$ pi
  PiManager  v0.2.2
  2 Pis: homepi(192.168.1.100) · mediaserver(192.168.1.101)

  Type help for commands, exit to quit
─────────────────────────────────────

pi > use                 # numbered Pi selection:
                         #   1) homepi (192.168.1.100)
                         #   2) mediaserver (192.168.1.101)
                         #   0) Cancel
                         # > 2
pi > status              # shows all Pis
pi > deploy              # numbered project selection
pi > restart             # numbered service selection
pi > status --pi homepi  # explicit Pi via flag
pi > list-pis
pi > update              # self-update from git
pi > exit
```

Features:
- **Tab completion** for all commands
- **Command history** persisted in `~/.pi-manager/history` (arrow keys to navigate)
- **Styled prompt** powered by prompt\_toolkit

### One-shot mode (CLI)

Pass a command directly for scripting or quick use:

```bash
pi status                    # all Pis
pi status --pi homepi        # specific Pi
pi deploy my-site            # uses Pi from project config
pi deploy my-site --pi mediaserver  # override target Pi
pi services --pi homepi
pi stop apache2 --pi homepi  # stop a service
pi start apache2             # start a service
pi ping                      # check all Pis reachable
pi ping --pi homepi          # check specific Pi
pi update                    # self-update from git
pi list-pis
pi add-pi
```

### Commands

| Command | Description |
|---|---|
| `status` | Show system status for all Pis (or `--pi <name>` for one) |
| `services` | Show service status for all Pis (or `--pi <name>` for one) |
| `logs` | Show last 30 lines of Apache error log |
| `logs -n 100` | Show more lines |
| `logs --live` | Stream logs in real-time (Ctrl+C to stop) |
| `restart` | Numbered service selection, then restart |
| `restart <service>` | Restart a specific service |
| `restart all` | Restart all monitored services |
| `stop` | Numbered service selection, then stop |
| `stop <service>` | Stop a specific service |
| `start` | Numbered service selection, then start |
| `start <service>` | Start a specific service |
| `ping` | Check if all Pis are reachable via SSH (with response time) |
| `ssh` | Open SSH in a new Terminal.app window |
| `deploy` | Numbered project selection, then deploy |
| `deploy <name>` | Deploy a specific project (rsync + cache purge) |
| `list-pis` | List all configured Pis |
| `add-pi` | Add a new Pi interactively |
| `remove-pi <name>` | Remove a Pi |
| `use` | Numbered Pi selection to set active Pi |
| `use <pi-name>` | Set active Pi by name |
| `config` | Show current configuration |
| `add-project` | Add a new deploy project (numbered Pi/folder selection) |
| `list-projects` | List all configured projects |
| `remove-project <name>` | Remove a project |
| `setup` | Re-run the setup wizard |
| `update` | Update PiManager to the latest version from git |
| `shutdown` | Shut down the active Pi (asks for confirmation) |
| `reboot` | Reboot the active Pi (asks for confirmation) |
| `uninstall` | Remove config and uninstall PiManager |
| `help` | Show all available commands |
| `exit` / `quit` | Exit the REPL |

All commands that target a specific Pi accept `--pi <name>` for scripting. Without it:
- `status`, `services`, and `ping` show **all Pis**
- `use`, `deploy`, `restart`, `stop`, and `start` without arguments show a **numbered selection list**
- Other commands use the **active Pi** (set via `use`) or the **default Pi**

## Configuration

All config and keys are stored in `~/.pi-manager/`:

```
~/.pi-manager/
├── config.json     # Main configuration
├── keys/           # SSH keys (generated during setup)
│   ├── id_rsa
│   └── id_rsa.pub
└── history         # REPL command history
```

Example `config.json`:

```json
{
  "pis": {
    "homepi": {
      "host": "192.168.1.100",
      "user": "pi",
      "ssh_key_path": "~/.pi-manager/keys/id_rsa",
      "services": ["apache2", "mariadb", "cloudflared"]
    },
    "mediaserver": {
      "host": "192.168.1.101",
      "user": "pi",
      "ssh_key_path": "~/.pi-manager/keys/id_rsa",
      "services": ["plex", "samba"],
      "cloudflare_api_token": "separate-token-if-different-account"
    }
  },
  "default_pi": "homepi",
  "cloudflare_api_token": "global-token-for-all-pis",
  "projects": {
    "my-site": {
      "local_path": "/Users/you/Sites/my-site/",
      "remote_path": "/var/www/my-site/",
      "pi": "homepi",
      "cloudflare_zone_id": "zone-id-for-my-site"
    },
    "blog": {
      "local_path": "/Users/you/Sites/blog/",
      "remote_path": "/var/www/blog/",
      "pi": "homepi",
      "cloudflare_zone_id": "different-zone-id-for-blog"
    }
  }
}
```

- **`cloudflare_api_token`** (global) — used for all Pis by default
- **`cloudflare_api_token`** (per-Pi, optional) — overrides the global token if a Pi uses a different Cloudflare account
- **`cloudflare_zone_id`** — always per project, since one Pi can host multiple sites with different zones

**Migration:** If you're upgrading from v0.1.0, your old single-Pi config is automatically migrated to the new format on first load. No manual changes needed.

You can edit the file directly or use `pi setup` / `pi add-project` / `pi add-pi`.

## Deploy workflow

When you run `deploy <name>`, PiManager:

1. **Resolves the target Pi** — from `--pi` flag, project config, active Pi, or default
2. **Rsyncs** the local project folder to the Pi (excludes `.git`, `.DS_Store`, `node_modules`)
3. **Restarts Apache** on the Pi
4. **Purges Cloudflare cache** (if a zone ID and API token are configured)

## Project structure

```
pi-manager/
├── pi_manager/
│   ├── __init__.py
│   ├── cli.py          # Click entry point, routes to REPL or one-shot
│   ├── repl.py         # Interactive REPL (prompt_toolkit + rich)
│   ├── config.py       # Config loading, saving, setup wizard, multi-Pi helpers
│   ├── ssh.py          # SSH connection, remote commands, Terminal.app integration
│   ├── monitor.py      # System status, services, log viewing
│   ├── services.py     # Service start, stop, restart, shutdown, reboot
│   └── deploy.py       # Rsync deploy + Cloudflare cache purge
├── pyproject.toml
└── README.md
```

## Dependencies

| Package | Purpose |
|---|---|
| [click](https://click.palletsprojects.com/) | CLI framework and one-shot command parsing |
| [rich](https://rich.readthedocs.io/) | Tables, panels, styled terminal output |
| [paramiko](https://www.paramiko.org/) | SSH connections and remote command execution |
| [prompt\_toolkit](https://python-prompt-toolkit.readthedocs.io/) | Interactive REPL with history and tab-completion |
| [requests](https://requests.readthedocs.io/) | Cloudflare API calls |

## FAQ

**Where is the config stored?**
`~/.pi-manager/config.json`. Edit it directly or use `pi setup` / `pi add-project`.

**Where are the SSH keys stored?**
In `~/.pi-manager/keys/`. This keeps them out of any project directory so they can't accidentally be committed to git.

**Can I manage multiple Pis?**
Yes. Run `pi add-pi` to add more Pis at any time, or add them during `pi setup`. Use `pi list-pis` to see all configured Pis. In the REPL, `use <name>` switches the active Pi for the session.

**How does Pi resolution work for commands?**
1. Explicit `--pi <name>` always wins
2. For `deploy`: falls back to the project's configured `pi` field
3. In the REPL: falls back to the active Pi set via `use`
4. Finally falls back to `default_pi` from the config

**I upgraded from v0.1.0 — do I need to change my config?**
No. PiManager automatically migrates old configs to the new multi-Pi format. Your existing Pi becomes `pi` (the default name).

**How do I change my SSH key path?**
Run `pi setup` to reconfigure, or edit `ssh_key_path` in the config file.

**How do I get a Cloudflare API token?**
Go to the [Cloudflare dashboard](https://dash.cloudflare.com/profile/api-tokens) and create a token with **Zone > Cache Purge > Purge** permission. Add it during setup or edit the config file.

**Can I deploy multiple websites?**
Yes. Run `add-project` for each site (assign each to a Pi), then `deploy <name>` to deploy individually.

**How do I monitor custom services?**
Enter your services as a comma-separated list during setup, or edit the `services` array per Pi in the config file.

**SSH opens in a new window — can I use the current terminal instead?**
In one-shot mode (`pi ssh`) SSH also opens in a new Terminal.app window. This is by design so the REPL stays usable. For an inline session, run `ssh -i ~/.pi-manager/keys/id_rsa pi@your-pi-ip` directly.

**Connection issues?**
- *"Can't reach the Pi"* — check that the Pi is powered on and the IP is correct
- *"SSH key rejected"* — run `pi setup` to regenerate and recopy the key
- *"Connection timed out"* — verify your network connection

## Updating

The easiest way to update:

```bash
pi update
```

This pulls the latest changes from git, reinstalls via pipx, and shows a changelog. Your config and SSH keys in `~/.pi-manager/` are never touched.

On first run, `update` asks for the path to your local git clone and remembers it.

Manual update (same thing, just by hand):

```bash
cd Pi_Manager
git pull
pipx install . --force
```

## Uninstalling

From the REPL:
```
pi > uninstall
```

Or manually:
```bash
pipx uninstall pi-manager
rm -rf ~/.pi-manager
```

## License

MIT
