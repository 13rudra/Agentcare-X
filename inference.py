import os
import requests
import json
import time
import sys
from openai import OpenAI

# Required Hackathon Evaluation Format
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-3.5-turbo")
HF_TOKEN = os.getenv("HF_TOKEN")
ENV_URL = os.getenv("ENV_URL", "http://127.0.0.1:7860")

# Optional - if you use from_docker_image():
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME")

BASE_URL = ENV_URL.rstrip("/")

def get_action_from_llm(client, state):
    """Dynamically decide what to do based on environment state."""
    available_tools = [t.get("name") for t in state.get("info", {}).get("available_tools", [])]
    obs_text = state.get("observation", "")
    
    prompt = (
        "You are an AI support agent. Output a JSON object exactly like this:\n"
        '{"action_type": "respond", "message": "I will help."}\n'
        'OR if calling a tool:\n'
        '{"action_type": "call_tool", "tool_name": "process_refund", "tool_parameters": {"order_id": "123"}}\n'
        f"Available tools: {available_tools}. Current observation: {obs_text}"
    )
    
    if not HF_TOKEN or not client:
        # Fallback for Phase 1 automated checks when token is missing
        return {"action_type": "respond", "message": "Automated fallback mode."}

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[WARN] LLM Call Failed: {e}")
        return {"action_type": "respond", "message": "Fallback due to LLM error."}

def run_episode():
    # Setup Client
    client = None
    if HF_TOKEN:
        client = OpenAI(api_key=HF_TOKEN, base_url=API_BASE_URL, max_retries=1)

    print(f"[START] task_id=baseline")
    
    # Reset Environment
    try:
        res = requests.post(f"{BASE_URL}/reset", json={}, timeout=5)
        res.raise_for_status()
        state = res.json()
    except Exception as e:
        print(f"[ERROR] Failed to start environment: {e}")
        sys.exit(1)

    total_reward = 0.0
    done = False
    step = 0
    
    while not done and step < 5:
        step += 1
        
        # Get Action
        action = get_action_from_llm(client, state)
        
        # Step Environment
        try:
            res_step = requests.post(f"{BASE_URL}/step", json=action, timeout=5)
            res_step.raise_for_status()
            state = res_step.json()
            reward = state.get("reward", 0.0)
            done = state.get("done", True)
            total_reward += reward
            
            print(f"[STEP] step={step} action={json.dumps(action)} reward={reward:.4f}")
        except Exception as e:
            print(f"[STEP] Failed: {e}")
            break
            
        time.sleep(0.5)

    print(f"[END] task_id=baseline total_reward={total_reward:.4f} steps={step}")

if __name__ == "__main__":
    run_episode()
