# COS_Deploy

Runtime deployment repository for the BrightWork Chief of Staff AI agent.

## Structure
- agents/crewai/ — CrewAI orchestration layer (swappable)
- tools/ — Framework-agnostic integrations (FUB, Telegram, Calendar)
- clients/ — Per-client configuration and content
- platform/ — Shared specs and compliance rules
- scripts/ — Utility scripts

## Adding a new client
1. Create clients/{realtor-name}/ 
2. Populate soul.yaml, fub-config.yaml, sequences/, knowledge/
3. Pass --client {realtor-name} to main.py

## Running locally
cp .env.example .env
# populate .env with real credentials
pip install -r requirements.txt
python agents/crewai/main.py --client ben-olsen

## Source of truth
Content files (sequences, knowledge base) are authored in COS_Project_Build.
Copy updated files into clients/{name}/ when finalized.
