from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from crewai import Agent, Task, Crew
from langchain_community.llms import Ollama
from crewai.telemetry import Telemetry
from typing import List
import fitz  # PyMuPDF

# === Disable CrewAI telemetry ===
def noop(*args, **kwargs): pass

def disable_crewai_telemetry():
    for attr in dir(Telemetry):
        if callable(getattr(Telemetry, attr)) and not attr.startswith("__"):
            setattr(Telemetry, attr, noop)

disable_crewai_telemetry()

# === Initialize FastAPI app and LLM ===
app = FastAPI()

llm = Ollama(
    model="llama3.2:latest",
    base_url="http://host.docker.internal:11434",
    temperature=0.7,
    num_predict=500,
)

# === Define Pydantic models ===
class AgentInput(BaseModel):
    role: str
    goal: str
    backstory: str

class TaskInput(BaseModel):
    writer_agent: AgentInput
    verifier_agent: AgentInput
    writing_task_description: str
    writing_task_expected_output: str
    verification_task_description: str
    verification_task_expected_output: str

# === Extract text from multiple PDFs ===
def extract_texts_from_pdfs(files: List[UploadFile]) -> str:
    full_text = ""
    for file in files:
        pdf_bytes = file.file.read()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            for page in doc:
                full_text += page.get_text()
        file.file.seek(0)  # reset file pointer
    return full_text

# === Run CrewAI with multiple PDFs ===
def run_custom_crew_with_pdfs(input_data: TaskInput, pdf_files: List[UploadFile]):
    pdf_context = extract_texts_from_pdfs(pdf_files)

    writer_agent = Agent(
        role=input_data.writer_agent.role,
        goal=input_data.writer_agent.goal,
        backstory=input_data.writer_agent.backstory,
        llm=llm,
        max_iter=10,
        verbose=True,
    )

    verifier_agent = Agent(
        role=input_data.verifier_agent.role,
        goal=input_data.verifier_agent.goal,
        backstory=f"{input_data.verifier_agent.backstory}\n\nUse the following reference:\n{pdf_context}",
        llm=llm,
        max_iter=19,
        verbose=True,
    )

    task1 = Task(
        description=input_data.writing_task_description,
        expected_output=input_data.writing_task_expected_output,
        agent=writer_agent,
    )

    task2 = Task(
        description=input_data.verification_task_description,
        expected_output=input_data.verification_task_expected_output,
        agent=verifier_agent,
    )

    crew = Crew(
        agents=[writer_agent, verifier_agent],
        tasks=[task1, task2],
        process="sequential",
        verbose=3,
    )

    return crew.kickoff()

# === POST endpoint to run the Crew task ===
@app.post("/run-crew-task/")
async def run_crew_task(task_data: str = Form(...), pdf_files: List[UploadFile] = File(...)):
    input_data = TaskInput.parse_raw(task_data)
    result = run_custom_crew_with_pdfs(input_data, pdf_files)
    return {"result": result}
