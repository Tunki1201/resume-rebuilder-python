import streamlit as st
import requests
import json
import os

import logging
from adobe.pdfservices.operation.auth.service_principal_credentials import (
    ServicePrincipalCredentials,
)
from adobe.pdfservices.operation.exception.exceptions import (
    ServiceApiException,
    ServiceUsageException,
    SdkException,
)
from adobe.pdfservices.operation.io.cloud_asset import CloudAsset
from adobe.pdfservices.operation.io.stream_asset import StreamAsset
from adobe.pdfservices.operation.pdf_services import PDFServices
from adobe.pdfservices.operation.pdf_services_media_type import PDFServicesMediaType
from adobe.pdfservices.operation.pdfjobs.jobs.document_merge_job import DocumentMergeJob
from adobe.pdfservices.operation.pdfjobs.params.documentmerge.document_merge_params import (
    DocumentMergeParams,
)
from adobe.pdfservices.operation.pdfjobs.params.documentmerge.output_format import (
    OutputFormat,
)
from adobe.pdfservices.operation.pdfjobs.result.document_merge_result import (
    DocumentMergePDFResult,
)

# Initialize the logger
logging.basicConfig(level=logging.INFO)

# Set page configuration to wide mode
st.set_page_config(layout="wide", page_title="Resume Rebuilder")

# Custom CSS to make the container wider
st.markdown(
    """
<style>
    .block-container {
        max-width: 1000px;
        padding-top: 2rem;
        padding-right: 8rem;
        padding-left: 8rem;
        padding-bottom: 2rem;
    }
    
    /* Additional styling for better appearance */
    .stTextArea textarea {
        font-size: 1rem;
    }
    
    .stButton button {
        width: 100%;
    }
</style>
""",
    unsafe_allow_html=True,
)


def convert_to_document(content, output_format=OutputFormat.PDF, template_path=None):
    """Convert text content to PDF or DOCX using Adobe PDF Services API"""
    try:
        print(
            "------------------------this is the template path----------", template_path
        )
        # Use default template if none provided
        if template_path is None:
            template_path = "./resumeTemplate.docx"
        # Check if content is already a dictionary (JSON object)
        if isinstance(content, dict):
            # Format the data to match the template structure
            formatted_data = {
                "Name": content.get("name", ""),
                "role": content.get("role", ""),
                "email": content.get("email", ""),
                "phone": content.get("phone", ""),
                "address": content.get("address", ""),
                "linkedin": content.get("linkedin", ""),
                "summary": content.get("summary", ""),
                "skills": format_skills(content.get("skills", [])),
                "experience": format_experience(content.get("experience", [])),
                "education": format_education(
                    content.get("education", []), template_path
                ),
            }
            # Format contact info to avoid empty separators
            formatted_data = format_contact_info(formatted_data)
            resume_data = {"user": formatted_data}
        else:
            # If content is a string, try to parse it as JSON
            try:
                json_content = json.loads(content)
                formatted_data = {
                    "Name": json_content.get("name", ""),
                    "role": json_content.get("role", ""),
                    "email": json_content.get("email", ""),
                    "phone": json_content.get("phone", ""),
                    "address": json_content.get("address", ""),
                    "linkedin": json_content.get("linkedin", ""),
                    "summary": json_content.get("summary", ""),
                    "skills": format_skills(json_content.get("skills", [])),
                    "experience": format_experience(json_content.get("experience", [])),
                    "education": format_education(json_content.get("education", [])),
                }
                # Format contact info to avoid empty separators
                formatted_data = format_contact_info(formatted_data)
                resume_data = {"user": formatted_data}
            except (json.JSONDecodeError, TypeError):
                # Fall back to the original text parsing logic
                logging.warning("Falling back to text parsing for resume content")
                sections = parse_text_content(content)
                resume_data = {"user": sections}

        # Debug output to check the data structure
        # Additional debug for experience data specifically
        if "user" in resume_data and "education" in resume_data["user"]:
            logging.info(
                f"Experience data structure: {json.dumps(resume_data['user']['education'], indent=2)}"
            )

        # Initial setup, create credentials instance
        credentials = ServicePrincipalCredentials(
            client_id=os.getenv("PDF_SERVICES_CLIENT_ID"),
            client_secret=os.getenv("PDF_SERVICES_CLIENT_SECRET"),
        )

        # Creates a PDF Services instance
        pdf_services = PDFServices(credentials=credentials)

        # Read the template file
        with open(template_path, "rb") as file:
            input_stream = file.read()

        # Creates an asset from source file and upload
        input_asset = pdf_services.upload(
            input_stream=input_stream, mime_type=PDFServicesMediaType.DOCX
        )

        print(
            "--------This is the final resume data for convet2DOC---------", resume_data
        )
        # Create parameters for the job
        document_merge_params = DocumentMergeParams(
            json_data_for_merge=resume_data, output_format=output_format
        )

        # Creates a new job instance
        document_merge_job = DocumentMergeJob(
            input_asset=input_asset, document_merge_params=document_merge_params
        )

        # Submit the job and gets the job result
        location = pdf_services.submit(document_merge_job)

        from adobe.pdfservices.operation.pdfjobs.result.document_merge_result import (
            DocumentMergePDFResult,
        )

        pdf_services_response = pdf_services.get_job_result(
            location, DocumentMergePDFResult
        )

        # Get content from the resulting asset(s)
        result_asset = pdf_services_response.get_result().get_asset()
        stream_asset = pdf_services.get_content(result_asset)

        # Return the document content as bytes
        return stream_asset.get_input_stream()

    except (ServiceApiException, ServiceUsageException, SdkException) as e:
        logging.exception(f"Exception encountered while executing operation: {e}")
        raise e


