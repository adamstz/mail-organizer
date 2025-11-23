"""LLM prompts and instructions for email classification.

This module centralizes all prompt templates used for LLM-based email classification.
"""

# System message for classification
CLASSIFICATION_SYSTEM_MESSAGE = "You are an email classification assistant. Return only valid JSON with no explanations."

# Classification prompt template
def build_classification_prompt(subject: str, body: str) -> str:
    """Build a structured prompt for LLM classification.
    
    Args:
        subject: Email subject
        body: Email body (will be truncated to 2000 chars)
        
    Returns:
        Formatted prompt string for LLM
    """
    # Truncate body to avoid token limits
    body_truncated = body[:2000] if body else ""

    return f"""Classify this email into categories, assign a priority level, and provide a brief summary.

Email to classify:
Subject: {subject}
Body: {body_truncated}

Instructions:
- You MUST ONLY choose labels from this exact list (do not create new labels):
  finance, banking, investments, security, authentication, meetings, appointments,
  personal, work, career, shopping, social, entertainment, news, newsletters,
  promotions, marketing, spam, travel, health, education, legal, taxes, receipts,
  notifications, updates, alerts, support, bills, insurance, job-application,
  job-interview, job-offer, job-rejection, job-ad, job-followup
- For job-related emails, use specific job labels:
  * job-application: confirmation that you applied for a job
  * job-interview: interview invitations or scheduling
  * job-offer: job offers received
  * job-rejection: rejection notifications
  * job-ad: job opportunity advertisements (LinkedIn, Indeed, etc.)
  * job-followup: follow-up emails about applications
- Choose 1-3 most relevant labels from the list above
- Assign priority: "high" (urgent/important), "normal" (routine), or "low" (can wait)
- Write a brief summary (1-2 sentences) of the email's main purpose
- Return ONLY a JSON object in this exact format:

{{"labels": ["category1", "category2"], "priority": "normal", "summary": "Brief description of the email"}}

Do not include explanations or markdown. Only output valid JSON. Do not invent labels not in the list."""
