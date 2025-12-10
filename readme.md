# Google ADK Learning

This repository is dedicated to learning and experimenting with the Google Agent Development Kit (ADK).

## Project Structure

The project currently contains the following agent implementations:

```text
.
├── my_agent/           # Single test agent implementation (Weather Agent)
│   ├── __init__.py
│   ├── .env
│   └── agent.py
├── agent_team/         # Agent team implementation with runner and session management
│   ├── agents/         # Agent definitions
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── greeting_farewell.py
│   │   └── root.py
│   ├── __init__.py
│   ├── .env
│   ├── conversation.py
│   └── setup.py
├── loop_agent/         # Loop agent implementation for document scanning
│   ├── __init__.py
│   ├── .env
│   └── agent.py
├── .gitignore
└── readme.md
```
