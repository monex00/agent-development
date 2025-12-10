import asyncio
from google.adk.agents import LoopAgent, LlmAgent, SequentialAgent
from google.adk.tools.tool_context import ToolContext
from google.adk.runners import InMemoryRunner
from google.adk.models.lite_llm import LiteLlm


# --- Constants ---
MODEL_GPT_4O = "openai/gpt-4.1" 
AGENT_MODEL = LiteLlm(model=MODEL_GPT_4O)

# --- State Keys ---
STATE_USER_QUERY = "user_query"        # La domanda dell'utente
STATE_DOC_LIST = "doc_structure"       # L'array di ID delle pagine
STATE_CURRENT_IDX = "current_index"    # A che pagina siamo
STATE_CURRENT_TEXT = "current_text"    # Il testo della pagina ATTUALE
STATE_KNOWLEDGE = "knowledge_base"     # Il contesto accumulato
STATE_IS_DONE = "is_processing_done"   # Flag per sapere se abbiamo finito

# --- MOCK DATA 
MOCK_DATABASE = [
    """Page 1: System Architecture Overview.
    The platform is built on a microservices architecture hosted on Google Kubernetes Engine (GKE).
    Services communicate via gRPC. The frontend is a React SPA hosted on Cloud Storage.
    Note: Legacy systems are being deprecated by Q4 2024.""",

    """Page 2: HR Policies - Remote Work.
    Employees are allowed to work remotely 2 days a week.
    Core hours are 10:00 AM to 4:00 PM.
    Please refer to the employee handbook for holiday request procedures.""",

    """Page 3: Cafeteria Weekly Menu (Standard).
    - Monday: Pizza Day (Margherita and Pepperoni options available).
    - Tuesday: Taco Tuesday (Beef and Vegan options).
    - Wednesday: Roast Chicken.
    - Thursday: Pasta / Lasagna.
    - Friday: Fish & Chips.""",

    """Page 4: Backend Code Style Guide (Python).
    When creating factory patterns, avoid generic names.
    BAD EXAMPLE:
    class PizzaFactory:
        def create_cheese(self): ...
    
    GOOD EXAMPLE:
    class RequestHandlerFactory:
        def create_handler(self): ...
    
    DO NOT use food metaphors in production code documentation.""",

    """Page 5: Database Infrastructure.
    Primary data is stored in Cloud Spanner for global consistency.
    Redis is used for caching user sessions.
    Backups are performed every 6 hours automatically.""",

    """Page 6: API Error Handling & Retry Logic.
    The API implements the 'Exponential Backoff' algorithm.
    - Initial retry: 200ms
    - Multiplier: 1.5x
    - Max retries: 3
    If the error persists after 3 tries, a 503 Service Unavailable is returned to the client.""",

    """Page 7: Office Party Photos 2023.
    Link to Google Drive folder: [LINK_REDACTED].
    Please do not share these outside the organization.""",
    
    """Page 8: URGENT UPDATE - Cafeteria Menu Change.
    Effective immediately, due to supply chain issues:
    Monday's Pizza Day is CANCELLED.
    Monday is now Salad Bar Day.
    Pizza Day is moved to Friday (replacing Fish & Chips)."""
]

# --- TOOLS ---

async def fetch_document_structure(user_prompt: str, tool_context: ToolContext):
    """
    Riceve la query utente e chiama una Mock API: Simula il recupero asincrono della struttura dei documenti.
    Ritorna la lista degli ID/Titoli e carica la PRIMA pagina in memoria.
    """
    print(f"[API MOCK] Connessione al Document Store (Async)...")
    await asyncio.sleep(1.0) # Finta latenza
    
    # Inizializza lo stato
    tool_context.state[STATE_DOC_LIST] = MOCK_DATABASE
    tool_context.state[STATE_CURRENT_IDX] = 0
    tool_context.state[STATE_KNOWLEDGE] = ""
    tool_context.state[STATE_USER_QUERY] = user_prompt
    
    # Carica subito la prima pagina nello stato per l'agente successivo
    if MOCK_DATABASE:
        tool_context.state[STATE_CURRENT_TEXT] = MOCK_DATABASE[0]
        tool_context.state[STATE_IS_DONE] = "FALSE"
    else:
        tool_context.state[STATE_CURRENT_TEXT] = "NO_DOCUMENTS"
        tool_context.state[STATE_IS_DONE] = "TRUE"

    return "Document structure fetched and first page loaded."

def process_and_advance(summary: str, relevant: bool, tool_context: ToolContext):
    """
    Salva il riassunto (se rilevante) e carica la pagina successiva nello stato.
    Se non ci sono più pagine, segnala la fine.
    """
    current_text = tool_context.state.get(STATE_CURRENT_TEXT, "N/A")
    # 1. Memorizza il riassunto se rilevante
    if relevant:
        print(f"⚠️ [CHECK] Agent found relevance in text: '{current_text[:30]}...'")
        print(f"[MEMORY] Saving info: {summary[:40]}...")
        current_knowledge = tool_context.state.get(STATE_KNOWLEDGE, "")
        tool_context.state[STATE_KNOWLEDGE] = current_knowledge + f"\n- {summary}"
    else:
        print(f"[SKIP] Skipping irrelevant page.")

    # 2. Avanza l'indice
    current_idx = tool_context.state.get(STATE_CURRENT_IDX, 0)
    next_idx = current_idx + 1
    doc_list = tool_context.state.get(STATE_DOC_LIST, [])

    print(f"[LOOP] Advancing to index {next_idx} of {len(doc_list)}...")
    # await asyncio.sleep(0.3) # Finta latenza lettura pagina successiva

    # 3. Controllo fine loop
    if next_idx >= len(doc_list):
        # Nessuna pagina rimasta
        tool_context.state[STATE_CURRENT_TEXT] = "END_OF_DOCUMENTS"
        tool_context.state[STATE_IS_DONE] = "TRUE"
        return "All pages processed."
    else:
        # Carica la prossima pagina nello stato
        tool_context.state[STATE_CURRENT_IDX] = next_idx
        tool_context.state[STATE_CURRENT_TEXT] = doc_list[next_idx]
        return f"Advanced to page {next_idx}."