def convert_to_pdf(content, template_path="./resumeTemplate.docx"):
    """Convert text content to PDF using Adobe PDF Services API"""
    try:
        # Check if content is already a dictionary (JSON object)
        if isinstance(content, dict):
            # Format the data to match the template structure
            formatted_data = {
                "Name": content.get("name", ""),
                "role": content.get("role", ""),
                "email": content.get("email", ""),
                "phone": content.get("phone", ""),
                "address": content.get("address", ""),
                "linkedin": content.get("linkedin", ""),
                "summary": content.get("summary", ""),
                "skills": format_skills(content.get("skills", [])),
                "experience": format_experience(content.get("experience", [])),
                "education": format_education(content.get("education", [])),
            }
            # Format contact info to avoid empty separators
            formatted_data = format_contact_info(formatted_data)
            resume_data = {"user": formatted_data}
        else:
            # If content is a string, try to parse it as JSON
            try:
                json_content = json.loads(content)
                formatted_data = {
                    "Name": json_content.get("name", ""),
                    "role": json_content.get("role", ""),
                    "email": json_content.get("email", ""),
                    "phone": json_content.get("phone", ""),
                    "address": json_content.get("address", ""),
                    "linkedin": json_content.get("linkedin", ""),
                    "summary": json_content.get("summary", ""),
                    "skills": format_skills(json_content.get("skills", [])),
                    "experience": format_experience(json_content.get("experience", [])),
                    "education": format_education(json_content.get("education", [])),
                }
                # Format contact info to avoid empty separators
                formatted_data = format_contact_info(formatted_data)
                resume_data = {"user": formatted_data}
            except (json.JSONDecodeError, TypeError):
                # Fall back to the original text parsing logic
                logging.warning("Falling back to text parsing for resume content")
                sections = parse_text_content(content)
                resume_data = {"user": sections}

        # Debug output to check the data structure
        logging.info(f"Template data: {json.dumps(resume_data, indent=2)}")

        # Initial setup, create credentials instance
        credentials = ServicePrincipalCredentials(
            client_id=os.getenv("PDF_SERVICES_CLIENT_ID"),
            client_secret=os.getenv("PDF_SERVICES_CLIENT_SECRET"),
        )

        # Creates a PDF Services instance
        pdf_services = PDFServices(credentials=credentials)

        # Read the template file
        with open(template_path, "rb") as file:
            input_stream = file.read()

        # Creates an asset from source file and upload
        input_asset = pdf_services.upload(
            input_stream=input_stream, mime_type=PDFServicesMediaType.DOCX
        )

        # Create parameters for the job
        document_merge_params = DocumentMergeParams(
            json_data_for_merge=resume_data, output_format=OutputFormat.PDF
        )

        # Creates a new job instance
        document_merge_job = DocumentMergeJob(
            input_asset=input_asset, document_merge_params=document_merge_params
        )

        # Submit the job and gets the job result
        location = pdf_services.submit(document_merge_job)
        pdf_services_response = pdf_services.get_job_result(
            location, DocumentMergePDFResult
        )

        # Get content from the resulting asset(s)
        result_asset = pdf_services_response.get_result().get_asset()
        stream_asset = pdf_services.get_content(result_asset)

        # Return the PDF content as bytes
        return stream_asset.get_input_stream()

    except (ServiceApiException, ServiceUsageException, SdkException) as e:
        logging.exception(f"Exception encountered while executing operation: {e}")
        raise e


