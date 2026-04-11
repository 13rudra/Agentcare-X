import json

def clamp_score(s):
    try:
        return max(0.01, min(0.99, float(s)))
    except Exception:
        return 0.1

def keyword_grader(agent_output: str, expected: str) -> float:
    try:
        if not agent_output or not str(agent_output).strip():
            return 0.1
        try:
            out_dict = json.loads(agent_output)
            out_msg = out_dict.get("message", str(agent_output))
        except Exception:
            out_msg = str(agent_output)
            
        out_msg = out_msg.lower()
        exp_msg = expected.lower()
        
        words_exp = set(exp_msg.split())
        words_out = set(out_msg.split())
        
        if not words_exp:
            return 0.99
            
        overlap = len(words_exp.intersection(words_out)) / len(words_exp)
        return clamp_score(overlap)
    except Exception:
        return 0.1
