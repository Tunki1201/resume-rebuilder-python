from fastapi import FastAPI, UploadFile, Form, File
from pydantic import BaseModel
from typing import List
import json
import os
from anthropic import Anthropic
import pymupdf  # Changed from fitz to pymupdf
import tempfile  # Add this import
import tempfile  # Add this import
import docx2txt  # Add this import for DOCX support
import subprocess

app = FastAPI()


class CompanyBackground(BaseModel):
    name: str
    background: str
    size: str


def summarize_text(text: str, max_length=8000) -> str:
    if not text:
        return ""

    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    if not paragraphs:
        return ""

    result = ""
    current_length = 0

    for paragraph in paragraphs:
        # Estimate tokens (roughly 0.25 tokens per character)
        estimated_tokens = len(paragraph) * 0.25

        if current_length + estimated_tokens > max_length:
            break

        result += paragraph + "\n"
        current_length += estimated_tokens

    return result.strip()


@app.post("/api/rebuild-resume")
async def rebuild_resume(
    job_description: str = Form(...),
    companies: str = Form(...),
    old_resume: UploadFile | None = File(None),
):
    # Parse the companies JSON string
    companies_data = json.loads(companies)

    # Read the old resume content if provided
    old_resume_content = ""
    if old_resume:
        content = await old_resume.read()
        file_extension = (
            old_resume.filename.split(".")[-1].lower() if old_resume.filename else ""
        )

        # Handle different file types
        if file_extension in ["pdf"]:
            # Handle PDF files using PyMuPDF
            try:
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name

                doc = pymupdf.open(temp_path)  # Changed from fitz.open to pymupdf.open
                old_resume_content = ""
                for page in doc:
                    old_resume_content += page.get_text()
                doc.close()

                # Clean up temp file
                os.unlink(temp_path)
            except Exception as e:
                print(f"Error reading PDF file: {e}")
                old_resume_content = "Error: Could not read PDF file."

        elif file_extension in ["doc", "docx"]:
            # Handle DOC/DOCX files
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f".{file_extension}"
                ) as temp_file:
                    temp_file.write(content)
                    temp_path = temp_file.name

                if file_extension == "docx":
                    # Use docx2txt for DOCX files
                    old_resume_content = docx2txt.process(temp_path)
                else:  # DOC files
                    # Use antiword for DOC files if available, otherwise try textract
                    try:
                        # Try antiword first (needs to be installed on the system)
                        old_resume_content = subprocess.check_output(
                            ["antiword", temp_path], stderr=subprocess.STDOUT
                        ).decode("utf-8", errors="replace")
                    except (subprocess.SubprocessError, FileNotFoundError):
                        try:
                            # Fallback to textract if available
                            import textract

                            old_resume_content = textract.process(temp_path).decode(
                                "utf-8", errors="replace"
                            )
                        except ImportError:
                            old_resume_content = "Error: Could not process DOC file. Please install antiword or textract."

                # Clean up temp file
                os.unlink(temp_path)
            except Exception as e:
                print(f"Error handling DOC/DOCX file: {e}")
                old_resume_content = f"Error: Could not process DOC/DOCX file: {str(e)}"

        else:
            # Handle text-based files with different encodings
            try:
                # Try UTF-8 first
                old_resume_content = content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    # Try Windows-1252 encoding (common in Windows documents)
                    old_resume_content = content.decode("cp1252")
                except UnicodeDecodeError:
                    try:
                        # Try Latin-1 (ISO-8859-1) as a fallback - it can decode any byte
                        old_resume_content = content.decode("latin-1")
                    except Exception as e:
                        # If all else fails, log the error and use an empty string
                        print(f"Error decoding resume file: {e}")
                        old_resume_content = (
                            "Error: Could not read resume file encoding."
                        )
    # Summarize text to avoid token limits
    summarized_job_description = summarize_text(job_description, 2000)

    # Format companies information
    companies_info = ""
    for i, company in enumerate(companies_data):
        companies_info += f"""
Company {i + 1}:
Name: {company.get('name', '')}
Industry: {company.get('background', '')}
Company_Size: {company.get('size', '')}
"""

    # Create the prompt for Claude with updated instructions
    prompt = f"""Create a tailored resume based on the following information:

Resume Content:
{old_resume_content}

Job Description:
{summarized_job_description}

Company Backgrounds:
{companies_info}

First, extract the following personal information from the original resume:
- Full Name
- Role
- Address
- Email address
- LinkedIn profile
- Phone number
- Current/previous companies worked at
- Universities attended
- Degrees earned

Then, create a professional resume that STRONGLY MATCHES the job requirements and aligns with the Company Backgrounds. The primary focus should be on highlighting experiences, skills, and achievements that directly relate to the job description. Use the extracted personal information in the new resume.

Format the resume as follows:

[Full Name]
[Role](Sometimes you generate like that "Senior Software Engineer - Mapping & Localization", But this is not correct. you don't need to add any explanation after role)

[Address]
[Email] | [Phone] | [LinkedIn]

Summary:
[A brief, tailored summary highlighting key qualifications for the job and how they fit with the companies' industries and sizes, but does not include 'Versatile']

Skills:
[Format the skills section with main skill categories and specific skills under each category, like this:
- Category Name: Skill 1, Skill 2, Skill 3
- Another Category: Skill 4, Skill 5, Skill 6
For example:
- Mobile Development: React Native, iOS, Android
- Frontend: React.js, TypeScript, JavaScript
Prioritize skills mentioned in the job description and valuable to the companies' industries and sizes]

Experience:
[List relevant work experience, tailoring descriptions to match job requirements and company backgrounds. When you generate experience, it needs to contain 9 or 10 bullets per each company. Each bullet point should be detailed and substantial (30-35 words each), describing specific achievements with metrics where possible. For example: "Implemented a secure authentication system with Node.js and OAuth 2.0, achieving HIPAA compliance and reducing account-related support inquiries by 25%."]

Education:
[List education details including universities and degrees]


Focus HEAVILY on relevant experience and skills that match the job description and align with the backgrounds of all companies. For each bullet point in the experience section, ensure it demonstrates a skill or achievement that is valuable for the target position. Highlight versatility and adaptability to different company sizes and industries.
When you generate experience, you need to update user's role at each company based on generated experience(user's role is limited to senior level, not lead level).

If the extracted info does not contain Linkedin or Phone, then you don't need to generate them. Just only use contact info from extracted info.
You have to generate only resume, not include explanation about extract information from old resume, not include explanation about your response and 

Additionally, after creating the resume, please also provide the same information in a structured JSON format with the following fields:
- name: The person's full name
- role: The person's professional role/title
- email: Email address
- phone: Phone number (if available)
- address: Physical address
- linkedin: LinkedIn profile (if available)
- summary: A brief professional summary
- skills: A list of relevant skills as an array of objects, where each object contains:
  - category: The skill category name
  - skills: A comma-separated string of skills in that category
  (This must match exactly with the skills listed in the resume text, in the format:
   "- Category Name: Skill 1, Skill 2, Skill 3")
- experience: An array of work experiences, where each experience contains:
  - company: Company name
  - location: Location of the company
  - role: Job title/role at the company (Should show career progression, starting from junior positions and advancing to more senior roles. For example: 1."Fullstack Engineer" → "Senior FullStack Engineer" → "Senior Fullstack Engineer" 2. "Frontend Engineer" → "FullStack Engineer" → "Senior Fullstack Engineer")
  - period: Employment period (e.g., "2020 - Present")
  - responsibilities: An array of bullet points describing achievements and responsibilities
    (These MUST be EXACTLY the same bullet points that appear in the resume text. Each bullet point should be detailed and substantial (30-35 words each), describing specific achievements with metrics where possible.)
- education: An array of education details, where each entry contains:
  - location: Location of the institution (optional)
  - institution: Name of the educational institution
  - degree: Degree obtained
  - field: Field of study
  - yearStart: Start year (optional)
  - yearEnd: Graduation year
  - gpa: GPA if available (optional)

Please provide both the formatted resume text AND the JSON structure.
"""

    try:
        # Initialize Anthropic client
        anthropic = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

        # Call Claude API
        message = anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract resume content from response
        resume_content = message.content[0].text

        # Try to extract JSON from the response
        json_data = {}
        try:
            # Look for JSON block in the response
            import re

            # First try to find JSON in a code block
            json_match = re.search(
                r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", resume_content, re.DOTALL
            )
            if json_match:
                json_text = json_match.group(1)
                json_data = json.loads(json_text)
                # Remove the JSON block from the resume content
                resume_content = re.sub(
                    r"```(?:json)?\s*\{[\s\S]*?\}\s*```",
                    "",
                    resume_content,
                    flags=re.DOTALL,
                ).strip()
            else:
                # Try to find a standalone JSON object (looking for a complete JSON structure with education field)
                json_match = re.search(
                    r'(\{[\s\S]*?"education"\s*:\s*\[[\s\S]*?\]\s*\})',
                    resume_content,
                    re.DOTALL,
                )
                if json_match:
                    json_text = json_match.group(1)
                    try:
                        json_data = json.loads(json_text)
                        # Remove the JSON object from the resume content
                        resume_content = resume_content.replace(json_text, "").strip()
                    except json.JSONDecodeError:
                        # If direct parsing fails, try to clean the text
                        cleaned_json = re.sub(r"[\n\r\t]+", " ", json_text)
                        json_data = json.loads(cleaned_json)
                        resume_content = resume_content.replace(json_text, "").strip()
        except Exception as json_error:
            print(f"Error parsing JSON from response: {json_error}")

        # Clean up any remaining JSON-like content or markdown artifacts
        resume_content = re.sub(
            r"^\s*\{[\s\S]*\}\s*$", "", resume_content, flags=re.MULTILINE
        ).strip()
        resume_content = re.sub(
            r"^\s*```.*?```\s*$", "", resume_content, flags=re.MULTILINE | re.DOTALL
        ).strip()

        # Return both the cleaned resume content and JSON data
        return {"resumeContent": resume_content, "resumeJson": json_data}

    except Exception as e:
        return {"error": f"An error occurred during resume rebuilding: {str(e)}"}, 500


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
