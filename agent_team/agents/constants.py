from google.adk.models.lite_llm import LiteLlm # For multi-model support

MODEL_GPT_4O = "openai/gpt-4.1" 
AGENT_MODEL = LiteLlm(model=MODEL_GPT_4O)