def format_contact_info(data):
    """Format contact information to avoid empty separators"""
    # Create a copy of the data to avoid modifying the original
    formatted_data = data.copy()

    # Create a combined contact field that only includes separators between non-empty fields
    contact_fields = []

    # Add non-empty fields to the list
    if formatted_data.get("email"):
        contact_fields.append(formatted_data["email"])

    if formatted_data.get("phone"):
        contact_fields.append(formatted_data["phone"])

    if formatted_data.get("address"):
        contact_fields.append(formatted_data["address"])

    if formatted_data.get("linkedin"):
        contact_fields.append(formatted_data["linkedin"])

    # Join the non-empty fields with the separator
    formatted_data["contact_info"] = (
        " | ".join(contact_fields) if contact_fields else ""
    )

    return formatted_data


def format_skills(skills):
    """Format skills list into a string with categories"""
    if not skills:
        return ""

    # If skills is already a formatted string, return it
    if isinstance(skills, str):
        # Check if the string contains category headers in the desired format
        if "- " in skills and ":" in skills:
            # Already in the desired format with categories
            lines = [line.strip() for line in skills.split("\n") if line.strip()]
            return "<br/>".join(lines)

        # Try to parse a comma-separated list into categories
        elif "," in skills:
            # Split by commas and clean up
            skill_items = [item.strip() for item in skills.split(",") if item.strip()]
            # Group all items under a generic "Skills" category
            return f"- Skills: {', '.join(skill_items)}"

        # Check if the string contains category headers without bullet points
        elif ":" in skills and "\n" in skills:
            lines = []
            for line in skills.split("\n"):
                if line.strip():
                    if ":" in line and not line.strip().startswith("-"):
                        lines.append(f"- {line.strip()}")
                    else:
                        lines.append(line.strip())
            return "<br/>".join(lines)

        return skills

    # Handle list of dictionaries with "category" and "skills" properties
    if isinstance(skills, list) and skills and isinstance(skills[0], dict):
        formatted_skills = []
        for skill_item in skills:
            # Check if the dictionary has "category" and "skills" keys
            if "category" in skill_item and "skills" in skill_item:
                category = skill_item["category"]
                skill_list = skill_item["skills"]
                formatted_skills.append(f"- {category}: {skill_list}")
            else:
                # Handle the original format (each dict containing a category and its skills)
                for category, skill_list in skill_item.items():
                    if isinstance(skill_list, list):
                        skills_str = ", ".join(skill_list)
                    else:
                        skills_str = str(skill_list)
                    formatted_skills.append(f"- {category}: {skills_str}")
        return "<br/>".join(formatted_skills)

    # If skills is a list of strings, process each item
    if isinstance(skills, list):
        formatted_skills = []
        for skill in skills:
            # Add each skill as is, without the "- " prefix
            if isinstance(skill, str):
                formatted_skills.append(skill)

        # If we successfully formatted skills, return them
        if formatted_skills:
            return "- ".join(formatted_skills)

        # If we couldn't format, just return the original list
        return skills

    # If skills is a dictionary with categories
    if isinstance(skills, dict):
        formatted_skills = []
        for category, skill_list in skills.items():
            if isinstance(skill_list, list):
                skills_str = ", ".join(skill_list)
            else:
                skills_str = str(skill_list)
            formatted_skills.append(f"- {category}: {skills_str}")
        return "<br/>".join(formatted_skills)

    # Try to parse skills from a string that looks like:
    # Category: Skill1, Skill2
    # Another Category: Skill3, Skill4
    if isinstance(skills, str) and ":" in skills:
        lines = []
        for line in skills.split("\n"):
            if line.strip():
                if not line.strip().startswith("-"):
                    lines.append(f"- {line.strip()}")
                else:
                    lines.append(line.strip())
        return "<br/>".join(lines)

    return str(skills)


