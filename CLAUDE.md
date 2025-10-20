# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

## Project Overview

WhaleBots is a gaming bot platform that provides automation for mobile games, specifically:
- Rise of Kingdoms Bot (ROKBot.exe)
- Call of Dragons Bot

The platform is built with compiled executables (.exe) and dynamic link libraries (.dll) that interface with Android emulators to automate gameplay.

## Architecture

### Core Components
- **WhaleBots.exe** - Main launcher application (192KB)
- **WhaleBots.dll** - Core bot engine library (8MB)
- **Apps/** - Individual game bot modules
  - `rise-of-kingdoms-bot/` - Rise of Kingdoms automation
  - `call-of-dragons-bot/` - Call of Dragons automation

### Configuration Structure
- **Settings/Users.json** - User authentication and installation settings
- **Apps/*/manifest.json** - Bot module configuration
- **Apps/*/Settings/Accounts.json** - Game account and emulator configurations
- **Apps/*/Localized/*.ini** - Localization files for different languages

### Bot Configuration
Each bot supports extensive automation features:
- Resource gathering and management
- Troop training and deployment
- Building construction and upgrades
- Research progression
- Alliance activities
- PvP and PvE combat
- Mail and report processing

## Development Notes

### Running the Application
Execute `WhaleBots.exe` to launch the main bot platform. Individual bots are launched through the main interface.

### Configuration Management
- Bot settings are stored in JSON format
- Localization files use INI format
- User credentials are encrypted in Settings/Users.json

### Emulator Integration
The platform integrates with Android emulators (BlueStacks mentioned in configuration) to:
- Launch game instances
- Control gameplay through automated actions
- Monitor game state and respond to events

### OpenSpec Integration
This project uses OpenSpec for specification-driven development. See `openspec/AGENTS.md` for detailed instructions on:
- Creating change proposals
- Managing specifications
- Following the three-stage workflow (Create → Implement → Archive)

## Important Notes

- This is a compiled application without visible source code
- Configuration files contain sensitive user data (encrypted credentials)
- The platform appears to be commercial bot software for mobile gaming
- No build scripts or development dependencies are present