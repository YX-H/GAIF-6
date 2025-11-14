# PaperFix - Streamlit Student Paper Review Platform

## Overview
This project provides a Streamlit app that connects to two fine-tuned models (configurable via `config.json`) to:
- Segment student papers into rhetorical sections
- Detect a configurable set of error codes
- Localize occurrences and provide personalized explanations and suggestions
- Allow students to edit inline and track time spent + edit statistics (insert/delete/replace)
- Re-check edits with the AI and generate a downloadable zip package containing:
  - original paper
  - AI segmentation and error detection outputs
  - per-error edits and edit stats
  - chat and interaction logs

## Quick start (Linux / macOS)
1. Unzip the package.
2. (Optional) Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. Edit `config.json` to point to your model endpoints and set environment variable names for API keys.
4. Run:
   ```bash
   streamlit run app.py
   ```

## Notes
- If `api_url` fields are empty, the app uses a mock response for local testing.
- The expected model output format is the `Output Format` you provided in your prompt (JSON with `segment_data` and `error_part`).
- The app stores logs under `student_logs/SESSION_ID/`.