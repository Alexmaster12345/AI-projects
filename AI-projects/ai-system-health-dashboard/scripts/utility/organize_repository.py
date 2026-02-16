#!/usr/bin/env python3
"""
Organize Repository Structure

Creates proper folder structure and moves files to appropriate directories.
"""

import os
import shutil
from pathlib import Path
import json

class RepositoryOrganizer:
    def __init__(self):
        self.repo_root = Path.cwd()
        self.folders_created = []
        self.files_moved = []
        self.errors = []
        
        # Define the target folder structure
        self.folder_structure = {
            'app': {
                'description': 'Application source code',
                'keep_files': ['main.py', 'protocols.py', 'storage.py', 'config.py', 'auth_storage.py']
            },
            'app/static': {
                'description': 'Static web files',
                'keep_files': ['*.html', '*.css', '*.js', '*.png', '*.jpg', '*.svg']
            },
            'app/static/assets': {
                'description': 'JavaScript and CSS assets',
                'keep_files': ['*.js', '*.css']
            },
            'app/static/images': {
                'description': 'Images and icons',
                'keep_files': ['*.png', '*.jpg', '*.svg', '*.ico']
            },
            'scripts': {
                'description': 'Automation and utility scripts',
                'keep_files': ['*.py', '*.sh']
            },
            'agents': {
                'description': 'Agent deployment files',
                'keep_files': ['*']
            },
            'docs': {
                'description': 'Documentation',
                'keep_files': ['*.md', '*.txt', '*.pdf']
            },
            'config': {
                'description': 'Configuration files',
                'keep_files': ['*.json', '*.yaml', '*.yml', '*.conf', '*.env*']
            },
            'data': {
                'description': 'Data files and databases',
                'keep_files': ['*.db', '*.sqlite', '*.csv', '*.log']
            },
            'tests': {
                'description': 'Test files',
                'keep_files': ['test_*.py', '*_test.py', 'test_*.sh']
            },
            'deployment': {
                'description': 'Deployment scripts and configs',
                'keep_files': ['deploy_*.sh', '*.yml', 'Dockerfile*', 'docker-compose*']
            },
            'tools': {
                'description': 'Development and maintenance tools',
                'keep_files': ['*.py', '*.sh']
            }
        }
    
    def create_folder_structure(self):
        """Create the organized folder structure."""
        print("📁 Creating organized folder structure...")
        
        for folder_path, info in self.folder_structure.items():
            folder = self.repo_root / folder_path
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
                self.folders_created.append(str(folder))
                print(f"   ✅ Created: {folder_path}")
            else:
                print(f"   ℹ️  Exists: {folder_path}")
    
    def move_files_to_folders(self):
        """Move files to their appropriate folders."""
        print("\n📋 Moving files to organized folders...")
        
        # Get all files in root directory
        root_files = [f for f in self.repo_root.iterdir() if f.is_file()]
        
        for file_path in root_files:
            # Skip certain files that should stay in root
            if self._should_keep_in_root(file_path):
                print(f"   ⏭️  Keeping in root: {file_path.name}")
                continue
            
            # Determine target folder
            target_folder = self._get_target_folder(file_path)
            
            if target_folder:
                target_path = self.repo_root / target_folder / file_path.name
                
                # Move file
                try:
                    shutil.move(str(file_path), str(target_path))
                    self.files_moved.append(f"{file_path.name} → {target_folder}/{file_path.name}")
                    print(f"   ✅ Moved: {file_path.name} → {target_folder}")
                except Exception as e:
                    self.errors.append(f"Error moving {file_path.name}: {e}")
                    print(f"   ❌ Error moving {file_path.name}: {e}")
    
    def organize_agents_folder(self):
        """Organize the agents folder by OS type."""
        print("\n🤖 Organizing agents folder...")
        
        agents_dir = self.repo_root / 'agents'
        if not agents_dir.exists():
            return
        
        # Create OS-specific subfolders
        os_types = ['ubuntu', 'debian', 'rhel', 'centos', 'rocky']
        
        for os_type in os_types:
            os_dir = agents_dir / os_type
            if os_dir.exists():
                # Create subfolders for each OS
                subfolders = ['scripts', 'config', 'services']
                for subfolder in subfolders:
                    sub_dir = os_dir / subfolder
                    sub_dir.mkdir(exist_ok=True)
                    print(f"   ✅ Created: agents/{os_type}/{subfolder}")
                
                # Move files to appropriate subfolders
                for file_path in os_dir.iterdir():
                    if file_path.is_file():
                        if file_path.name.endswith('.sh'):
                            target = os_dir / 'scripts' / file_path.name
                        elif file_path.name.endswith('.conf'):
                            target = os_dir / 'config' / file_path.name
                        elif file_path.name.endswith('.service'):
                            target = os_dir / 'services' / file_path.name
                        else:
                            continue
                        
                        try:
                            shutil.move(str(file_path), str(target))
                            print(f"   ✅ Moved: agents/{os_type}/{file_path.name} → agents/{os_type}/{subfolder}")
                        except Exception as e:
                            print(f"   ❌ Error moving {file_path.name}: {e}")
    
    def organize_scripts_folder(self):
        """Organize scripts into categories."""
        print("\n🔧 Organizing scripts folder...")
        
        scripts_dir = self.repo_root / 'scripts'
        if not scripts_dir.exists():
            return
        
        # Create script categories
        categories = {
            'deployment': ['deploy', 'setup', 'install'],
            'monitoring': ['monitor', 'check', 'test', 'snmp', 'ntp'],
            'network': ['network', 'discovery', 'scan'],
            'maintenance': ['fix', 'update', 'cleanup', 'close'],
            'utility': ['take_screenshots', 'verify', 'organize']
        }
        
        for category, keywords in categories.items():
            category_dir = scripts_dir / category
            category_dir.mkdir(exist_ok=True)
            print(f"   ✅ Created: scripts/{category}")
        
        # Move scripts to categories
        for file_path in scripts_dir.iterdir():
            if file_path.is_file() and file_path.name.endswith('.py'):
                file_name_lower = file_path.name.lower()
                
                # Determine category based on keywords
                target_category = None
                for category, keywords in categories.items():
                    if any(keyword in file_name_lower for keyword in keywords):
                        target_category = category
                        break
                
                if target_category:
                    target_path = scripts_dir / target_category / file_path.name
                    try:
                        shutil.move(str(file_path), str(target_path))
                        print(f"   ✅ Moved: scripts/{file_path.name} → scripts/{target_category}")
                    except Exception as e:
                        print(f"   ❌ Error moving {file_path.name}: {e}")
    
    def organize_docs_folder(self):
        """Organize documentation by category."""
        print("\n📚 Organizing documentation...")
        
        docs_dir = self.repo_root / 'docs'
        if not docs_dir.exists():
            docs_dir.mkdir(exist_ok=True)
        
        # Create doc categories
        categories = {
            'guides': ['guide', 'manual', 'tutorial', 'howto'],
            'api': ['api', 'endpoint'],
            'deployment': ['deployment', 'deploy', 'install'],
            'monitoring': ['monitoring', 'snmp', 'ntp'],
            'screenshots': ['screenshot', 'image', 'png', 'jpg']
        }
        
        for category in categories:
            category_dir = docs_dir / category
            category_dir.mkdir(exist_ok=True)
            print(f"   ✅ Created: docs/{category}")
        
        # Move documentation files
        for file_path in self.repo_root.iterdir():
            if file_path.is_file() and file_path.name.endswith('.md'):
                file_name_lower = file_path.name.lower()
                
                # Determine category
                target_category = None
                for category, keywords in categories.items():
                    if any(keyword in file_name_lower for keyword in keywords):
                        target_category = category
                        break
                
                if target_category:
                    target_path = docs_dir / target_category / file_path.name
                    try:
                        shutil.move(str(file_path), str(target_path))
                        print(f"   ✅ Moved: {file_path.name} → docs/{target_category}")
                    except Exception as e:
                        print(f"   ❌ Error moving {file_path.name}: {e}")
    
    def _should_keep_in_root(self, file_path):
        """Check if file should stay in root directory."""
        keep_files = {
            'README.md', 'LICENSE', '.gitignore', '.env.example',
            'requirements.txt', 'setup.py', 'pyproject.toml',
            'Dockerfile', 'docker-compose.yml', 'Makefile'
        }
        return file_path.name in keep_files
    
    def _get_target_folder(self, file_path):
        """Determine the appropriate folder for a file."""
        file_name = file_path.name.lower()
        
        # Configuration files
        if file_name.endswith(('.json', '.yaml', '.yml', '.conf', '.env')):
            return 'config'
        
        # Data files
        if file_name.endswith(('.db', '.sqlite', '.csv', '.log')):
            return 'data'
        
        # Documentation
        if file_name.endswith(('.md', '.txt', '.pdf', '.rst')):
            return 'docs'
        
        # Test files
        if file_name.startswith(('test_', '_test')):
            return 'tests'
        
        # Deployment files
        if file_name.startswith(('deploy_', 'docker', 'k8s', 'helm')):
            return 'deployment'
        
        # Scripts
        if file_name.endswith(('.py', '.sh')):
            return 'scripts'
        
        return None
    
    def create_folder_index(self):
        """Create index files for each folder."""
        print("\n📋 Creating folder indexes...")
        
        for folder_path, info in self.folder_structure.items():
            folder = self.repo_root / folder_path
            
            if folder.exists():
                # Create README.md for each folder
                readme_path = folder / 'README.md'
                
                content = f"""# {folder_path.title()}

{info['description']}

## Files in this directory

"""
                
                # List files in directory
                if folder.exists():
                    for file_path in sorted(folder.iterdir()):
                        if file_path.is_file():
                            content += f"- `{file_path.name}`\n"
                
                try:
                    with open(readme_path, 'w') as f:
                        f.write(content)
                    print(f"   ✅ Created: {folder_path}/README.md")
                except Exception as e:
                    print(f"   ❌ Error creating README for {folder_path}: {e}")
    
    def create_repository_overview(self):
        """Create a repository overview file."""
        print("\n📊 Creating repository overview...")
        
        overview_content = """# Repository Structure Overview

## 📁 Folder Structure

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
│   │   ├── scripts/       # Deployment scripts
│   │   ├── config/         # Configuration files
│   │   └── services/       # Systemd services
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
   cp .env.example .env
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

- **Main Documentation**: `docs/guides/`
- **API Documentation**: `docs/api/`
- **Deployment Guides**: `docs/deployment/`
- **Monitoring Guides**: `docs/monitoring/`

## 🔧 Scripts

- **Deployment**: `scripts/deployment/`
- **Monitoring**: `scripts/monitoring/`
- **Network**: `scripts/network/`
- **Maintenance**: `scripts/maintenance/`

## 🤖 Agents

Agent deployment files are organized by operating system in the `agents/` directory:
- Ubuntu/Debian: `apt` package management
- RHEL/CentOS/Rocky: `yum/dnf` package management

## 📊 Data

- **Configuration**: `config/`
- **Databases**: `data/`
- **Logs**: `data/`

---

*Repository structure automatically organized for better maintainability.*
"""
        
        try:
            with open(self.repo_root / 'REPOSITORY_STRUCTURE.md', 'w') as f:
                f.write(overview_content)
            print("   ✅ Created: REPOSITORY_STRUCTURE.md")
        except Exception as e:
            print(f"   ❌ Error creating repository overview: {e}")
    
    def run_organization(self):
        """Run the complete organization process."""
        print("🗂️  Repository Organization")
        print("=" * 50)
        print("This will organize all files into appropriate folders")
        print("and create a clean repository structure.")
        print("")
        
        # Create folder structure
        self.create_folder_structure()
        
        # Move files to folders
        self.move_files_to_folders()
        
        # Organize specific folders
        self.organize_agents_folder()
        self.organize_scripts_folder()
        self.organize_docs_folder()
        
        # Create indexes
        self.create_folder_index()
        self.create_repository_overview()
        
        # Print summary
        print(f"\n📊 Organization Summary")
        print("=" * 30)
        print(f"Folders created: {len(self.folders_created)}")
        print(f"Files moved: {len(self.files_moved)}")
        print(f"Errors: {len(self.errors)}")
        
        if self.errors:
            print(f"\n❌ Errors encountered:")
            for error in self.errors[:5]:
                print(f"   {error}")
            if len(self.errors) > 5:
                print(f"   ... and {len(self.errors) - 5} more errors")
        
        print(f"\n🎯 Repository organized successfully!")
        print(f"📁 New structure created with proper folder organization")
        print(f"📋 Documentation updated with folder indexes")
        print(f"🚀 Ready for development with clean structure")

def main():
    """Main function."""
    organizer = RepositoryOrganizer()
    organizer.run_organization()

if __name__ == "__main__":
    main()
