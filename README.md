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
- [Current Status](#current-status)
- [Features](#features)
- [Demo](#demo)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [Examples](#examples)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Safety Features](#safety-features)
- [Performance](#performance)
- [Known Limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Built With](#built-with)
- [Security](#security)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Contributors](#contributors)
- [Support](#support)

---

## Overview

Theta AI is an experimental AI agent that automates desktop tasks through a perception-planning-action loop. It uses computer vision to understand screen state, LLMs to plan actions, and integrates multiple automation tools to execute tasks across desktop applications and web browsers.

This is a proof-of-concept implementation demonstrating autonomous desktop agent architecture. It works well for simple automation tasks and serves as a foundation for exploring AI-driven computer control.

**Warning:** Theta AI can control your computer but requires user approval for sensitive operations. Use in a safe environment and supervise all actions. This is experimental software not intended for production use.

---

## Current Status

### Version 0.1.0 Alpha - Proof of Concept

This release demonstrates core desktop agent capabilities with the following maturity levels:

#### Reliable Features
- **Notepad automation** - Text input, file operations (success rate: ~90%)
- **Calculator automation** - Basic arithmetic operations (success rate: ~85%)
- **Browser navigation** - URL navigation, search queries (success rate: ~95%)
- **Application launching** - Start any Windows application via Start menu
- **Voice control** - Wake word detection and command recognition
- **Screen perception** - OCR-based screen content extraction
- **Permission system** - User approval gates for sensitive operations

#### Experimental Features
- **Complex application automation** - VS Code, Office applications (limited element discovery)
- **Browser interactions** - Form filling, button clicking (inconsistent reliability)
- **Multi-step workflows** - Success rate decreases with task complexity
- **Error recovery** - Basic retry logic, may get stuck in loops

#### Not Yet Implemented
- **Cross-platform support** - Currently Windows 10/11 only
- **Task memory** - No context retention between sessions
- **Parallel execution** - Single task queue only
- **Automatic rollback** - No undo functionality for completed actions
- **Advanced vision** - No visual element detection beyond OCR

### Why Open Source Now?

This proof-of-concept is released to:
1. Demonstrate functional AI agent architecture for desktop automation
2. Gather feedback from the developer community on approach and implementation
3. Attract contributors interested in improving UI automation reliability
4. Serve as a learning resource for building autonomous agents
5. Validate the concept before investing in production-grade implementation

Contributions are particularly welcome in areas of UI element discovery, error recovery, and cross-platform support.

---

## Features

- Autonomous task execution via natural language commands
- Screen perception through OCR and UI element detection
- LLM-based action planning using Groq Llama 3.3 70B
- Multi-tool orchestration (browser, desktop apps, file system)
- Permission gates for destructive, payment, and login operations
- Voice command support with wake word detection
- Real-time overlay interface for monitoring
- Audit logging for all executed actions
- Safety checks for sensitive operations

---

## Demo

### Example Commands

**Working Reliably:**
```bash
# Notepad automation
python -m agent.main "open notepad and write hello world"

# Calculator operations  
python -m agent.main "open calculator and calculate 25 times 30"

# Browser navigation
python -m agent.main "search for python tutorials on bing"
```

**Experimental (may fail):**
```bash
# Complex app interaction
python -m agent.main "open vs code and create new file"

# Browser form interaction
python -m agent.main "fill login form on github"
```

### Voice Commands (Overlay Mode)
```
"Hey Theta, open notepad"
"Hey Theta, calculate 123 plus 456"
"Hey Theta, search for AI news"
```

**Note:** Video demonstrations will be added as the project stabilizes. Current focus is on core functionality rather than polished demos.

---

## Architecture

<p align="center">
  <img src="assets/architecture.png" alt="Theta AI Architecture" width="100%" />
</p>

The agent operates in a continuous perception-planning-action loop:

1. **Perceive** - Capture and analyze screen state using OCR
2. **Plan** - Query LLM to determine next action based on task and current state
3. **Safety Check** - Request user approval for sensitive operations
4. **Execute** - Call appropriate tool to perform planned action
5. **Verify** - Check task completion status or handle errors
6. **Iterate** - Repeat until task complete or maximum iterations reached

### Core Components

- **Orchestrator** - Main control loop managing state and tool execution
- **LLM Client** - Interface to Groq API for action planning
- **Perception Engine** - Screen capture and OCR processing
- **Tool Suite** - Browser, UI automation, file system, input control
- **Safety Layer** - Permission gates and audit logging
- **Voice Interface** - Wake word detection and speech recognition

---

## Prerequisites

- Python 3.10 or higher
- Windows 10/11 (for full desktop automation support)
- Groq API key (free tier available at groq.com)
- 8GB RAM minimum (16GB recommended for optimal OCR performance)
- Internet connection for LLM API calls

---

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/Bhaveshj008/theta-ai.git
cd theta-ai
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
```

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browsers

```bash
playwright install chromium
```

### 5. Configure Environment

Create a `.env` file in the project root:

```env
# API Keys (Required)
GROQ_API_KEY=your_groq_api_key_here

# Optional: For vision models
OPENROUTER_API_KEY=your_openrouter_key_here

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

**Obtaining API Keys:**

1. Visit [console.groq.com](https://console.groq.com)
2. Sign up for free account
3. Navigate to API Keys section
4. Create new key and copy to `.env` file

Groq free tier provides 30 requests per minute, sufficient for most use cases.

---

## Usage

### Overlay Mode (Recommended)

Launch the graphical interface:

```bash
python -m agent.main --overlay
```

Type commands in the input field or use voice with "Hey Theta" wake word.

### Command Line Mode

Execute single task:

```bash
python -m agent.main "open notepad and write hello world"
```

### Interactive Mode

Enter interactive shell:

```bash
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

**Notepad (Reliable):**
```bash
python -m agent.main "open notepad and write hello world"
# Expected: Opens Notepad, types text, completes in 8-12 seconds
```

**Calculator (Reliable):**
```bash
python -m agent.main "launch calculator and calculate 123 plus 456"
# Expected: Opens Calculator, performs operation, shows result
```

**Complex Apps (Experimental):**
```bash
python -m agent.main "open vs code and create new file"
# Expected: May launch VS Code but interaction reliability varies
```

### Web Browser

**Navigation (Reliable):**
```bash
python -m agent.main "go to github.com"
# Expected: Opens browser, navigates to URL
```

**Search (Reliable):**
```bash
python -m agent.main "search for python documentation on bing"
# Expected: Opens Bing, enters search query
```

**Interactions (Not Working):**
```bash
python -m agent.main "login to github and create repository"
# Expected: Currently fails - browser interactions limited in v0.1
```

### File Operations

```bash
python -m agent.main "create file notes.txt in workspace"
python -m agent.main "list files in workspace directory"
python -m agent.main "read todo.txt and show contents"
```

**Note:** File operations are restricted to the workspace directory for safety.

### Voice Commands (Overlay Mode)

```
"Hey Theta, open notepad"
"Hey Theta, search for python tutorials"
"Hey Theta, calculate 25 times 30"
```

---

## Configuration

Edit `agent/config.py` or use `.env` file to modify settings:

```python
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
WARNING: PERMISSION REQUIRED

Action: Delete file
Description: Remove important_document.txt
Risk Level: High

[Approve] [Reject]
```

**CLI Mode:**
```
WARNING: Permission Required
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

- Task iteration limit prevents infinite loops (default: 50)
- Loop detection identifies repeated failed actions
- File operations restricted to workspace directory only
- Real-time action monitoring through overlay interface
- Sensitive data pattern detection (SSN, credit cards)
- Automatic approval timeout for unattended prompts

---

## Performance

### System Requirements
- **Minimum:** 8GB RAM, Dual-core CPU, 2GB disk space
- **Recommended:** 16GB RAM, Quad-core CPU, 5GB disk space
- **GPU:** Optional (improves OCR speed by 2-3x with CUDA)

### Actual Response Times

Based on real-world testing:

- **Screen perception:** 2-4 seconds (OCR + analysis)
- **LLM planning:** 4-8 seconds (Groq Llama 3.3 70B including network latency)
- **Action execution:** 1-3 seconds (depends on task complexity)
- **Full iteration:** 10-20 seconds average (perception to action completion)

**Multi-step tasks:**
- Simple (3 steps): 30-45 seconds
- Medium (5-7 steps): 60-90 seconds
- Complex (10+ steps): May timeout or fail

### Resource Usage
- **Memory:** 800MB-2.5GB (depends on OCR and browser usage)
- **CPU:** 15-40% average (spikes to 60-80% during OCR)
- **Network:** ~50KB per LLM request (text-only)
- **Disk:** Workspace and logs grow with usage (typically 10-50MB per session)

### Optimization Tips
- Close unused applications to reduce OCR processing time
- Use `--no-voice` flag if voice input not needed
- Enable GPU OCR if NVIDIA GPU available (`USE_GPU_OCR=True`)
- Increase screen resolution for better OCR accuracy (1920x1080 recommended)
- Clear workspace periodically to manage disk usage

---

## Known Limitations

### Current Implementation Constraints

- **Windows-only** - Desktop automation requires pywinauto (Windows-specific)
- **Single task execution** - No parallel processing or task queuing
- **OCR dependency** - Accuracy varies with screen resolution, fonts, and UI complexity
- **No task memory** - Agent does not remember previous sessions or learn from mistakes
- **Limited error recovery** - May get stuck in loops on repeated failures
- **Browser limitations** - Cannot handle complex JavaScript interactions or dynamic content
- **No undo/rollback** - Executed actions cannot be automatically reversed
- **Voice quality** - Recognition requires clear audio input, sensitive to background noise

### Known Issues

- Complex applications (VS Code, Office) have unreliable element discovery
- Browser form filling often fails due to dynamic page loading
- Calculator button names may not match across different Windows versions
- Voice wake word occasionally triggers on similar-sounding phrases
- Permission dialogs may timeout if user is away from computer
- OCR sometimes misreads text with decorative fonts or low contrast
- Agent may repeat failed actions before recognizing the loop

### Future Work

See [Roadmap](#roadmap) section for planned improvements addressing these limitations.

---

## Troubleshooting

### Common Issues

**Q: "ModuleNotFoundError: No module named 'agent'"**

Ensure you are in the project root directory and virtual environment is activated:
```bash
cd theta-ai
.venv\Scripts\activate  # Windows
python -m agent.main --overlay
```

**Q: "Groq API error 401: Invalid API key"**

- Verify `.env` file exists and contains `GROQ_API_KEY=your_key_here`
- Check key is valid at [https://console.groq.com](https://console.groq.com)
- Ensure no extra spaces or quotes around the key value

**Q: "OCR not detecting text on screen"**

- Increase screen resolution (1920x1080 or higher recommended)
- Ensure text size is at least 10pt font
- Check contrast between text and background
- Try enabling GPU OCR: `USE_GPU_OCR=True` in `.env`
- Verify EasyOCR installed correctly: `pip install easyocr`

**Q: "Voice commands not working"**

- Check microphone permissions in Windows Settings
- Verify `ENABLE_VOICE=True` in `.env`
- Test microphone with Windows Voice Recorder
- Speak wake word clearly: "hey theta" (pause) "command"
- Check audio input device is set correctly

**Q: "pywinauto cannot find window"**

- Ensure application is visible and not minimized
- Try running as Administrator for system applications
- Verify application name matches exactly (case-sensitive)
- Check if application is 64-bit (pywinauto may need adjustment)

**Q: "Playwright browser won't launch"**

```bash
# Reinstall Playwright browsers
playwright install chromium --force
```

**Q: "Agent gets stuck in loop"**

- Check logs for repeated failed actions
- Manually stop with Ctrl+C
- Restart with simpler task to verify functionality
- Report issue with logs if problem persists

### Getting Help

If you encounter issues not listed here:

1. Check [GitHub Issues](https://github.com/Bhaveshj008/theta-ai/issues) for existing reports
2. Search [Discussions](https://github.com/Bhaveshj008/theta-ai/discussions) for similar problems
3. Open a new issue with:
   - Complete error message and stack trace
   - Your OS version and Python version
   - Steps to reproduce the problem
   - Expected vs actual behavior

---

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black agent/
isort agent/
```

### Linting

```bash
flake8 agent/
pylint agent/
```

### Development Mode

Run with debug logging:

```bash
python -m agent.main --overlay --debug
```

---

## Contributing

Contributions are welcome, particularly in the following areas:

### High Priority
- Cross-platform support (Linux, macOS)
- Improved UI element discovery for complex applications
- Better error recovery and retry logic
- Enhanced browser interaction reliability

### Medium Priority
- Test coverage expansion
- Performance optimizations
- Documentation improvements
- Additional tool integrations (email, calendar)

### Contributing Guidelines

1. Fork the repository
2. Create feature branch (`git checkout -b feature/description`)
3. Commit changes with clear messages (`git commit -m 'Add feature'`)
4. Push to branch (`git push origin feature/description`)
5. Open Pull Request with description of changes

Please ensure:
- Code follows existing style (black + isort)
- Tests pass for modified code
- Documentation updated for new features
- No breaking changes without discussion

---

## Roadmap

### Version 0.2 (Q1 2026)
- Linux and macOS desktop automation support
- Improved UI element discovery using accessibility APIs
- Enhanced error recovery with automatic retry strategies
- Multi-tab browser management
- Comprehensive test suite

### Version 0.3 (Q2 2026)
- Memory system for task history and learning
- Plugin architecture for custom tools
- Multi-monitor support
- Advanced vision model integration (beyond OCR)
- Parallel task execution

### Version 1.0 (Q3 2026)
- Production-ready stability and reliability
- Enterprise security features
- Performance optimizations
- Complete API documentation
- Migration guides and tutorials

---

## FAQ

### General

**Q: Is Theta AI free to use?**  
A: Yes, Theta AI is open source under MIT License. You need a Groq API key, which has a free tier with generous limits.

**Q: Does it work on Mac or Linux?**  
A: Currently Windows 10/11 only. macOS and Linux support is planned for v0.2 due to different UI automation APIs.

**Q: Can I use it without Groq API?**  
A: No, Theta AI requires LLM API access for action planning. Groq offers 30 requests/minute free tier.

**Q: Is my data secure?**  
A: Theta AI runs locally. Screenshots are processed locally via OCR. Only text prompts are sent to LLM APIs. No data is stored externally.

### Technical

**Q: Which LLM models does it support?**  
A: Primary: Groq Llama 3.3 70B, Fallback: Groq Llama 3.1 8B, Vision: OpenRouter Nemotron 12B (optional).

**Q: Can I add custom tools?**  
A: Yes. Inherit from `agent/tools/base_tool.py`, implement `execute()` method, and register in orchestrator.

**Q: How does permission system work?**  
A: Theta AI detects sensitive keywords in planned actions (delete, payment, login) and pauses for user approval before executing.

**Q: Can it run multiple tasks simultaneously?**  
A: Not currently. Single task execution is a v0.1 limitation. Parallel processing planned for v0.3.

**Q: What is the token/cost usage?**  
A: Groq free tier provides 30 requests/minute and ~6000 tokens/minute. Typical task uses 500-2000 tokens. Very cost-effective for most use cases.

### Safety

**Q: Can it damage my system?**  
A: Theta AI has safety gates for destructive operations and restricts file operations to workspace directory. However, always supervise automated actions.

**Q: What permissions does it need?**  
A: Screen capture, keyboard/mouse control, file system access (workspace only), microphone (for voice), internet access (for API calls).

**Q: Is there an undo feature?**  
A: No automatic rollback in v0.1. Audit log tracks all actions for manual review if needed.

---

## Built With

| Component | Technology |
|-----------|-----------|
| **LLM Provider** | [Groq](https://groq.com) - Llama 3.3 70B |
| **Vision Model** | [OpenRouter](https://openrouter.ai) - Nemotron 12B |
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

If you discover a security vulnerability, please report it via:
- **GitHub Issues:** Create confidential issue
- **Email:** bhaveshj008@gmail.com (mark subject: SECURITY)

Response time: 48-72 hours

Please do not open public issues for security vulnerabilities until they are addressed.

### Security Best Practices

When using Theta AI:
- Review permissions before approval
- Check audit logs regularly
- Use in isolated or test environment first
- Keep API keys in `.env` file (never commit to version control)
- Run with least privileges necessary
- Do not use on production systems without supervision
- Do not approve operations you do not understand

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Acknowledgments

Built with open source libraries:

- **Groq** - Fast LLM inference
- **EasyOCR** - Accurate text recognition
- **Playwright** - Reliable browser automation
- **pywinauto** - Windows UI automation
- **PyAutoGUI** - Cross-platform input control
- **OpenRouter** - Unified LLM API access
- **Whisper** - State-of-the-art speech recognition

Special thanks to the open source community for these excellent tools.

---

## Contributors

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

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=Bhaveshj008/theta-ai&type=Date)](https://star-history.com/#Bhaveshj008/theta-ai&Date)

---

## Disclaimer

This software is provided "as is" without warranty of any kind. Use at your own risk. The authors are not responsible for any damage or data loss caused by this software. Always supervise automated actions and maintain backups of important data.

---

<p align="center">
  Made with care by the Theta AI community
</p>

<p align="center">
  <a href="https://github.com/Bhaveshj008/theta-ai">Star</a> •
  <a href="https://github.com/Bhaveshj008/theta-ai/fork">Fork</a> •
  <a href="https://github.com/Bhaveshj008/theta-ai/issues">Report Bug</a> •
  <a href="https://github.com/Bhaveshj008/theta-ai/issues">Request Feature</a>
</p>