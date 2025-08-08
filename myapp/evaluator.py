import os
import json
import zipfile
import requests
import logging
from django.conf import settings
from .models import HackathonSubmission

logger = logging.getLogger('ai_evaluation')


def evaluate_submission_task(submission_id):
    """
    Direct evaluation function (no Celery needed)
    Uses OpenRouter (Mistral-7B-Instruct:free) to evaluate hackathon submissions
    """
    try:
        submission = HackathonSubmission.objects.get(id=submission_id)
    except HackathonSubmission.DoesNotExist:
        logger.error(f"Submission {submission_id} not found")
        return

    logger.info(f"Starting evaluation for submission {submission_id}: {submission.project_title}")

    # ------ 1  mark IN-PROGRESS ------------------------------------------------
    submission.evaluation_status = HackathonSubmission.EvaluationStatus.IN_PROGRESS
    submission.save(update_fields=['evaluation_status'])

    # ------ 2  unzip & collect code snippets -----------------------------------
    file_content = ""
    try:
        if not submission.submission_file:
            raise ValueError("No submission file found")

        with zipfile.ZipFile(submission.submission_file, 'r') as zf:
            for filename in zf.namelist():
                if any(filename.endswith(ext) for ext in settings.AI_EVALUATION_SETTINGS['SUPPORTED_EXTENSIONS']):
                    try:
                        content = zf.read(filename).decode('utf-8', errors='ignore')
                        file_content += f"--- File: {filename} ---\n{content}\n\n"
                    except Exception as e:
                        logger.warning(f"Could not read file {filename}: {e}")
                        file_content += f"--- File: {filename} (could not read: {e}) ---\n\n"

    except Exception as e:
        logger.error(f"Error processing ZIP for submission {submission_id}: {e}")
        submission.ai_evaluation_notes = f"Error processing ZIP: {e}"
        submission.evaluation_status = HackathonSubmission.EvaluationStatus.ERROR
        submission.save(update_fields=['ai_evaluation_notes', 'evaluation_status'])
        return

    if not file_content.strip():
        logger.warning(f"No supported files found in submission {submission_id}")
        submission.ai_evaluation_notes = "No supported code files found in submission."
        submission.ai_evaluation_score = 20.0
        submission.evaluation_status = HackathonSubmission.EvaluationStatus.COMPLETED
        submission.save(update_fields=['ai_evaluation_notes', 'ai_evaluation_score', 'evaluation_status'])
        return

    # Truncate large submissions
    max_size = settings.AI_EVALUATION_SETTINGS['MAX_FILE_SIZE']
    if len(file_content) > max_size:
        file_content = file_content[:max_size] + "\n\n... (content truncated)"

    # ------ 3  build prompt -----------------------------------------------------
    prompt = f"""You are an expert code reviewer for a hackathon.

The user was assigned this project:
Title: "{submission.project_title}"
Description: "{submission.project_description}"

The user submitted these files:
{file_content}

Analyse the submission and respond with ONLY a valid JSON object:
{{
  "summary": "Brief summary",
  "strength": "One key strength",
  "improvement": "One key area for improvement",
  "score": <0-100>
}}

Base your score on:
- Alignment with title and description
- Code quality and structure
- Completeness of implementation
- Functionality and logic"""

    # ------ 4  call OpenRouter --------------------------------------------------
    try:
        api_key = settings.validate_openrouter_setup()  # helper in settings.py
        logger.info(f"Calling OpenRouter (Mistral) for submission {submission_id}")

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": settings.OPENROUTER_SITE_URL,
                "X-Title": settings.OPENROUTER_SITE_NAME
            },
            json={
                "model": settings.AI_EVALUATION_SETTINGS['MODEL'],  # mistralai/mistral-7b-instruct:free
                "messages": [
                    {"role": "system",
                     "content": "You are a senior software engineer reviewing hackathon submissions. "
                                "Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": settings.AI_EVALUATION_SETTINGS['MAX_TOKENS'],
                "temperature": settings.AI_EVALUATION_SETTINGS['TEMPERATURE']
            },
            timeout=settings.AI_EVALUATION_SETTINGS['TIMEOUT']
        )

        if response.status_code == 200:
            result_text = response.json()["choices"][0]["message"]["content"].strip()
            ai_json_response = parse_ai_json_response(result_text)
        else:
            logger.error(f"OpenRouter error {response.status_code}: {response.text}")
            ai_json_response = rule_based_fallback(file_content, submission)

    except requests.exceptions.Timeout:
        logger.warning("OpenRouter request timed out")
        ai_json_response = rule_based_fallback(file_content, submission)

    except Exception as e:
        logger.error(f"Unexpected OpenRouter error: {e}")
        ai_json_response = rule_based_fallback(file_content, submission)

    # ------ 5  save results -----------------------------------------------------
    score = ai_json_response.get('score', settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE'])
    if not isinstance(score, (int, float)):
        score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
    score = max(0, min(100, float(score)))

    submission.ai_evaluation_notes = (
        f"Summary: {ai_json_response.get('summary', 'No summary')}\n"
        f"Strength: {ai_json_response.get('strength', 'No strength')}\n"
        f"Improvement: {ai_json_response.get('improvement', 'No improvement')}"
    )
    submission.ai_evaluation_score = score
    submission.evaluation_status = HackathonSubmission.EvaluationStatus.COMPLETED
    submission.save(update_fields=['ai_evaluation_notes', 'ai_evaluation_score', 'evaluation_status'])

    logger.info(f"Evaluation finished for submission {submission_id} – score {score}/100")
    return ai_json_response


# ---------- helper functions (unchanged) --------------------------------------
def parse_ai_json_response(text: str) -> dict:
    try:
        start = text.find('{')
        end = text.rfind('}') + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise ValueError("No JSON found")
    except Exception as e:
        logger.warning(f"JSON parse error: {e}")
        return {
            "summary": "AI response could not be parsed – fallback applied",
            "strength": "N/A",
            "improvement": "N/A",
            "score": 50
        }


def rule_based_fallback(file_content: str, submission) -> dict:
    logger.info(f"Using fallback rules for submission {submission.id}")
    score = settings.AI_EVALUATION_SETTINGS['FALLBACK_SCORE']
    lines = file_content.splitlines()
    file_count = file_content.count('--- File:')

    if file_count >= 3:
        score += 15
    if len(lines) > 50:
        score += 10
    if 'def ' in file_content or 'function ' in file_content:
        score += 10
    if 'class ' in file_content:
        score += 5
    if any(k in file_content.lower() for k in ['import', 'require', 'include']):
        score += 5
    if 'readme' in file_content.lower():
        score += 10

    title_words = submission.project_title.lower().split()
    desc_words = submission.project_description.lower().split()
    matching = sum(1 for w in title_words + desc_words if len(w) > 3 and w in file_content.lower())
    score += min(15, matching * 2)

    score = max(0, min(100, score))
    return {
        "summary": f"Fallback analysis – {file_count} files, {len(lines)} lines.",
        "strength": "Basic code structure present",
        "improvement": "Add documentation and tests",
        "score": score
    }