def format_experience(experience):
    """Format experience data to match the template structure"""
    if not isinstance(experience, list):
        # If it's already a string, return it as is
        return experience if experience else ""

    formatted_experience = []

    for exp in experience:
        if isinstance(exp, dict):
            # Create a new dictionary with the expected structure
            formatted_exp = {
                "company": exp.get("company", ""),
                "role": exp.get("role", ""),
                "location": exp.get("location", ""),
                "period": exp.get("period", ""),
                "responsibilities": [],
            }

            # Handle responsibilities
            responsibilities = exp.get("responsibilities", [])
            if responsibilities:
                if isinstance(responsibilities, list):
                    # Convert each string to an object with an "item" property
                    formatted_exp["responsibilities"] = [
                        {"item": resp} for resp in responsibilities
                    ]
                else:
                    # Convert string to list by splitting on newlines or bullet points
                    if isinstance(responsibilities, str):
                        # Split by newlines and/or bullet points
                        resp_items = []
                        for line in responsibilities.split("\n"):
                            line = line.strip()
                            if line:
                                # Remove bullet points if they exist
                                if (
                                    line.startswith("•")
                                    or line.startswith("-")
                                    or line.startswith("*")
                                ):
                                    line = line[1:].strip()
                                resp_items.append({"item": line})
                        formatted_exp["responsibilities"] = resp_items
                    else:
                        # Fallback for unexpected types
                        formatted_exp["responsibilities"] = [
                            {"item": str(responsibilities)}
                        ]

            formatted_experience.append(formatted_exp)

    # Log the formatted experience for debugging
    logging.info(f"Formatted experience: {json.dumps(formatted_experience, indent=2)}")

    return formatted_experience


def format_education(education, template_path=None):
    """Format education list into appropriate structure based on template"""
    if not isinstance(education, list):
        return education if education else ""

    # Use template-specific formatting if it's resumeTemplate1.docx
    if template_path and "resumeTemplate1.docx" in template_path:
        return format_education_template1(education)
    else:
        return format_education_classic(education)


