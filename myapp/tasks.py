from .models import HackathonSubmission
import zipfile
import time

def evaluate_submission_task(submission_id):
    """
    Evaluates a submission using a FREE, SIMULATED AI response.
    """
    print(f"🔥 EVALUATION FUNCTION CALLED with ID: {submission_id}")
    
    try:
        submission = HackathonSubmission.objects.get(id=submission_id)
        print(f"✅ Found submission: {submission.project_title}")
        
        # Simulate processing time
        print("⏳ Simulating AI processing...")
        time.sleep(2)

        # Set the results
        submission.ai_evaluation_notes = "Match Analysis: This is a simulated AI response. The project appears to be a strong match.\n\nIdentified Purpose: Web application that aligns with requirements."
        submission.ai_evaluation_score = 92
        submission.evaluation_status = 'completed'
        submission.save()
        
        print(f"✅ EVALUATION COMPLETE! Score: 92/100")
        
    except Exception as e:
        print(f"❌ ERROR in evaluation: {e}")
        try:
            submission = HackathonSubmission.objects.get(id=submission_id)
            submission.ai_evaluation_notes = f"Evaluation failed: {e}"
            submission.evaluation_status = 'error'
            submission.save()
        except:
            pass
