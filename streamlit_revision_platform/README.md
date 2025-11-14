# Streamlit Paper Revision Platform

## Overview
This Streamlit app connects to your fine-tuned ChatGPT-like model via an HTTP API and helps students revise papers.  
It:
- Lets students enter name & student ID and upload a paper (txt or pdf or docx).
- Sends the paper text to your model endpoint (configurable in `config.json`).
- Parses the model output (expected JSON structure shown in `presets.json`).
- Shows 6 configurable error-categories, expandable to view locations, personalized explanations, and AI suggestions.
- Tracks per-error timers and records edits (insertions, deletions, replacements in word-count).
- Allows in-browser edits and re-submission for re-check.
- Generates a zip package containing all logs, original & final versions, step segmentation, error-detection results and full interaction log.

## Quick start (local)
1. Create a Python venv, install requirements:
   ```
   python -m venv venv
   source venv/bin/activate   # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
2. Edit `config.json` to point to your model API endpoint and set API key (if any).
3. Run:
   ```
   streamlit run app.py
   ```
4. Use the UI, then press "Download results" to get the zip.

## Files
- app.py : main Streamlit app
- utils.py : helper functions (text extraction, diff counting, logging)
- presets.json : editable presets (6 error codes, labels, and model prompts)
- config.json : API endpoint and key
- run.sh : convenience script to run locally