def format_education_template1(education):
    """Format education for resumeTemplate1.docx structure"""
    if not isinstance(education, list):
        return education if education else ""

    formatted_education = []

    for edu in education:
        if isinstance(edu, dict):
            formatted_edu = {
                # Create dictionary without 'university' prefix to match template
                "institution": edu.get("institution", ""),
                "field": edu.get("field", ""),
                "degree": edu.get("degree", ""),
                "location": edu.get("location", ""),
                "gpa": edu.get("gpa", ""),
                "period": "",  # Will format period from various possible inputs
            }

            # Handle period formatting
            if edu.get("yearStart") and edu.get("yearEnd"):
                formatted_edu["period"] = (
                    f"{edu.get('yearStart')} - {edu.get('yearEnd')}"
                )
            elif edu.get("yearEnd"):
                formatted_edu["period"] = str(edu.get("yearEnd"))
            elif edu.get("year"):
                formatted_edu["period"] = str(edu.get("year"))

            # Add comma before degree if field exists
            if formatted_edu["field"] and formatted_edu["degree"]:
                formatted_edu["degree"] = f", {formatted_edu['degree']}"

            formatted_education.append(formatted_edu)

    return formatted_education


def format_education_classic(education):
    """Format education list into HTML string for classic template"""
    if not isinstance(education, list):
        return education if education else ""

    formatted = []
    for edu in education:
        if isinstance(edu, dict):
            edu_line = []

            # Add styling similar to experience section
            institution_info = f"<div style=\"margin-left: 0 !important; padding: 0; text-indent: 0; display: block; width: 100%;\"><span style=\"font-weight: bold\">{edu.get('institution', '')}</span>"

            # Add location if present
            if edu.get("location"):
                institution_info += f", {edu.get('location')}"

            # Build degree info
            degree_info = ""
            if edu.get("degree"):
                degree_info += f"{edu.get('degree', '')}"
            if edu.get("field"):
                if degree_info:
                    degree_info += f" in {edu.get('field', '')}"
                else:
                    degree_info += f"{edu.get('field', '')}"

            # Handle year formatting with support for yearStart/yearEnd
            year_info = ""
            if edu.get("yearStart") and edu.get("yearEnd"):
                year_info = f"{edu.get('yearStart')} - {edu.get('yearEnd')}"
            elif edu.get("yearEnd"):
                year_info = f"{edu.get('yearEnd')}"
            elif edu.get("yearStart"):
                year_info = f"{edu.get('yearStart')}"
            elif edu.get("year"):
                year_info = edu.get("year")

            # Add degree and year info with proper separator
            if degree_info or year_info:
                institution_info += " | "

                if degree_info:
                    institution_info += (
                        f'<span style="font-style: italic">{degree_info}</span>'
                    )

                if year_info:
                    if degree_info:
                        institution_info += f", {year_info}"
                    else:
                        institution_info += f"{year_info}"

            institution_info += "</div>"  # Close the div tag
            edu_line.append(institution_info)

            # Add any additional details if present
            if edu.get("details"):
                if isinstance(edu.get("details"), list):
                    for detail in edu.get("details"):
                        edu_line.append(
                            f'<div style="margin-left: 0 !important; padding: 0; text-indent: 0; display: block; width: 100%;">• {detail.strip()}</div>'
                        )
                else:
                    edu_line.append(
                        f"<div style=\"margin-left: 0 !important; padding: 0; text-indent: 0; display: block; width: 100%;\">• {edu.get('details').strip()}</div>"
                    )

            formatted.append("<br/>".join(edu_line))

    return "<br/><br/>\n\n".join(formatted)


