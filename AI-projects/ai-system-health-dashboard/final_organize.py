#!/usr/bin/env python3
"""
Final Repository Organization

Creates a clean, organized structure for the System Trace dashboard.
"""

import os
import subprocess
from pathlib import Path

def restore_files_from_git():
    """Restore files from git commit."""
    print("🔄 Restoring files from git...")
    
    # Get all files from the latest commit
    result = subprocess.run(['git', 'show', '--name-only', '--pretty=format:""', 'HEAD'], 
                          capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Error getting file list from git")
        return False
    
    files = result.stdout.strip().split('\n')
    files = [f for f in files if f.strip()]
    
    # Filter files that belong to our repository
    repo_files = []
    for file_path in files:
        if file_path.startswith('ai-system-health-dashboard/'):
            relative_path = file_path.replace('ai-system-health-dashboard/', '')
            repo_files.append(relative_path)
    
    print(f"   Found {len(repo_files)} files to restore")
    
    # Restore each file
    restored_count = 0
    for file_path in repo_files:
        try:
            # Get file content from git
            result = subprocess.run(['git', 'show', f'HEAD:ai-system-health-dashboard/{file_path}'], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                # Create directory if needed
                Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                
                # Write file
                with open(file_path, 'w') as f:
                    f.write(result.stdout)
                
                restored_count += 1
                print(f"   ✅ Restored: {file_path}")
            else:
                print(f"   ❌ Failed to restore: {file_path}")
                
        except Exception as e:
            print(f"   ❌ Error restoring {file_path}: {e}")
    
    print(f"   Restored {restored_count} files")
    return restored_count > 0

def create_folder_structure():
    """Create organized folder structure."""
    print("\n📁 Creating organized folder structure...")
    
    folders = [
        'app/static/assets',
        'app/static/images',
        'scripts/deployment',
        'scripts/monitoring',
        'scripts/network',
        'scripts/maintenance',
        'scripts/utility',
        'docs/guides',
        'docs/api',
        'docs/deployment',
        'docs/monitoring',
        'docs/screenshots',
        'config',
        'data',
        'tests',
        'tools'
    ]
    
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"   ✅ Created: {folder}")

def organize_files():
    """Organize files into appropriate folders."""
    print("\n📋 Organizing files...")
    
    # Move scripts to subfolders
    script_mappings = {
        'scripts/auto_discover_hosts.py': 'scripts/network',
        'scripts/deploy_agents_non_root.py': 'scripts/deployment',
        'scripts/deploy_all_agents.py': 'scripts/deployment',
        'scripts/quick_deploy_agent.py': 'scripts/deployment',
        'scripts/setup_snmp.py': 'scripts/monitoring',
        'scripts/test_snmp_devices.py': 'scripts/monitoring',
        'scripts/check_agent_status.py': 'scripts/monitoring',
        'scripts/network_monitor_setup.py': 'scripts/network',
        'scripts/quick_network_scan.py': 'scripts/network',
        'scripts/fix_centos_docker_monitoring.py': 'scripts/maintenance',
        'scripts/fix_hostname_resolution.py': 'scripts/maintenance',
        'scripts/update_centos_docker_ip.py': 'scripts/maintenance',
        'scripts/close_all_ports.py': 'scripts/maintenance',
        'scripts/take_screenshots.py': 'scripts/utility',
        'scripts/rename_to_system_trace.py': 'scripts/utility',
        'scripts/organize_repository.py': 'scripts/utility',
        'scripts/create_hosts_dashboard.py': 'scripts/utility',
        'scripts/create_non_root_scripts.py': 'scripts/utility',
        'scripts/update_dashboard_hosts.py': 'scripts/utility',
        'scripts/configure_network_monitoring.py': 'scripts/utility'
    }
    
    # Move documentation
    doc_mappings = {
        'AGENT_DEPLOYMENT_GUIDE.md': 'docs/guides',
        'NON_ROOT_DEPLOYMENT_GUIDE.md': 'docs/guides',
        'MANUAL_FIX_GUIDE.md': 'docs/guides',
        'MANUAL_NON_ROOT_FIX.md': 'docs/guides',
        'QUICK_FIX_SUMMARY.md': 'docs/guides',
        'QUICK_NON_ROOT_FIX.md': 'docs/guides',
        'NON_ROOT_READY.md': 'docs/guides',
        'DEPLOYMENT_READY.md': 'docs/guides',
        'auto_discovery_summary.md': 'docs/guides',
        'correct_ip_deployment_guide.md': 'docs/deployment',
        'hostname_fix_summary.md': 'docs/guides',
        'pysnmp_fix_summary.md': 'docs/guides',
        'RENAMING_SUMMARY.md': 'docs/guides',
        'PORTS_CLOSED_SUMMARY.md': 'docs/guides'
    }
    
    # Move config files
    config_mappings = {
        '.env.example': 'config',
        'monitoring_config.json': 'config',
        'deployment_commands.json': 'config',
        'deployment_plan.json': 'config',
        'discovery_results.json': 'config',
        'network_inventory.json': 'config',
        'agent_status_report.json': 'config',
        'renaming_results.json': 'config'
    }
    
    # Move deployment files
    deploy_mappings = {
        'deploy_agent_manual.sh': 'deployment',
        'deploy_centos_docker_agent.sh': 'deployment',
        'deploy_non_root_centos_docker.sh': 'deployment',
        'deploy_now.sh': 'deployment',
        'deploy_to_192_168_50_1.sh': 'deployment',
        'deploy_to_192_168_50_198.sh': 'deployment',
        'deploy_to_192_168_50_81.sh': 'deployment',
        'deploy_to_192_168_50_89.sh': 'deployment',
        'fix_centos_docker_direct.sh': 'deployment',
        'fix_ntp_centos_docker.sh': 'deployment'
    }
    
    # Move data files
    data_mappings = {
        'hosts_entry.txt': 'data'
    }
    
    # Move docs to docs folder
    docs_mappings = {
        'docs/CENTOS_DOCKER_DEPLOYMENT.md': 'docs/deployment',
        'docs/NETWORK_MONITORING_GUIDE.md': 'docs/guides',
        'docs/SNMP_CONFIGURATION.md': 'docs/guides'
    }
    
    # Combine all mappings
    all_mappings = {}
    all_mappings.update(script_mappings)
    all_mappings.update(doc_mappings)
    all_mappings.update(config_mappings)
    all_mappings.update(deploy_mappings)
    all_mappings.update(data_mappings)
    all_mappings.update(docs_mappings)
    
    # Move files
    moved_count = 0
    for src_file, target_folder in all_mappings.items():
        src_path = Path(src_file)
        if src_path.exists():
            target_path = Path(target_folder) / src_path.name
            try:
                # Create target directory if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move file
                src_path.rename(target_path)
                moved_count += 1
                print(f"   ✅ Moved: {src_file} → {target_folder}")
            except Exception as e:
                print(f"   ❌ Error moving {src_file}: {e}")
    
    print(f"   Moved {moved_count} files")

def create_folder_readmes():
    """Create README files for organized folders."""
    print("\n📋 Creating folder READMEs...")
    
    readme_content = {
        'scripts/deployment': """# Deployment Scripts

This folder contains scripts for deploying System Trace agents.

## Scripts
- `deploy_agents_non_root.py` - Deploy agents as non-root users
- `deploy_all_agents.py` - Deploy agents to all discovered hosts
- `quick_deploy_agent.py` - Quick deployment interface
""",
        'scripts/monitoring': """# Monitoring Scripts

This folder contains scripts for monitoring system health.

## Scripts
- `setup_snmp.py` - Configure SNMP monitoring
- `test_snmp_devices.py` - Test SNMP connectivity
- `check_agent_status.py` - Check agent status
""",
        'scripts/network': """# Network Scripts

This folder contains scripts for network operations.

## Scripts
- `auto_discover_hosts.py` - Discover hosts on network
- `network_monitor_setup.py` - Setup network monitoring
- `quick_network_scan.py` - Quick network scan
""",
        'scripts/maintenance': """# Maintenance Scripts

This folder contains scripts for system maintenance.

## Scripts
- `fix_centos_docker_monitoring.py` - Fix monitoring issues
- `fix_hostname_resolution.py` - Fix hostname resolution
- `update_centos_docker_ip.py` - Update IP configuration
- `close_all_ports.py` - Close monitoring ports
""",
        'scripts/utility': """# Utility Scripts

This folder contains utility and helper scripts.

## Scripts
- `take_screenshots.py` - Take dashboard screenshots
- `rename_to_system_trace.py` - Rename project to System Trace
- `organize_repository.py` - Organize repository structure
""",
        'docs/guides': """# User Guides

This folder contains user guides and documentation.

## Guides
- Agent deployment guides
- Configuration guides
- Troubleshooting guides
- Quick start guides
""",
        'docs/deployment': """# Deployment Documentation

This folder contains deployment-related documentation.

## Documentation
- Deployment guides
- Configuration examples
- Best practices
""",
        'config': """# Configuration Files

This folder contains configuration files and templates.

## Files
- Environment variable templates
- Configuration JSON files
- Deployment configurations
""",
        'deployment': """# Deployment Files

This folder contains deployment scripts and configurations.

## Files
- Shell scripts for deployment
- Configuration files
- Utility scripts
""",
        'data': """# Data Files

This folder contains data files and logs.

## Files
- Host entries
- Status reports
- Configuration data
"""
    }
    
    for folder, content in readme_content.items():
        readme_path = Path(folder) / 'README.md'
        try:
            with open(readme_path, 'w') as f:
                f.write(content)
            print(f"   ✅ Created: {folder}/README.md")
        except Exception as e:
            print(f"   ❌ Error creating README for {folder}: {e}")

def create_main_readme():
    """Create main README with organized structure."""
    print("\n📝 Creating main README...")
    
    readme_content = """# AI-Powered System Trace Dashboard

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
"""
    
    try:
        with open('README.md', 'w') as f:
            f.write(readme_content)
        print("   ✅ Created: README.md")
    except Exception as e:
        print(f"   ❌ Error creating README: {e}")

def main():
    """Main function."""
    print("🗂️  Final Repository Organization")
    print("=" * 50)
    
    # Restore files from git
    if not restore_files_from_git():
        print("❌ Failed to restore files from git")
        return
    
    # Create folder structure
    create_folder_structure()
    
    # Organize files
    organize_files()
    
    # Create folder READMEs
    create_folder_readmes()
    
    # Create main README
    create_main_readme()
    
    print("\n🎯 Repository organized successfully!")
    print("📁 Files organized into proper folders")
    print("📋 Documentation created for each folder")
    print("🚀 Ready for development with clean structure")
    
    # Show final structure
    print("\n📊 Final Structure:")
    print("   app/                    # Application code")
    print("   ├── static/            # Web assets")
    print("   ├── main.py           # Main application")
    print("   └── ...")
    print("   scripts/               # Automation scripts")
    print("   ├── deployment/       # Deployment scripts")
    print("   ├── monitoring/       # Monitoring scripts")
    print("   ├── network/          # Network scripts")
    print("   ├── maintenance/     # Maintenance scripts")
    print("   └── utility/          # Utility scripts")
    print("   agents/               # Agent files")
    print("   docs/                 # Documentation")
    print("   config/               # Configuration")
    print("   data/                 # Data files")
    print("   deployment/           # Deployment configs")
    print("   tests/                # Test files")
    print("   tools/                # Development tools")

if __name__ == "__main__":
    main()