def exit_reading_loop(tool_context: ToolContext):
    """Chiama questa funzione SOLO quando non ci sono più pagine da leggere."""
    print("[LOOP EXIT] Reading complete.")
    tool_context.actions.escalate = True
    return {}

# --- AGENTS ---

# 1. SETUP AGENT: Ottiene la lista e prepara il terreno
setup_agent = LlmAgent(
    name="SetupAgent",
    model=AGENT_MODEL,
    instruction="""You are a Document Fetcher.
    Your ONLY job is to call the 'fetch_document_structure' tool to initialize the reading session passing the user's query as input.
    Do not output any text, just call the tool.
    """,
    tools=[fetch_document_structure]
)

# 2. READER AGENT (Inside the Loop): Analizza 1 pagina alla volta
reader_agent = LlmAgent(
    name="PageReaderAgent",
    model=AGENT_MODEL,
    instruction=f"""You are a systematic Document Scanner. Your job IS NOT to answer the user, but ONLY to extract facts.

    **User Query:** {{user_query}}
    **Status:** processing_done = {{is_processing_done}}
    **Content:**
    ```
    {{current_text}}
    ```

    **STRICT RULES:**
    1. **CHECK FOR END:** If 'processing_done' is "TRUE" OR content is "END_OF_DOCUMENTS", you MUST call `exit_reading_loop` immediately.
    2. **DO NOT STOP EARLY:** Even if you find the answer to the user's question, **YOU MUST CONTINUE** scanning to see if there is contradictory info on later pages.
    3. **ACTION:**
       - If content is relevant: Call `process_and_advance` with `relevant=True` and a summary.
       - If content is NOT relevant: Call `process_and_advance` with `relevant=False` (summary ignored).
    """,
    tools=[process_and_advance, exit_reading_loop],
    include_contents='none'
)

# 3. THE LOOP: Contiene il Reader Agent
reading_loop = LoopAgent(
    name="DocumentScanningLoop",
    sub_agents=[reader_agent],
    max_iterations=10 # Safety limit
)

# 4. FINAL ANSWER AGENT: Guarda il contesto accumulato e risponde
final_answer_agent = LlmAgent(
    name="FinalWriterAgent",
    model=AGENT_MODEL,
    instruction=f"""You are a helpful assistant.
    
    The user asked: "{{user_query}}"
    
    I have scanned the documents for you. Here are the extracted notes:
    ====================
    {{knowledge_base}}
    ====================
    
    **INSTRUCTIONS:**
    - Use ONLY the notes above to answer.
    - If the notes section is empty or contains only whitespace, assume no information was found.
    - Do not make up information not present in the notes.
    """,
    include_contents='none' 
)

# --- PIPELINE ---
root_agent = SequentialAgent(
    name="DocAnalysisPipeline",
    sub_agents=[
        setup_agent,      # 1. Scarica la lista
        reading_loop,     # 2. Loopa e riassume
        final_answer_agent # 3. Risponde
    ]
)


""" async def main():
    runner = InMemoryRunner(agent=root_agent)
    
    user_input = "Tell me about the system architecture and retry logic."
    print(f"🤖 USER: {user_input}\n")
    
    # Inizializziamo lo stato con la query utente
    initial_context = {STATE_USER_QUERY: user_input}
    
    result = await runner.run(route="start", context=initial_context)
    
    print("\n" + "="*50)
    print("📢 FINAL RESPONSE:")
    print(result.get_output()) # In ADK questo recupera l'output dell'ultimo step
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main()) """

""" session_service = InMemorySessionService()
SESSION_ID_STATEFUL = "session_state_demo_001"
USER_ID_STATEFUL = "user_state_demo"

async def init_session(app_name:str,user_id:str,session_id:str) -> InMemorySessionService:
    session = await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=session_id
    )
    print(f"Session created: App='{app_name}', User='{user_id}', Session='{session_id}'")
    return session

# Import necessary session components
from google.adk.sessions import InMemorySessionService
 """


""" initial_state = {
    "user_prompt": "How does the retry logic work in the system?",
}

# Create the session, providing the initial state
session_stateful = await session_service_stateful.create_session(
    app_name=APP_NAME, # Use the consistent app name
    user_id=USER_ID_STATEFUL,
    session_id=SESSION_ID_STATEFUL,
    state=initial_state # <<< Initialize state during creation
)
print(f"✅ Session '{SESSION_ID_STATEFUL}' created for user '{USER_ID_STATEFUL}'.")

# Verify the initial state was set correctly
retrieved_session = await session_service_stateful.get_session(app_name=APP_NAME,
                                                         user_id=USER_ID_STATEFUL,
                                                         session_id = SESSION_ID_STATEFUL)
print("\n--- Initial Session State ---")
if retrieved_session:
    print(retrieved_session.state)
else:
    print("Error: Could not retrieve session.") """