def parse_text_content(content):
    """Parse text content into structured data"""
    lines = content.strip().split("\n")

    sections = {
        "Name": "",
        "role": "",
        "email": "",
        "phone": "",
        "address": "",
        "linkedin": "",
        "summary": "",
        "skills": "",
        "experience": "",
        "education": "",
    }

    # First line is name
    if lines and lines[0].strip():
        sections["Name"] = lines[0].strip()

    # Second line is role
    if len(lines) > 1 and lines[1].strip():
        sections["role"] = lines[1].strip()

    # Parse contact info (third line)
    if len(lines) > 2 and lines[2].strip():
        contact_line = lines[2].strip()
        contact_parts = contact_line.split("|")
        if len(contact_parts) >= 1:
            sections["email"] = contact_parts[0].strip()
        if len(contact_parts) >= 2:
            sections["phone"] = contact_parts[1].strip()
        if len(contact_parts) >= 3:
            sections["address"] = contact_parts[2].strip()
        if len(contact_parts) >= 4:
            sections["linkedin"] = contact_parts[3].strip()

    # Find section headers and extract content
    current_section = None
    section_content = []

    # Start from line 4 (after name, role, and contact info)
    for i in range(3, len(lines)):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            continue

        # Check if this line is a section header
        if (
            line.upper() == "SUMMARY"
            or line.upper() == "SKILLS"
            or line.upper() == "EXPERIENCE"
            or line.upper() == "EDUCATION"
        ):
            # Save previous section content if any
            if current_section and section_content:
                sections[current_section.lower()] = "\n".join(section_content).strip()
                section_content = []

            current_section = line.lower()
        # Check if line starts with a section header
        elif (
            line.upper().startswith("SUMMARY ")
            or line.upper().startswith("SKILLS ")
            or line.upper().startswith("EXPERIENCE ")
            or line.upper().startswith("EDUCATION ")
        ):
            # Save previous section content if any
            if current_section and section_content:
                sections[current_section.lower()] = "\n".join(section_content).strip()
                section_content = []

            # Extract the section name
            if line.upper().startswith("SUMMARY"):
                current_section = "summary"
            elif line.upper().startswith("SKILLS"):
                current_section = "skills"
            elif line.upper().startswith("EXPERIENCE"):
                current_section = "experience"
            elif line.upper().startswith("EDUCATION"):
                current_section = "education"
        elif current_section and line:  # Add content to current section
            section_content.append(line)

    # Save the last section
    if current_section and section_content:
        sections[current_section.lower()] = "\n".join(section_content).strip()

    return sections


