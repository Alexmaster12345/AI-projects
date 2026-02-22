#!/usr/bin/env python3
"""
Rename ASHD to System Trace

Systematically changes all references from ASHD/Ashd to System Trace
throughout the entire project.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List

class SystemTraceRenamer:
    def __init__(self):
        self.project_root = Path.cwd()
        self.changes_made = 0
        self.files_processed = 0
        self.errors = []
        
        # Mapping of changes
        self.replacements = {
            'ASHD': 'System Trace',
            'Ashd': 'System Trace',
            'ashd': 'system-trace',
            'ASHD_AGENT': 'SYSTEM_TRACE_AGENT',
            'ashd-agent': 'system-trace-agent',
            'ASHD_AGENT_SERVICE': 'SYSTEM_TRACE_AGENT_SERVICE',
            'ashd-agent.service': 'system-trace-agent.service',
            'ASHD_USER': 'system-trace',
            'ashd_user': 'system-trace',
            'ASHD_SERVER': 'SYSTEM_TRACE_SERVER',
            'ashd_server': 'system-trace-server',
            'ASHD_DASHBOARD': 'SYSTEM_TRACE_DASHBOARD',
            'ashd_dashboard': 'system-trace-dashboard',
            'ASHD_CONFIG': 'SYSTEM_TRACE_CONFIG',
            'ashd_config': 'system-trace-config',
            'ASHD_METRICS': 'SYSTEM_TRACE_METRICS',
            'ashd_metrics': 'system-trace-metrics',
            'ASHD_HOST': 'SYSTEM_TRACE_HOST',
            'ashd_host': 'system-trace-host',
            'ASHD_PORT': 'SYSTEM_TRACE_PORT',
            'ashd_port': 'system-trace-port',
            'ASHD_SESSION': 'SYSTEM_TRACE_SESSION',
            'ashd_session': 'system-trace-session',
            'ASHD_ADMIN': 'SYSTEM_TRACE_ADMIN',
            'ashd_admin': 'system-trace-admin',
            'ASHD_USER_GROUP': 'SYSTEM_TRACE_USER_GROUP',
            'ashd_user_group': 'system-trace-user-group',
            'ASHD_API': 'SYSTEM_TRACE_API',
            'ashd_api': 'system-trace-api',
            'ASHD_DB': 'SYSTEM_TRACE_DB',
            'ashd_db': 'system-trace-db',
            'ASHD_LOG': 'SYSTEM_TRACE_LOG',
            'ashd_log': 'system-trace-log',
            'ASHD_DATA': 'SYSTEM_TRACE_DATA',
            'ashd_data': 'system-trace-data',
        }
        
        # Case-insensitive patterns for regex
        self.patterns = {
            'ASHD': re.compile(r'ASHD'),
            'Ashd': re.compile(r'Ashd'),
            'ashd': re.compile(r'ashd'),
        }
    
    def rename_file(self, file_path: Path) -> bool:
        """Rename references in a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            modified_content = content
            
            # Apply all replacements
            for old, new in self.replacements.items():
                modified_content = modified_content.replace(old, new)
            
            # Only write if content changed
            if modified_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                self.changes_made += 1
                return True
            
            return False
            
        except Exception as e:
            self.errors.append(f"Error processing {file_path}: {e}")
            return False
    
    def rename_json_file(self, file_path: Path) -> bool:
        """Rename references in JSON file with proper handling."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert JSON to string and replace
            content_str = json.dumps(data, indent=2)
            original_content = content_str
            modified_content = content_str
            
            # Apply all replacements
            for old, new in self.replacements.items():
                modified_content = modified_content.replace(old, new)
            
            # Only write if content changed
            if modified_content != original_content:
                # Parse back to JSON to ensure validity
                modified_data = json.loads(modified_content)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(modified_data, f, indent=2)
                
                self.changes_made += 1
                return True
            
            return False
            
        except Exception as e:
            self.errors.append(f"Error processing JSON {file_path}: {e}")
            return False
    
    def rename_python_file(self, file_path: Path) -> bool:
        """Rename references in Python file with proper handling."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            modified = False
            original_lines = lines[:]
            
            for i, line in enumerate(lines):
                original_line = line
                
                # Apply replacements while preserving case sensitivity for strings
                for old, new in self.replacements.items():
                    # Replace in strings (preserve case for string literals)
                    line = re.sub(rf'"{old}"', rf'"{new}"', line)
                    line = re.sub(rf"'{old}'", rf"'{new}'", line)
                    # Replace in comments and identifiers (case-insensitive)
                    line = re.sub(self.patterns[old], new, line)
                
                if line != original_line:
                    lines[i] = line
                    modified = True
            
            if modified:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                
                self.changes_made += 1
                return True
            
            return False
            
        except Exception as e:
            self.errors.append(f"Error processing Python {file_path}: {e}")
            return False
    
    def rename_html_file(self, file_path: Path) -> bool:
        """Rename references in HTML file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            modified_content = content
            
            # Apply all replacements
            for old, new in self.replacements.items():
                modified_content = modified_content.replace(old, new)
            
            # Only write if content changed
            if modified_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                self.changes_made += 1
                return True
            
            return False
            
        except Exception as e:
            self.errors.append(f"Error processing HTML {file_path}: {e}")
            return False
    
    def rename_bash_file(self, file_path: Path) -> bool:
        """Rename references in shell script."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            modified_content = content
            
            # Apply all replacements
            for old, new in self.replacements.items():
                modified_content = modified_content.replace(old, new)
            
            # Only write if content changed
            if modified_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                self.changes_made += 1
                return True
            
            return False
            
        except Exception as e:
            self.errors.append(f"Error processing shell script {file_path}: {e}")
            return False
    
    def rename_markdown_file(self, file_path: Path) -> bool:
        """Rename references in Markdown file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            modified_content = content
            
            # Apply all replacements
            for old, new in self.replacements.items():
                modified_content = modified_content.replace(old, new)
            
            # Only write if content changed
            if modified_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                self.changes_made += 1
                return True
            
            return False
            
        except Exception as e:
            self.errors.append(f"Error processing Markdown {file_path}: {e}")
            return False
    
    def process_file(self, file_path: Path) -> bool:
        """Process a single file based on its extension."""
        self.files_processed += 1
        
        # Skip certain files/directories
        skip_patterns = [
            '.git',
            '__pycache__',
            '.venv',
            'node_modules',
            '.pytest_cache',
            '.coverage'
        ]
        
        if any(pattern in str(file_path) for pattern in skip_patterns):
            return False
        
        # Skip if file doesn't contain ASHD references
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if not any(pattern.lower() in content.lower() for pattern in ['ashd']):
                    return False
        except:
            pass
        
        # Process based on file extension
        if file_path.suffix.lower() == '.json':
            return self.rename_json_file(file_path)
        elif file_path.suffix.lower() == '.py':
            return self.rename_python_file(file_path)
        elif file_path.suffix.lower() == '.html':
            return self.rename_html_file(file_path)
        elif file_path.suffix.lower() == '.sh':
            return self.rename_bash_file(file_path)
        elif file_path.suffix.lower() in ['.md', '.txt', '.rst']:
            return self.rename_markdown_file(file_path)
        else:
            return self.rename_file(file_path)
    
    def process_directory(self, directory: Path) -> Dict:
        """Process all files in a directory recursively."""
        results = {
            'files_processed': 0,
            'files_changed': 0,
            'errors': []
        }
        
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                if self.process_file(file_path):
                    results['files_changed'] += 1
                results['files_processed'] += 1
            elif file_path.is_dir():
                continue  # Skip directories
        
        results['files_processed'] = self.files_processed
        results['files_changed'] = self.changes_made
        results['errors'] = self.errors
        
        return results
    
    def update_project_name(self):
        """Update project name in key files."""
        print("🔄 Updating project name...")
        
        # Update README.md
        readme_path = self.project_root / 'README.md'
        if readme_path.exists():
            try:
                with open(readme_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Update title and description
                content = content.replace(
                    '# AI-Powered System Health Dashboard',
                    '# AI-Powered System Trace Dashboard'
                )
                content = content.replace(
                    'Local, real-time system monitoring dashboard.',
                    'Local, real-time system trace monitoring dashboard.'
                )
                content = content.replace(
                    'ASHD',
                    'System Trace'
                )
                
                with open(readme_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print("   ✅ Updated README.md")
                self.changes_made += 1
                
            except Exception as e:
                self.errors.append(f"Error updating README.md: {e}")
        
        # Update main.py
        main_path = self.project_root / 'app' / 'main.py'
        if main_path.exists():
            try:
                with open(main_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Update app description
                content = content.replace(
                    'ASHD',
                    'System Trace'
                )
                
                with open(main_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print("   ✅ Updated app/main.py")
                self.changes_made += 1
                
            except Exception as e:
                self.errors.append(f"Error updating main.py: {e}")
    
    def run_renaming(self):
        """Run the complete renaming process."""
        print("🔄 Renaming ASHD to System Trace")
        print("=" * 50)
        print("This will change all references from ASHD/Ashd to System Trace")
        print("throughout the entire project.")
        print("")
        
        # Update project name first
        self.update_project_name()
        
        # Process all files
        print(f"\n📁 Processing files in {self.project_root}...")
        results = self.process_directory(self.project_root)
        
        # Print summary
        print(f"\n📊 Renaming Summary")
        print("=" * 30)
        print(f"Files processed: {results['files_processed']}")
        print(f"Files changed: {results['files_changed']}")
        print(f"Changes made: {self.changes_made}")
        
        if self.errors:
            print(f"\n❌ Errors encountered: {len(self.errors)}")
            for error in self.errors[:10]:  # Show first 10 errors
                print(f"   {error}")
            if len(self.errors) > 10:
                print(f"   ... and {len(self.errors) - 10} more errors")
        else:
            print(f"\n✅ Renaming completed successfully!")
        
        print(f"\n🎯 Next Steps:")
        print(f"   1. Review the changes")
        print(f"2. Test the application")
        print(f"3. Update any documentation or scripts")
        print(f"4. Commit the changes to Git")
        
        return results

def main():
    """Main function to run the renaming."""
    renamer = SystemTraceRenamer()
    results = renamer.run_renaming()
    
    # Save results
    with open('renaming_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Results saved to: renaming_results.json")
    
    if results['files_changed'] > 0:
        print(f"\n🚀 Ready to commit changes:")
        print(f"   git add .")
        print(f"   git commit -m 'Rename ASHD to System Trace'")
        print(f"   git push origin main")

if __name__ == "__main__":
    main()
