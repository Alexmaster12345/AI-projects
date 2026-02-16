#!/usr/bin/env python3
"""
Restore and Organize Repository

Restores files from git and organizes them into proper folders.
"""

import os
import shutil
from pathlib import Path
import subprocess

def restore_from_git():
    """Restore all files from git."""
    print("🔄 Restoring files from git...")
    
    try:
        # Reset to restore all files
        result = subprocess.run(['git', 'reset', '--hard', 'HEAD'], 
                              capture_output=True, text=True, cwd='.')
        if result.returncode == 0:
            print("   ✅ Files restored from git")
        else:
            print("   ❌ Error restoring from git")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    return True

def create_organized_structure():
    """Create organized folder structure."""
    print("\n📁 Creating organized structure...")
    
    folders = [
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
    
    # File mappings
    file_mappings = {
        # Scripts
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
        
        # Documentation
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
        'PORTS_CLOSED_SUMMARY.md': 'docs/guides',
        
        # Config files
        '.env.example': 'config',
        'monitoring_config.json': 'config',
        'deployment_commands.json': 'config',
        'deployment_plan.json': 'config',
        'discovery_results.json': 'config',
        'network_inventory.json': 'config',
        'agent_status_report.json': 'config',
        'renaming_results.json': 'config',
        
        # Deployment files
        'deploy_agent_manual.sh': 'deployment',
        'deploy_centos_docker_agent.sh': 'deployment',
        'deploy_non_root_centos_docker.sh': 'deployment',
        'deploy_now.sh': 'deployment',
        'deploy_to_192_168_50_1.sh': 'deployment',
        'deploy_to_192_168_50_198.sh': 'deployment',
        'deploy_to_192_168_50_81.sh': 'deployment',
        'deploy_to_192_168_50_89.sh': 'deployment',
        'fix_centos_docker_direct.sh': 'deployment',
        'fix_ntp_centos_docker.sh': 'deployment',
        
        # Data files
        'hosts_entry.txt': 'data'
    }
    
    for src_file, target_folder in file_mappings.items():
        src_path = Path(src_file)
        if src_path.exists():
            target_path = Path(target_folder) / src_path.name
            try:
                shutil.move(str(src_path), str(target_path))
                print(f"   ✅ Moved: {src_file} → {target_folder}")
            except Exception as e:
                print(f"   ❌ Error moving {src_file}: {e}")

def create_folder_readmes():
    """Create README files for each folder."""
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

def main():
    """Main function."""
    print("🔄 Restore and Organize Repository")
    print("=" * 50)
    
    # Restore from git
    if not restore_from_git():
        print("❌ Failed to restore from git")
        return
    
    # Create organized structure
    create_organized_structure()
    
    # Organize files
    organize_files()
    
    # Create folder READMEs
    create_folder_readmes()
    
    print("\n🎯 Repository organized successfully!")
    print("📁 Files organized into proper folders")
    print("📋 Documentation created for each folder")
    print("🚀 Ready for development with clean structure")

if __name__ == "__main__":
    main()
