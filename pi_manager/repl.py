import asyncio
import os
import shlex
import shutil
import subprocess
from io import StringIO

from prompt_toolkit import Application
from prompt_toolkit.application import run_in_terminal
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML, ANSI, FormattedText
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.margins import ScrollbarMargin
from prompt_toolkit.widgets import TextArea
from rich.console import Console
from rich.table import Table

from .config import CONFIG_DIR, load_config, save_config, first_run_setup, add_project, remove_project

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COMMANDS = [
    "status", "services", "logs", "restart", "ssh", "deploy",
    "config", "project", "setup", "shutdown", "reboot",
    "uninstall", "help", "clear", "exit", "quit",
]

HELP_TABLE = [
    ("status", "Show Pi system status (CPU, RAM, disk, temp, uptime)"),
    ("services", "Show status of all monitored services"),
    ("logs", "Show Apache error logs"),
    ("logs --live", "Stream logs in real-time (use pi logs --live from CLI)"),
    ("restart <service>", "Restart a service on the Pi"),
    ("restart all", "Restart all monitored services"),
    ("ssh", "Open SSH in a new Terminal window"),
    ("deploy <name>", "Deploy a project (rsync + cache purge)"),
    ("config", "Show current configuration"),
    ("project add", "Add a new deploy project"),
    ("project list", "List configured projects"),
    ("project remove <name>", "Remove a project"),
    ("setup", "Re-run the setup wizard"),
    ("shutdown", "Shut down the Pi"),
    ("reboot", "Reboot the Pi"),
    ("uninstall", "Uninstall PiManager"),
    ("clear", "Clear the output"),
    ("help", "Show this help"),
    ("exit / quit", "Exit PiManager"),
]

# Commands that need direct terminal access (interactive prompts)
INTERACTIVE_COMMANDS = {"setup", "shutdown", "reboot", "uninstall"}

# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------

_app: Application | None = None
_config: dict = {}
_output_text: str = ""
_busy: bool = False

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _term_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def _make_console() -> Console:
    """Create a Console that captures output to a StringIO buffer."""
    return Console(
        file=StringIO(),
        force_terminal=True,
        width=max(_term_width() - 4, 40),
    )


def _patch_consoles(cap: Console):
    """Replace console objects in command modules. Returns a restore function."""
    import pi_manager.monitor as _mon
    import pi_manager.services as _svc
    import pi_manager.deploy as _dep
    import pi_manager.ssh as _ssh

    modules = [_mon, _svc, _dep, _ssh]
    saved = {}
    for m in modules:
        if hasattr(m, "console"):
            saved[m] = m.console
            m.console = cap

    def restore():
        for m, c in saved.items():
            m.console = c

    return restore


# ---------------------------------------------------------------------------
# UI rendering
# ---------------------------------------------------------------------------


def _get_header() -> HTML:
    host = _config.get("pi_host", "not configured")
    user = _config.get("pi_user", "?")
    return HTML(
        "\n"
        '  <b>PiManager</b> <style fg="ansibrightblack">v0.1.0</style>\n'
        f'  <style fg="ansibrightblack">Connected to</style> <ansicyan>{user}@{host}</ansicyan>\n'
    )


def _get_hint() -> HTML:
    return HTML(
        '  <style fg="ansibrightblack">Type </style>'
        "<b>help</b>"
        '<style fg="ansibrightblack"> for commands, </style>'
        "<b>exit</b>"
        '<style fg="ansibrightblack"> to quit</style>'
    )


def _get_output():
    if not _output_text:
        return HTML('  <style fg="ansibrightblack">Type a command to get started...</style>')
    try:
        return ANSI(_output_text)
    except Exception:
        return FormattedText([("", _output_text)])


# ---------------------------------------------------------------------------
# Command dispatch (captured — output goes to the TUI output area)
# ---------------------------------------------------------------------------


