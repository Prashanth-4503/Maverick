import csv
from django.core.management.base import BaseCommand
from myapp.models import Competency, Question, Answer

class Command(BaseCommand):
    help = 'Bulk import quiz topics, questions, and answers from CSV'

    def handle(self, *args, **options):
        with open('quiz_bulk_import.csv', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Create or get topic (competency)
                comp, _ = Competency.objects.get_or_create(
                    name=row['topic'],
                    defaults={'description': f"{row['topic']} questions."}
                )
                # Create question
                q = Question.objects.create(
                    text=row['question'],
                    competency=comp,
                    difficulty=row['difficulty']
                )
                # Add up to 4 answer options
                for i in range(1, 5):
                    answer_text = row.get(f'answer_{i}')
                    if answer_text:
                        Answer.objects.create(
                            question=q,
                            text=answer_text,
                            is_correct=(answer_text.strip() == row['correct'].strip())
                        )
                self.stdout.write(self.style.SUCCESS(f"Imported question: {row['question'][:50]}..."))
        self.stdout.write(self.style.SUCCESS("Quiz import completed!"))
