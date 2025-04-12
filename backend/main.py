from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import aiohttp
from aiohttp import FormData
import json

app = FastAPI()

# Allow CORS for all origins (dev only!)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Async call to LLM container
async def run_to_llm(upload_file_path: str):
    url = "http://llm:5050/run-crew-task/"  # Make sure this matches your service
    task_data_dict = {
        "writer_agent": {
            "role": "Technical PDF Analyst",
            "goal": "Carefully read the provided PDF files and extract relevant technical details about the Rust 3D renderer, including architecture, shader handling, .obj parsing, math, and SCOP requirements.",
            "backstory": "A detail-oriented software engineer with experience in Rust and 3D graphics. Specializes in dissecting documentation and pulling out precise engineering requirements for development teams."
        },
        "verifier_agent": {
            "role": "Technical Summary Writer",
            "goal": "Write a short, clear report that summarizes the most important technical information extracted by the reader agent.",
            "backstory": "An experienced technical communicator who transforms complex findings into brief, accurate summaries for documentation or presentations. Focused on clarity, precision, and relevance."
        },
        "writing_task_description": "Based on the text extracted from the PDF files, identify and list the most critical technical requirements for building a Rust-based 3D renderer (e.g. OpenGL setup, shader implementation, .obj support, matrix math, SCOP compliance). Ignore general background or non-technical filler.",
        "writing_task_expected_output": "A bullet-point or numbered list of key requirements: what the renderer must do, what constraints must be followed, what must be implemented manually (like shaders and parsers), and what tools/libraries are forbidden.",
        "verification_task_description": "Using the extracted list, write a brief and clear summary suitable for inclusion in a report or project overview. It should clearly state the scope and goals of the renderer project.",
        "verification_task_expected_output": "A short paragraph (max 6 sentences) summarizing the goals and implementation requirements for the Rust renderer, written in professional, technical language."
    }

    form = FormData()
    form.add_field(
        "task_data",
        json.dumps(task_data_dict),
        content_type="application/json"
    )

    with open(upload_file_path, "rb") as f:
        form.add_field(
            "pdf_files",
            f,
            filename=os.path.basename(upload_file_path),
            content_type="application/pdf"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return {
                        "error": f"Failed with status {response.status}",
                        "details": await response.text()
                    }

# File upload route
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as f:
        f.write(await file.read())

    llm_response = await run_to_llm(file_path)

    return JSONResponse(content={
        "filename": file.filename,
        "status": "uploaded",
        "llm_response": llm_response
    })
