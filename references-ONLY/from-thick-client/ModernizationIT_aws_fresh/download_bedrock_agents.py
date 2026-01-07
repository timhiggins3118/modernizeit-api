#!/usr/bin/env python3
import boto3
import json
import os

REGION = 'us-east-1'
BASE_DIR = '/Users/timhiggins/Desktop/ModernizationIT_aws_fresh/bedrock_agents'

COBOL_AGENTS = ['COBOLAnalyst', 'COBOLAnalystV2', 'COBOLDataAnalystV2', 'CodeRefactorAnalyst']

def main():
    client = boto3.client('bedrock-agent', region_name=REGION)

    response = client.list_agents()

    for agent_summary in response['agentSummaries']:
        name = agent_summary['agentName']
        agent_id = agent_summary['agentId']

        if name not in COBOL_AGENTS:
            continue

        print(f"{name}...", end=' ', flush=True)

        agent_details = client.get_agent(agentId=agent_id)

        with open(os.path.join(BASE_DIR, f'{name}_{agent_id}.json'), 'w') as f:
            json.dump(agent_details, f, indent=2, default=str)

        print(f'✓ ({agent_id})')

    print(f"\n=== {len(COBOL_AGENTS)} Bedrock Agents downloaded ===")

if __name__ == '__main__':
    main()