def _dispatch_captured(args: list[str]) -> str:
    """Dispatch a command, capture all rich output, return as ANSI string."""
    global _config

    cap = _make_console()
    restore = _patch_consoles(cap)

    try:
        cmd = args[0]
        rest = args[1:]

        from .ssh import SSHError

        try:
            if cmd == "help":
                table = Table(show_header=True, header_style="bold cyan", show_edge=False, pad_edge=False)
                table.add_column("Command", style="bold white", min_width=24)
                table.add_column("Description")
                for c, desc in HELP_TABLE:
                    table.add_row(c, desc)
                cap.print(table)

            elif cmd == "status":
                from .monitor import show_status
                show_status(_config)

            elif cmd == "services":
                from .monitor import show_services
                show_services(_config)

            elif cmd == "logs":
                from .monitor import show_logs
                live = "--live" in rest
                if live:
                    cap.print("[yellow]Live streaming is not supported in the REPL.[/yellow]")
                    cap.print("[dim]Use [bold]pi logs --live[/bold] from your terminal instead.[/dim]")
                else:
                    lines = 30
                    for i, a in enumerate(rest):
                        if a in ("-n", "--lines") and i + 1 < len(rest):
                            try:
                                lines = int(rest[i + 1])
                            except ValueError:
                                pass
                    show_logs(_config, live=False, lines=lines)

            elif cmd == "restart":
                from .services import restart_service, restart_all
                if not rest:
                    cap.print("[yellow]Usage: restart <service|all>[/yellow]")
                elif rest[0] == "all":
                    restart_all(_config)
                else:
                    restart_service(_config, rest[0])

            elif cmd == "ssh":
                from .ssh import open_ssh_session
                open_ssh_session(_config)

            elif cmd == "deploy":
                from .deploy import deploy
                if not rest:
                    cap.print("[yellow]Usage: deploy <project-name>[/yellow]")
                else:
                    deploy(_config, rest[0])

            elif cmd == "config":
                _show_config(cap)

            elif cmd == "project":
                if not rest:
                    cap.print("[yellow]Usage: project add|list|remove <name>[/yellow]")
                elif rest[0] == "list":
                    _project_list(cap)
                elif rest[0] == "remove":
                    if len(rest) < 2:
                        cap.print("[yellow]Usage: project remove <name>[/yellow]")
                    else:
                        _project_remove(rest[1], cap)
                elif rest[0] == "add":
                    # Interactive — handled separately, should not reach here
                    cap.print("[yellow]Opening interactive prompt...[/yellow]")
                else:
                    cap.print(f"[yellow]Unknown subcommand: project {rest[0]}[/yellow]")

            else:
                cap.print(f"[red]Unknown command:[/red] {cmd}")
                cap.print("[dim]Type [bold]help[/bold] to see available commands.[/dim]")

        except SSHError as e:
            cap.print(f"[red]{e}[/red]")
        except Exception as e:
            cap.print(f"[red]Error: {e}[/red]")
    finally:
        restore()

    cap.file.seek(0)
    return cap.file.read()


def _show_config(cap: Console) -> None:
    table = Table(title="PiManager Config", show_header=True, header_style="bold cyan")
    table.add_column("Setting", style="bold")
    table.add_column("Value")
    table.add_row("Pi host", _config.get("pi_host", ""))
    table.add_row("Pi user", _config.get("pi_user", ""))
    table.add_row("SSH key", _config.get("ssh_key_path", ""))
    cf_token = _config.get("cloudflare_api_token", "")
    if cf_token:
        masked = cf_token[:4] + "..." + cf_token[-4:] if len(cf_token) > 8 else "****"
    else:
        masked = "(not set)"
    table.add_row("Cloudflare token", masked)
    services_list = _config.get("services", [])
    table.add_row("Services", ", ".join(services_list) if services_list else "(none)")
    projects = _config.get("projects", {})
    table.add_row("Projects", ", ".join(projects.keys()) if projects else "(none)")
    cap.print(table)


