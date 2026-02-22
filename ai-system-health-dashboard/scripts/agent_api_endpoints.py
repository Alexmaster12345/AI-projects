
# Add to main.py - Agent Management API

@app.get("/hosts")
async def hosts_page(request: Request):
    """Serve the hosts management page."""
    return FileResponse("app/static/hosts.html")

@app.get("/api/discovery/results")
async def get_discovery_results():
    """Get discovery results."""
    try:
        with open('discovery_results.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Discovery results not found"}

@app.get("/api/agent/files/{os_type}")
async def get_agent_files(os_type: str):
    """Get available agent files for OS type."""
    agent_dir = Path(f'agents/{os_type}')
    if not agent_dir.exists():
        return {"error": f"OS type {os_type} not supported"}
    
    files = {}
    for file_path in agent_dir.glob('*'):
        files[file_path.name] = str(file_path)
    
    return {"os_type": os_type, "files": files}

@app.post("/api/agent/deploy/{host_ip}")
async def deploy_agent_to_host(host_ip: str, request: Request):
    """Deploy agent to specific host."""
    try:
        data = await request.json()
        os_type = data.get('os_type')
        
        if not os_type:
            return {"error": "OS type required"}
        
        # Get deployment commands
        with open('deployment_plan.json', 'r') as f:
            plan = json.load(f)
        
        if host_ip in plan['deployment_commands']:
            commands = plan['deployment_commands'][host_ip]
            return {"host_ip": host_ip, "commands": commands}
        else:
            return {"error": f"No deployment commands for {host_ip}"}
            
    except Exception as e:
        return {"error": str(e)}
