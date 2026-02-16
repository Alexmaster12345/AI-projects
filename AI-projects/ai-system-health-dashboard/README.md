# AI-Powered System Trace Dashboard

Local, real-time system trace monitoring dashboard.

## 📁 Repository Structure

```
ai-system-health-dashboard/
├── app/                    # Application source code
│   ├── static/             # Static web files
│   │   ├── assets/         # JavaScript and CSS
│   │   └── images/         # Images and icons
│   ├── main.py             # Main application entry point
│   ├── protocols.py        # Protocol implementations
│   ├── storage.py          # Data storage layer
│   ├── config.py           # Configuration management
│   └── auth_storage.py     # Authentication storage
├── scripts/                # Automation and utility scripts
│   ├── deployment/         # Deployment scripts
│   ├── monitoring/         # Monitoring scripts
│   ├── network/           # Network scripts
│   ├── maintenance/       # Maintenance scripts
│   └── utility/           # Utility scripts
├── agents/                 # Agent deployment files
│   ├── ubuntu/            # Ubuntu agents
│   ├── debian/            # Debian agents
│   ├── rhel/              # RHEL agents
│   ├── centos/            # CentOS agents
│   └── rocky/             # Rocky Linux agents
├── docs/                   # Documentation
│   ├── guides/            # User guides
│   ├── api/               # API documentation
│   ├── deployment/        # Deployment guides
│   ├── monitoring/        # Monitoring guides
│   └── screenshots/       # Screenshots
├── config/                 # Configuration files
├── data/                   # Data files and databases
├── deployment/             # Deployment configurations
├── tests/                  # Test files
├── tools/                  # Development tools
├── README.md               # Main documentation
├── requirements.txt        # Python dependencies
└── .env.example           # Environment variables template
```

## 🚀 Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp config/.env.example .env
   # Edit .env with your configuration
   ```

3. **Start the Application**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

4. **Access the Dashboard**
   ```
   http://localhost:8001
   ```

## 📚 Documentation

- **User Guides**: `docs/guides/`
- **API Documentation**: `docs/api/`
- **Deployment Guides**: `docs/deployment/`
- **Monitoring Guides**: `docs/monitoring/`

## 🔧 Scripts

- **Deployment**: `scripts/deployment/`
- **Monitoring**: `scripts/monitoring/`
- **Network**: `scripts/network/`
- **Maintenance**: `scripts/maintenance/`
- **Utility**: `scripts/utility/`

## 🤖 Agents

Agent deployment files are organized by operating system in the `agents/` directory:
- Ubuntu/Debian: `apt` package management
- RHEL/CentOS/Rocky: `yum/dnf` package management

## 📊 Data

- **Configuration**: `config/`
- **Databases**: `data/`
- **Logs**: `data/`

---

*Repository structure organized for better maintainability.*