def _project_list(cap: Console) -> None:
    projects = _config.get("projects", {})
    if not projects:
        cap.print("[yellow]No projects configured. Use 'project add' to add one.[/yellow]")
        return
    table = Table(title="Projects", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Local path")
    table.add_column("Remote path")
    table.add_column("CF zone")
    for name, info in projects.items():
        zone = info.get("cloudflare_zone_id", "")
        table.add_row(name, info.get("local_path", ""), info.get("remote_path", ""), zone or "-")
    cap.print(table)


def _project_remove(name: str, cap: Console) -> None:
    if remove_project(_config, name):
        cap.print(f"[green]Project '{name}' removed.[/green]")
    else:
        cap.print(f"[red]Project '{name}' not found.[/red]")
        projects = _config.get("projects", {})
        if projects:
            cap.print(f"Available: {', '.join(projects.keys())}")


# ---------------------------------------------------------------------------
# Interactive command handlers (run in real terminal, not captured)
# ---------------------------------------------------------------------------


def _run_setup() -> None:
    global _config
    _config = first_run_setup()


def _run_project_add() -> None:
    import click
    console = Console()
    name = click.prompt("Project name")
    if name in _config.get("projects", {}):
        console.print(f"[yellow]Project '{name}' already exists.[/yellow]")
        return
    local_path = click.prompt("Local path (folder to sync)")
    remote_path = click.prompt("Remote path on Pi (e.g. /var/www/my-site/)")
    cf_zone = click.prompt("Cloudflare zone ID (leave empty to skip)", default="")
    add_project(_config, name, local_path, remote_path, cloudflare_zone_id=cf_zone)
    console.print(f"[green]Project '{name}' added.[/green]")


def _run_uninstall() -> None:
    import click
    console = Console()
    if not click.confirm("This will delete your config and uninstall PiManager. Continue?"):
        return
    if CONFIG_DIR.exists():
        shutil.rmtree(CONFIG_DIR)
        console.print("[green]Config removed (~/.pi-manager)[/green]")
    console.print("[cyan]Uninstalling via pipx...[/cyan]")
    subprocess.run(["pipx", "uninstall", "pi-manager"])


# ---------------------------------------------------------------------------
# Input handler
# ---------------------------------------------------------------------------


def _on_accept(buff) -> None:
    """Called when the user presses Enter in the input area."""
    global _output_text, _busy

    text = buff.text.strip()
    if not text:
        return

    try:
        args = shlex.split(text)
    except ValueError as e:
        _output_text = f"\033[31mParse error: {e}\033[0m\n"
        _app.invalidate()
        return

    cmd = args[0]

    # Exit
    if cmd in ("exit", "quit"):
        _app.exit()
        return

    # Clear
    if cmd == "clear":
        _output_text = ""
        _app.invalidate()
        return

    # Don't allow concurrent commands
    if _busy:
        _output_text = "\033[33mCommand still running, please wait...\033[0m\n"
        _app.invalidate()
        return

    # Interactive commands need real terminal access
    is_interactive = cmd in INTERACTIVE_COMMANDS or (
        cmd == "project" and len(args) > 1 and args[1] == "add"
    )

    if is_interactive:
        _busy = True

        async def run_interactive():
            global _busy, _output_text

            handler = {
                "setup": _run_setup,
                "shutdown": lambda: __import__("pi_manager.services", fromlist=["shutdown_pi"]).shutdown_pi(_config),
                "reboot": lambda: __import__("pi_manager.services", fromlist=["reboot_pi"]).reboot_pi(_config),
                "uninstall": _run_uninstall,
            }

            func = handler.get(cmd, _run_project_add)

            try:
                await run_in_terminal(func)
            except Exception as e:
                _output_text = f"\033[31mError: {e}\033[0m\n"
            finally:
                _busy = False
                _app.invalidate()

        _app.create_background_task(run_interactive())
        return

    # Non-interactive: capture output in background thread
    _busy = True
    _output_text = "\033[33mRunning...\033[0m\n"
    _app.invalidate()

    async def run_captured():
        global _output_text, _busy
        loop = asyncio.get_event_loop()
        try:
            output = await loop.run_in_executor(None, lambda: _dispatch_captured(args))
            _output_text = output
        except Exception as e:
            _output_text = f"\033[31mError: {e}\033[0m\n"
        finally:
            _busy = False
            _app.invalidate()

    _app.create_background_task(run_captured())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def start_repl() -> None:
    """Start the interactive PiManager REPL."""
    global _app, _config

    _config = load_config()
    if not _config:
        _config = first_run_setup()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # --- Layout ---

    header_window = Window(
        content=FormattedTextControl(_get_header),
        height=4,
        dont_extend_height=True,
    )

    hint_window = Window(
        content=FormattedTextControl(_get_hint),
        height=1,
        dont_extend_height=True,
    )

    separator = Window(height=1, char="\u2500", style="class:separator")

    output_window = Window(
        content=FormattedTextControl(_get_output, focusable=False),
        wrap_lines=True,
        right_margins=[ScrollbarMargin(display_arrows=True)],
    )

    completer = WordCompleter(COMMANDS, ignore_case=True)
    history_file = CONFIG_DIR / "history"

    input_area = TextArea(
        height=1,
        prompt=HTML("<b><skyblue>pi</skyblue></b> <b>&gt;</b> "),
        multiline=False,
        completer=completer,
        history=FileHistory(str(history_file)),
        accept_handler=_on_accept,
    )

    body = HSplit([
        header_window,
        hint_window,
        separator,
        output_window,
        separator,
        input_area,
    ])

    layout = Layout(body, focused_element=input_area)

    # --- Key bindings ---

    kb = KeyBindings()

    @kb.add("c-c")
    @kb.add("c-d")
    def _exit(event):
        event.app.exit()

    # --- Application ---

    _app = Application(
        layout=layout,
        key_bindings=kb,
        full_screen=True,
        mouse_support=False,
    )

    _app.run()
