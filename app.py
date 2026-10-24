import io
import os
import re

import streamlit as st
from openai import OpenAI


st.set_page_config(page_title="Play Feedback", page_icon="🎭", layout="centered")


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return os.getenv(name, default).strip()


def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    data = uploaded_file.getvalue()
    if name.endswith(".txt") or name.endswith(".md"):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if name.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    raise ValueError("Please upload a .pdf, .docx, .txt, or .md file.")


SYSTEM_PROMPT = """You are a careful dramaturg giving useful feedback on a playwright's draft.
Read the supplied play closely and avoid inventing plot points, quotations, page numbers, or errors.
Treat creative judgments as suggestions rather than objective facts. If the text is incomplete or
poorly extracted, say so and limit your claims. Produce exactly these five sections:

1. My reading of your play (60–90 words): the apparent central tension, artistic approach, and
desired audience experience. Do not give a plot recap.
2. What's working — and worth preserving: up to 3 specific notes, 40–60 words each. Identify a
concrete choice, where it occurs (scene or verified location), and its effect.
3. Your strongest revision opportunities: up to 3 ranked priorities, 90–130 words each. For each,
give observation, evidence/location, possible effect, and one optional revision direction.
4. Specific fixes and questions: up to 5 notes, 30–50 words each. Label each as Clear error,
Possible inconsistency, or Optional craft suggestion. Use exact excerpts only when verified.
5. Where I'd start (30–50 words): recommend one bounded action drawn from the earlier priorities.

Use headings exactly as listed. Keep the tone direct, respectful, and specific. Do not give a
submission-readiness verdict, confidence percentages, or generic writing advice."""


def clean_output(text: str) -> str:
    text = re.sub(r"\bhigh[- ]level\b", "", text, flags=re.IGNORECASE)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


st.title("Play Feedback")
st.write("Upload a play to receive focused feedback on what is working and where revision may help.")

password = get_secret("APP_PASSWORD")
if password:
    entered = st.text_input("Test password", type="password")
    if entered != password:
        st.info("Enter the test password to continue.")
        st.stop()

uploaded = st.file_uploader("Upload your play", type=["pdf", "docx", "txt", "md"])
if uploaded:
    st.caption(f"Selected: {uploaded.name}")

if st.button("Get feedback", type="primary", disabled=uploaded is None):
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        st.error("The app is missing its OpenAI API secret. Add OPENAI_API_KEY in Streamlit Secrets.")
        st.stop()
    try:
        with st.spinner("Reading the play and preparing feedback…"):
            play_text = extract_text(uploaded)
            if len(play_text.strip()) < 500:
                st.error("The uploaded file did not produce enough readable text to review.")
                st.stop()
            if len(play_text) > 180_000:
                st.warning("This file is very long; the feedback request will use the first 180,000 characters for this test.")
                play_text = play_text[:180_000]
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model="gpt-6.1-sol",
                instructions=SYSTEM_PROMPT,
                input=f"Here is the play to review:\n\n{play_text}",
                max_output_tokens=5000,
            )
            feedback = clean_output(response.output_text)
        st.divider()
        st.subheader("Your feedback")
        st.markdown(feedback)
    except Exception as exc:
        st.error(f"The feedback request could not be completed: {exc}")

st.caption("Test prototype. Uploaded plays are processed for the request and are not saved by this app.")
