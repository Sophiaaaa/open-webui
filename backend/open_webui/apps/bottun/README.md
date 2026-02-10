# KPI Bot

A MySQL-based Q&A Chatbot integrated into Open WebUI.

## Features

- **Natural Language Query**: Supports asking questions about KPIs (e.g., "Show me headcount for FY25").
- **Automatic Parameter Extraction**: Extracts KPI, Time Range, and Scope (Product, Org, Tool) from queries.
- **Interactive UI**:
  - Prompts user for missing parameters using buttons and dropdowns.
  - Supports cascading filters for Scopes.
  - Visualizes results with Charts.
  - Provides Excel/CSV download for detailed data.
- **Configurable**: Fully driven by YAML configurations in `config/`.

## Architecture

- **Backend**: FastAPI app mounted at `/bottun`.
  - `services.py`: Core logic for Config, DB, AI, and Charts.
  - `main.py`: API endpoints.
- **Frontend**: SvelteKit page at `src/routes/(app)/bottun`.
  - `ParameterSelector.svelte`: Complex UI for parameter selection.
  - `ChatBubble.svelte`: Renders chat messages and interactive elements.

## Configuration

Located in `backend/open_webui/apps/bottun/config/`:
- `db_config.yaml`: Database connection settings.
- `kpi_config.yaml`: SQL templates, KPI definitions, and allowed scopes.
- `ui_mappings.yaml`: UI labels and hierarchy for the frontend.
- `bot_config.yaml`: Bot profile settings.

## Usage

1. Navigate to `/bottun` in the browser.
2. Type a question (e.g., "查询 headcount") or use the quick start buttons.
3. If parameters are missing, use the UI to select them.
4. View the result summary, chart, and download the detailed report.

## Development

- **Add new KPI**:
  1. Add definition in `kpi_config.yaml` (SQL template, allowed scopes).
  2. Add UI mapping in `ui_mappings.yaml` (Level 2 list).
- **Modify DB**: Update `db_config.yaml`.
