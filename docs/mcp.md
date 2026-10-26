# The MCP server: Claude and other AI apps

An AI app, such as Claude Code, can read this project and the running ROS graph through
a small server, `tools/mcp_server.py`. It only reads. MCP (the Model Context Protocol) is
how AI apps talk to tools like this one.

```
AI app ──stdio──► mcp_server.py ──► the docs and contracts (files in git)
                                ──► the ROS graph: list it, read one message
```

## What it can do

| Tool | What it does |
|---|---|
| `list_pages`, `read_page`, `search_pages` | the docs, the README, `CLAUDE.md`, `TODO.md`, and the three contracts |
| `contract` | `docs/interfaces.yaml`: a summary, or one topic, service, action, frame or node |
| `repo_status` | the branch, the last 10 commits, and the uncommitted files |
| `ros_graph` | the running nodes, topics and services, and who publishes and subscribes |
| `read_topic` | one message from a topic. Long arrays, such as images, are cut short |
| `check_contract` | the running graph against the contract, like `pixi run check` |
| `run_tests` | `tools/test.sh`: the tests that don't need ROS |

## What it can't do

- **Write to ROS:** no publishing, no service or action calls, no parameters. So it can't
  move the car. A test checks that the server's code has none of those calls. Driving
  has a server of its own, with its own rules: [Plain English](plain-english.md).
- **Read files outside git:** it never sees `secrets.h`, `vendor/`, or anything else that
  isn't committed.
- **Change files:** the only thing it writes is `run_tests`' build output, which git
  ignores.

## Connect Claude Code

1. Once: `pixi run build`, then `pixi install -e mcp`.
2. Start Claude Code in the repo folder. It finds `.mcp.json`, which lists two servers:
   `aav` (this one, read-only) and `aav-drive` (it drives the stand-ins:
   [Plain English](plain-english.md#claude-as-the-driver)). Say yes to `aav`.
3. Type `/mcp` to check: `aav` should say connected.

## Connect another app

Give the app the command that starts the server, with full paths:

```json
{
  "mcpServers": {
    "aav": {
      "command": "/Users/you/.pixi/bin/pixi",
      "args": ["run", "--manifest-path", "/Users/you/ecolo-av/pixi.toml",
               "--frozen", "-e", "mcp", "mcp"]
    }
  }
}
```

That's Claude Desktop's `claude_desktop_config.json`. Other apps ask for the same command
and arguments. The server talks over stdio, so it runs only on the computer the app is on.

## Which ROS network it sees

The server uses the ROS settings it was started with.

| Started with | It sees |
|---|---|
| The default settings, on the car's network | the car |
| `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` | only this computer, such as the stand-ins |
| Another `ROS_DOMAIN_ID` | only that domain |

- `ros_graph` and `check_contract` print the domain and the range on their first line.
- To change them, set them before starting the app, or add an `env` block to
  `.mcp.json`.

## How it's tested

| Test | What it checks |
|---|---|
| `tools/tests/test_mcp_parts.py` | which files it offers, short names, search, the contract, the QoS rule, and that the server has no call that writes to ROS |
| `tools/tests/mcp_smoke.py` | starts the server the way an app does, lists its 9 tools, reads a page, and reads one message from a stand-in publisher, on a ROS domain of its own |

`pixi run test` runs both. The smoke test needs the `mcp` environment: it's skipped where
that isn't installed. CI installs it.
