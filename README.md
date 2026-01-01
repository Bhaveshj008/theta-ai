<p align="center">
  <img src="assets/full_logo.png" alt="Theta AI - The Ultimate Desktop Agent" />
</p>

<h1 align="center">Theta AI</h1>

<p align="center">
  <strong>An autonomous AI agent for desktop automation powered by large language models</strong>
</p>

<p align="center">
  <a href="https://github.com/Bhaveshj008/theta-ai/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  </a>
  <a href="https://github.com/Bhaveshj008/theta-ai/releases">
    <img src="https://img.shields.io/badge/version-0.1.0--alpha-orange.svg" alt="Version">
  </a>
  <a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python">
  </a>
  <a href="https://github.com/Bhaveshj008/theta-ai/stargazers">
    <img src="https://img.shields.io/github/stars/Bhaveshj008/theta-ai?style=social" alt="Stars">
  </a>
</p>

<p align="center">
  <em>Status: Alpha / Proof of Concept</em>
</p>

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Demo](#-demo)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Safety Features](#safety-features)
- [Performance](#-performance)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#-troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [FAQ](#-faq)
- [Built With](#️-built-with)
- [Security](#-security)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contributors](#-contributors)
- [Support](#support)

---

## Overview

Theta AI is an experimental AI agent that automates desktop tasks through a perception-planning-action loop. It uses computer vision to understand screen state, LLMs to plan actions, and integrates multiple automation tools to execute tasks across desktop applications and web browsers.

**Warning:** Theta AI can control your computer but requires user approval for sensitive operations. Use in a safe environment and supervise all actions. This is experimental software not intended for production use.

---

## Features

- Autonomous task execution via natural language commands
- Screen perception through OCR and UI element detection
- LLM-based action planning (Groq/Llama 3.3 70B)
- Multi-tool orchestration (browser, desktop apps, file system)
- Permission gates for destructive, payment, and login operations
- Voice command support with wake word detection
- Real-time overlay interface for monitoring
- Audit logging for all executed actions

---

## 🎥 Demo

### Overlay Interface
> **Note:** Demo screenshots and GIFs coming soon!

### Voice Commands
```
"Hey Theta, open notepad"
"Hey Theta, search for Python tutorials"
"Hey Theta, calculate 123 times 456"
```

### Example Tasks
- Open applications and interact with UI elements
- Automate web browsing and form filling
- Manage files and folders
- Execute system commands safely
- Voice-controlled desktop automation

---

## Architecture

<p align="center">
  <img src="assets/architecture.png" alt="Theta AI Architecture" width="100%" />
</p>

The agent operates in a continuous loop with built-in safety checks:

1. **Perceive** - Capture and analyze screen state using OCR
2. **Plan** - Use LLM to determine next action based on current state
3. **Safety Check** - Request approval for sensitive operations
4. **Execute** - Call appropriate tool to perform action
5. **Verify** - Check completion status or handle errors

---

## Prerequisites

- Python 3.10 or higher
- Windows 10/11 (for full desktop automation support)
- Groq API key (free tier available at groq.com)
- 8GB RAM minimum (16GB recommended for OCR)

---

## Installation

### 1. Clone Repository

```
git clone https://github.com/Bhaveshj008/theta-ai.git
cd theta-ai
```

### 2. Create Virtual Environment

```
python -m venv .venv
```

**Windows:**
```
.venv\Scripts\activate
```

**macOS/Linux:**
```
source .venv/bin/activate
```

### 3. Install Dependencies

```
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```
playwright install chromium
```

### 5. Configure Environment

Create a `.env` file in the project root (or copy from `.env.example`):

```
# API Keys (Required)
GROQ_API_KEY=your_groq_api_key_here
OPENROUTER_API_KEY=your_openrouter_key_here  # Optional, for vision models

# Model Configuration
AGENT_MODEL_PRIMARY=groq:llama-3.3-70b-versatile
AGENT_MODEL_FALLBACK=groq:llama-3.1-8b-instant
VISION_MODEL_PRIMARY=openrouter:nvidia/nemotron-nano-12b-v2-vl
WHISPER_MODEL=whisper-large-v3

# Safety Settings
REQUIRE_PERMISSION_FOR_DESTRUCTIVE=True
REQUIRE_PERMISSION_FOR_PAYMENT=True
REQUIRE_PERMISSION_FOR_LOGIN=True
ENABLE_AUDIT_LOG=True

# Voice Settings
ENABLE_VOICE=True
VOICE_WAKE_WORD=hey theta
```

To obtain a Groq API key:
1. Visit [console.groq.com](https://console.groq.com)
2. Sign up for free account
3. Navigate to API Keys section
4. Create new key and copy to `.env` file

---

## Usage

### Overlay Mode (Recommended)

Launch the graphical interface:

```
python -m agent.main --overlay
```

Type commands in the input field or use voice with "Hey Theta" wake word.

### Command Line Mode

Execute single task:

```
python -m agent.main "open notepad and write hello world"
```

### Interactive Mode

Enter interactive shell:

```
python -m agent.main --interactive
```

Commands are entered at the prompt:

```
> open calculator and compute 45 times 67
> search for python tutorials on bing
> quit
```

---

## Examples

### Desktop Applications
```
python -m agent.main "open notepad and write hello world"
python -m agent.main "launch calculator and calculate 123 plus 456"
python -m agent.main "open camera and take a photo"
```

### Web Browser
```
python -m agent.main "search for AI news on bing and open first result"
python -m agent.main "go to github.com"
python -m agent.main "find Python documentation and summarize"
```

### File Operations
```
python -m agent.main "create file notes.txt in workspace"
python -m agent.main "list files in workspace directory"
python -m agent.main "read todo.txt and show contents"
```

### Voice Commands (Overlay Mode)
```
"Hey Theta, open notepad"
"Hey Theta, search for python documentation"
"Hey Theta, take a screenshot"
"Hey Theta, what's on my screen"
```

---

## Configuration

Edit `agent/config.py` or use `.env` file to modify settings:

```
# LLM Configuration
AGENT_MODEL_PRIMARY = "groq:llama-3.3-70b-versatile"
AGENT_MODEL_FALLBACK = "groq:llama-3.1-8b-instant"
MAX_ITERATIONS = 50

# Workspace
WORKSPACE_DIR = Path.home() / "agent_workspace"

# Voice
ENABLE_VOICE = True
VOICE_WAKE_WORD = "hey theta"

# Safety Policies
SAFETY_POLICIES = {
    "destructive_operations": ["delete", "remove", "format", "kill"],
    "payment_operations": ["buy", "purchase", "checkout", "payment"],
    "login_operations": ["login", "signin", "password", "authenticate"]
}
```

---

## Project Structure

```
theta-ai/
├── agent/
│   ├── core/
│   │   ├── orchestrator.py       # Main agent loop
│   │   ├── llm_client.py         # LLM API integration
│   │   ├── prompts.py            # System prompts
│   │   └── state_machine.py      # State management
│   │
│   ├── tools/
│   │   ├── browser.py            # Browser automation (Playwright)
│   │   ├── ui_automation.py      # Desktop app control (pywinauto)
│   │   ├── mouse_keyboard.py     # Input simulation
│   │   ├── app_controller.py     # Application launcher
│   │   ├── filesystem.py         # File operations
│   │   ├── command_runner.py     # Shell command execution
│   │   └── base_tool.py          # Tool interface
│   │
│   ├── perception/
│   │   ├── screen_capture.py     # Screen analysis and OCR
│   │   └── voice_input.py        # Speech recognition
│   │
│   ├── planning/
│   │   └── task_planner.py       # Task decomposition
│   │
│   ├── safety/
│   │   ├── permission_gate.py    # Permission management
│   │   └── audit_log.py          # Action logging
│   │
│   ├── ui/
│   │   ├── overlay.py            # GUI interface (Tkinter)
│   │   └── overlay_agent.py      # Agent runner
│   │
│   ├── config.py                 # Configuration settings
│   └── main.py                   # Entry point
│
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Environment template
├── .gitignore
├── requirements.txt              # Python dependencies
├── LICENSE                       # MIT License
└── README.md
```

---

## Safety Features

### Permission System

Theta AI requests explicit user approval before executing sensitive operations:

**Destructive Operations**
- File deletion or removal
- System shutdowns or restarts
- Process termination
- Disk formatting operations

**Payment Operations**
- Online purchases
- Checkout processes
- Payment form submissions

**Login Operations**
- Password entry
- Authentication forms
- Account credential input

### Permission Dialog

When a sensitive action is detected, Theta AI displays an approval dialog:

**Overlay Mode:**
```
⚠️  PERMISSION REQUIRED

Action: Delete file
Description: Remove important_document.txt
Risk Level: High

[Approve] [Reject]
```

**CLI Mode:**
```
⚠️ Permission Required
Action: Delete file
Description: Remove important_document.txt
Approve this action? (y/n):
```

### Audit Logging

All actions are logged to `agent_workspace/audit_log.json` with:
- Timestamp
- Action type and parameters
- Approval status
- Execution result
- User identity (for multi-user setups)

### Additional Safety Measures

- Task iteration limit prevents infinite loops
- Loop detection identifies repeated actions
- File operations restricted to workspace directory
- Real-time action monitoring through overlay interface
- Sensitive data pattern detection (SSN, credit cards)

---

## Performance

### System Requirements
- **Minimum:** 8GB RAM, Dual-core CPU, 2GB disk space
- **Recommended:** 16GB RAM, Quad-core CPU, 5GB disk space
- **GPU:** Optional (improves OCR speed by 2-3x)

### Response Times
- **Screen perception:** 1-3 seconds (OCR + analysis)
- **LLM planning:** 2-5 seconds (Groq Llama 3.3 70B)
- **Action execution:** 0.5-2 seconds (depends on task)
- **Full iteration:** ~5-10 seconds (perception → planning → action)

### Resource Usage
- **Memory:** 500MB-2GB (depends on OCR and browser)
- **CPU:** 10-30% (spikes during OCR)
- **Network:** ~50KB per LLM request
- **Disk:** Workspace and logs grow with usage

---

## Known Limitations

- Windows-only for desktop automation (Linux/macOS support planned)
- OCR accuracy varies with screen resolution and font size
- Single task execution (no parallel processing)
- LLM planning can occasionally select incorrect actions
- Browser automation may fail on sites with complex JavaScript
- No automatic rollback of executed actions
- Voice recognition requires clear audio input

---

## Troubleshooting

### Common Issues

**Q: "ModuleNotFoundError: No module named 'agent'"**
```
# Make sure you're in the project root directory
cd theta-ai
python -m agent.main --overlay
```

**Q: "Groq API error 401: Invalid API key"**
- Check your `.env` file has `GROQ_API_KEY=your_key_here`
- Verify the key is valid at https://console.groq.com

**Q: "OCR not detecting text on screen"**
- Increase screen resolution (1920x1080 recommended)
- Ensure text is not too small (font size 10+ recommended)
- Check `USE_GPU_OCR=True` in `.env` for better accuracy

**Q: "Voice commands not working"**
- Check microphone permissions in Windows
- Verify `ENABLE_VOICE=True` in `.env`
- Say wake word clearly: "hey theta"

**Q: "pywinauto cannot find window"**
- Make sure the application is visible and not minimized
- Try running as Administrator for system applications
- Check application name matches exactly

**Q: "Playwright browser won't launch"**
```
# Reinstall Playwright browsers
playwright install chromium --force
```

### Getting Help

If you encounter issues not listed here:
1. Check [GitHub Issues](https://github.com/Bhaveshj008/theta-ai/issues)
2. Search [Discussions](https://github.com/Bhaveshj008/theta-ai/discussions)
3. Open a new issue with:
   - Error message
   - Your OS and Python version
   - Steps to reproduce

---

## Development

### Running Tests

```
pytest tests/
```

### Code Formatting

```
black agent/
isort agent/
```

### Linting

```
flake8 agent/
pylint agent/
```

---

## Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/description`)
3. Commit changes (`git commit -m 'Add feature'`)
4. Push to branch (`git push origin feature/description`)
5. Open Pull Request

### Areas for Contribution

- Cross-platform support (Linux, macOS)
- Additional tool integrations (email, calendar, Slack)
- Improved error handling and recovery
- Test coverage expansion
- Documentation improvements
- Bug fixes and performance optimizations

---

## Roadmap

### Version 0.2
- Linux and macOS desktop automation support
- Multi-tab browser management
- Enhanced error recovery mechanisms
- Comprehensive test suite

### Version 0.3
- Memory system for task history
- Plugin architecture for custom tools
- Multi-monitor support
- Advanced vision model integration

### Version 1.0
- Production-ready stability
- Enterprise security features
- Performance optimizations
- Complete documentation

---

## FAQ

### General

**Q: Is Theta AI free to use?**  
A: Yes, Theta AI is open source under MIT License. However, you need a Groq API key (free tier available).

**Q: Does it work on Mac or Linux?**  
A: Currently Windows-only. macOS and Linux support is planned for v0.2.

**Q: Can I use it without Groq API?**  
A: No, Theta AI requires LLM API access. Groq offers a free tier with generous limits.

**Q: Is my data secure?**  
A: Theta AI runs locally. Screenshots are processed locally via OCR. Only text prompts are sent to LLM APIs (Groq/OpenRouter).

### Technical

**Q: Which LLM models does it support?**  
A: Primary: Groq Llama 3.3 70B, Fallback: Groq Llama 3.1 8B, Vision: OpenRouter Nemotron 12B

**Q: Can I add custom tools?**  
A: Yes! See `agent/tools/base_tool.py` for the interface. Implement `execute()` method and register in orchestrator.

**Q: How does permission system work?**  
A: Theta AI detects sensitive operations (delete, payment, login) and pauses for user approval before executing.

**Q: Can it run multiple tasks simultaneously?**  
A: Not yet. Single task execution is current limitation. Parallel processing planned for future.

**Q: What's the token/cost usage?**  
A: Groq free tier: 30 requests/minute, ~6000 tokens/min. Typical task uses 500-2000 tokens. Very affordable!

### Safety

**Q: Can it damage my system?**  
A: Theta AI has safety gates for destructive operations and restricts file operations to workspace directory. However, always supervise and use in safe environment.

**Q: What permissions does it need?**  
A: Screen capture, keyboard/mouse control, file system access (workspace only), microphone (for voice).

**Q: Is there an undo feature?**  
A: No automatic rollback yet. Audit log tracks all actions for manual review.

---

## Built With

| Component | Technology |
|-----------|-----------|
| **LLM Provider** | [Groq](https://groq.com) (Llama 3.3 70B) |
| **Vision Model** | [OpenRouter](https://openrouter.ai) (Nemotron 12B) |
| **OCR Engine** | [EasyOCR](https://github.com/JaidedAI/EasyOCR) |
| **Browser Automation** | [Playwright](https://playwright.dev) |
| **Desktop Automation** | [pywinauto](https://github.com/pywinauto/pywinauto) |
| **Screen Capture** | [mss](https://github.com/BoboTiG/python-mss) |
| **Input Control** | [PyAutoGUI](https://pyautogui.readthedocs.io) |
| **Voice Recognition** | [Groq Whisper](https://groq.com) |
| **UI Framework** | Tkinter |
| **Async Runtime** | asyncio + aiohttp |

---

## Security

### Reporting Vulnerabilities

If you discover a security vulnerability, please email:
- **Email:** security@theta-ai.example.com
- **Response Time:** Within 48 hours

Please do not open public issues for security vulnerabilities.

### Security Best Practices

When using Theta AI:
- ✅ Review permissions before approval
- ✅ Check audit logs regularly
- ✅ Use in isolated/test environment first
- ✅ Keep API keys in `.env` (never commit)
- ✅ Run with least privileges necessary
- ❌ Don't use on production systems initially
- ❌ Don't approve operations you don't understand

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

Built with open source libraries:

- **Groq** - LLM inference
- **EasyOCR** - Text recognition
- **Playwright** - Browser automation
- **pywinauto** - Windows UI automation
- **PyAutoGUI** - Input control
- **OpenRouter** - Vision model API
- **Whisper** - Speech recognition

---

## Contributors

Thanks to all contributors who helped build Theta AI!

<a href="https://github.com/Bhaveshj008/theta-ai/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Bhaveshj008/theta-ai" />
</a>

### Core Team
- **Bhavesh Jadhav** - [@Bhaveshj008](https://github.com/Bhaveshj008) - Creator & Lead Developer

---

## Support

- **Issues:** [GitHub Issues](https://github.com/Bhaveshj008/theta-ai/issues)
- **Discussions:** [GitHub Discussions](https://github.com/Bhaveshj008/theta-ai/discussions)
- **Documentation:** [Wiki](https://github.com/Bhaveshj008/theta-ai/wiki)

---

## ⭐ Star History

If you find Theta AI useful, please consider giving it a star! ⭐

[![Star History Chart](https://api.star-history.com/svg?repos=Bhaveshj008/theta-ai&type=Date)](https://star-history.com/#Bhaveshj008/theta-ai&Date)

---

## Disclaimer

This software is provided "as is" without warranty of any kind. Use at your own risk. The authors are not responsible for any damage or data loss caused by this software. Always supervise automated actions and maintain backups of important data.

---

<p align="center">
  Made with ❤️ by the Theta AI community
</p>

<p align="center">
  <a href="https://github.com/Bhaveshj008/theta-ai">⭐ Star</a> •
  <a href="https://github.com/Bhaveshj008/theta-ai/fork">🔱 Fork</a> •
  <a href="https://github.com/Bhaveshj008/theta-ai/issues">🐛 Report Bug</a> •
  <a href="https://github.com/Bhaveshj008/theta-ai/issues">💡 Request Feature</a>
</p>