def main():
    st.title("Resume Rebuilder")

    # Initialize session state to store results
    if "result" not in st.session_state:
        st.session_state.result = None
    if "resume_content" not in st.session_state:
        st.session_state.resume_content = None
    if "template_path" not in st.session_state:
        st.session_state.template_path = "./resumeTemplate.docx"
    if "stored_resume_json" not in st.session_state:
        st.session_state.stored_resume_json = None

    # # Template Selection
    # st.header("Select Resume Template")
    # template_options = {
    #     "Classic Template": "./resumeTemplate.docx",
    #     "Professional Template": "./resumeTemplate1.docx",
    #     "Creative Template": "./resumeTemplate2.docx",
    # }

    # # Create columns for template selection
    # col1, col2 = st.columns([2, 1])

    # with col1:
    #     selected_template = st.radio(
    #         "Choose a template style:",
    #         options=list(template_options.keys()),
    #         index=0,
    #         horizontal=True,
    #     )

    # # Update template path based on selection
    # st.session_state.template_path = template_options[selected_template]
    # Job Description
    job_description = st.text_area(
        "Job Description", placeholder="Paste the job description here", height=200
    )

    # Resume Upload
    old_resume = st.file_uploader("Upload Your Old Resume", type=["pdf", "docx"])

    # Companies Information
    st.header("Companies Information")
    st.markdown(
        """
    Add information about companies you've worked for. This helps provide context about your 
    professional background and work experience. The resume rebuilder will use this information 
    to highlight your relevant experience and accomplishments at each company.
    """
    )
    companies = []

    for i in range(3):
        st.subheader(f"Company {i + 1}")
        col1, col2 = st.columns(2)

        with col1:
            company_name = st.text_input(f"Company Name", key=f"name_{i}")
            company_size = st.text_input(
                f"Company Size",
                placeholder="E.g., Startup, SME, Large Enterprise",
                key=f"size_{i}",
            )

        with col2:
            company_background = st.text_area(
                f"Company Background",
                placeholder="E.g., Technology, Healthcare, Finance",
                height=120,
                key=f"background_{i}",
            )

        companies.append(
            {
                "name": company_name,
                "background": company_background,
                "size": company_size,
            }
        )

    # Submit Button
    if st.button("Rebuild Resume"):
        with st.spinner("Rebuilding Resume..."):
            # Prepare the form data
            files = {}
            if old_resume:
                files["old_resume"] = old_resume

            data = {
                "job_description": job_description,
                "companies": json.dumps(companies),
            }

            # Make the API request
            try:
                response = requests.post(
                    "http://localhost:8000/api/rebuild-resume", data=data, files=files
                )

                if response.status_code == 200:
                    # Store result in session state
                    st.session_state.result = response.json()
                    st.success("Resume rebuilt successfully!")

                    # Handle different response structures
                    if (
                        isinstance(st.session_state.result, dict)
                        and "resumeContent" in st.session_state.result
                    ):
                        st.session_state.resume_content = st.session_state.result[
                            "resumeContent"
                        ]
                    elif (
                        isinstance(st.session_state.result, list)
                        and len(st.session_state.result) > 0
                    ):
                        # If result is a list, take the first item or handle appropriately
                        st.session_state.resume_content = str(
                            st.session_state.result[0]
                        )
                    else:
                        st.session_state.resume_content = str(st.session_state.result)
                else:
                    st.error(f"Failed to rebuild resume: {response.text}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")

    # Display resume preview and download buttons if we have results
    if (
        st.session_state.result is not None
        and st.session_state.resume_content is not None
    ):
        st.text_area(
            "New Resume Preview", value=st.session_state.resume_content, height=500
        )

        # Add export buttons
        col2 = st.columns(1)[0]

        with col2:
            try:
                # Check if template exists
                if not os.path.exists(st.session_state.template_path):
                    st.error(
                        f"Template file not found at {st.session_state.template_path}"
                    )
                else:
                    # Get resumeJson from the response if available
                    if (
                        isinstance(st.session_state.result, dict)
                        and "resumeJson" in st.session_state.result
                    ):
                        resume_json = st.session_state.result["resumeJson"]

                        print(
                            "111111111111111111111111111111111222222222222222222---------------------11111111111111111111111",
                            resume_json,
                        )
                        # Store the resume_json in session state to prevent it from being lost
                        if resume_json and not hasattr(
                            st.session_state, "stored_resume_json"
                        ):
                            st.session_state.stored_resume_json = resume_json

                        # If resume_json is empty but we have a stored version, use that
                        if not resume_json and hasattr(
                            st.session_state, "stored_resume_json"
                        ):
                            resume_json = st.session_state.stored_resume_json
                            logging.info("Using stored resume_json from session state")

                        # Create columns for PDF and DOCX download buttons
                        pdf_col, docx_col = st.columns(2)

                        with pdf_col:
                            if st.button("Download as PDF"):
                                with st.spinner("Converting to PDF..."):
                                    pdf_bytes = convert_to_document(
                                        resume_json,
                                        OutputFormat.PDF,
                                        st.session_state.template_path,
                                    )

                                    # Use st.download_button separately
                                    st.download_button(
                                        label="Click to Download PDF",
                                        data=pdf_bytes,
                                        file_name="rebuilt_resume.pdf",
                                        mime="application/pdf",
                                        key="pdf_download",
                                    )

                        with docx_col:
                            if st.button("Download as DOCX"):
                                with st.spinner("Converting to DOCX..."):
                                    docx_bytes = convert_to_document(
                                        resume_json,
                                        OutputFormat.DOCX,
                                        st.session_state.template_path,
                                    )

                                    # Use st.download_button separately
                                    st.download_button(
                                        label="Click to Download DOCX",
                                        data=docx_bytes,
                                        file_name="rebuilt_resume.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        key="docx_download",
                                    )
                    else:
                        st.error("Resume JSON data not found in the response")
            except Exception as e:
                st.error(f"Document conversion failed: {str(e)}")


if __name__ == "__main__":
    main()
